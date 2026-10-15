import os
import uuid
import base64
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File, Header
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

# Load environment configuration from backend/.env
BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)
else:
    load_dotenv(override=True)

from app.db import (
    get_db,
    init_db,
    get_database_url,
    get_sanitized_database_url,
    sanitize_error_message,
    is_placeholder_url,
)
from app.models import Conversation, Message, Document, UserPreference
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    MessageItemResponse,
    ConversationMessagesResponse,
    ConversationSummaryResponse,
    SearchMatchItem,
    SearchResponse,
)
from app.schemas.preferences import (
    UserPreferenceUpdate,
    UserPreferenceResponse,
)
from app.schemas.document import (
    DocumentUploadResponse,
    DocumentItemResponse,
    DocumentSummaryResponse,
    PDFGenerateRequest,
    PDFGenerateResponse,
)
from app.services.document_parser import (
    parse_document,
    DocumentParsingError,
    SUPPORTED_EXTENSIONS,
    MAX_FILE_SIZE_BYTES,
)
from app.services.rag_service import (
    retrieve_relevant_context,
    build_aethermind_system_prompt,
    build_grounded_system_prompt,
)
from app.services.pdf_generator import generate_pdf_document, get_generated_pdf


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler to initialize database schema if PostgreSQL is available."""
    init_db()
    yield


# Initialize the FastAPI application
app = FastAPI(
    title="AetherMind API",
    description="Backend API for AetherMind with Google Gemini & PostgreSQL Integration",
    version="0.3.0",
    lifespan=lifespan,
)

# Configure CORS safely for the local Vite development server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    """Root endpoint to quickly check that the server is online."""
    return {
        "app": "AetherMind API",
        "status": "online",
        "docs_url": "/docs",
    }


@app.get("/api/health")
def health_check():
    """
    Health check endpoint confirming backend status and PostgreSQL connection state.
    Preserves existing {"status": "ok", "project": "AetherMind"} contract.
    Does not report connected: true unless a live query actually succeeds.
    """
    db_url = get_database_url()
    safe_url = get_sanitized_database_url()
    has_valid_config = bool(db_url) and not is_placeholder_url(db_url)

    db_status = {
        "configured": has_valid_config,
        "connected": False,
        "target": safe_url if db_url else "Not configured (set DATABASE_URL in backend/.env)",
    }

    if is_placeholder_url(db_url):
        db_status["warning"] = "DATABASE_URL contains placeholder values. Please update backend/.env with your real credentials."

    if has_valid_config:
        try:
            from app.db.database import get_session_factory
            factory = get_session_factory()
            if factory:
                with factory() as session:
                    session.execute(text("SELECT 1"))
                    db_status["connected"] = True
        except Exception as e:
            db_status["connected"] = False
            db_status["error"] = sanitize_error_message(e)

    return {
        "status": "ok",
        "project": "AetherMind",
        "database": db_status,
    }


def analyze_pdf_intent(user_message: str, has_docs: bool) -> tuple[bool, bool]:
    """
    Analyzes whether the user is requesting a PDF file to be generated or provided.
    Returns (is_pdf_requested, is_ambiguous).

    If the user only says 'provide the PDF', 'give me the PDF', 'can you provide the PDF'
    without specifying which document or topic, and no document is attached,
    is_ambiguous=True (Requirement 2).
    """
    import re
    msg = (user_message or "").strip().lower()
    if not msg:
        return False, False

    if not re.search(r"\bpdf\b", msg):
        return False, False

    # Check for standalone ambiguous requests
    ambiguous_patterns = [
        r"^(can you |could you |please )?(provide|give me|send me|show me|download|get|make)( me)? (the|a)? pdf\??$",
        r"^(the |a )?pdf please\??$",
        r"^pdf\??$",
        r"^(where is|where's) the pdf\??$",
        r"^(can i have|i want|send) (the|a) pdf\??$",
    ]
    is_strictly_ambiguous = any(re.match(pat, msg) for pat in ambiguous_patterns)

    if is_strictly_ambiguous and not has_docs:
        return True, True

    # Check if the user is asking an informational capability question rather than a generation request
    # e.g., "Can you generate, attach, or upload physical PDF files, or are you just a text-based AI?"
    is_capability_question = (
        bool(re.search(r"\b(or are you|text[- ]based|capabilities|can you actually|are you capable)\b", msg))
        or (bool(re.match(r"^(can you|do you|are you)\b", msg)) and bool(re.search(r"\b(or|just a|purely|only)\b", msg)))
    )
    if is_capability_question:
        return False, False

    # Action request pattern (e.g., "generate a pdf", "create a pdf", "export to pdf", "download as pdf")
    action_request_pattern = r"(generate|create|make|export|download|save|convert|provide|give me|send me)\b.*pdf"
    if re.search(action_request_pattern, msg) or is_strictly_ambiguous:
        return True, False

    return False, False


@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(
    request: ChatRequest,
    x_user_id: Optional[str] = Header(default="default_user", alias="X-User-ID"),
    db: Session = Depends(get_db),
):
    """
    POST /api/chat endpoint.
    1. Validates the incoming message and any attached documents/images.
    2. Resolves documents by document_ids from PostgreSQL with user isolation.
    3. Handles PDF generation requests and ambiguous clarification (Requirement 2).
    4. Uses RAG retrieval (BM25 keyword relevance) on long documents.
    5. Generates grounded responses with Google Gemini SDK (Gemini).
    6. Persists both the user message and the Gemini response to PostgreSQL.
    7. Returns clear errors without crashing if Gemini quota or operations fail.
    """
    import re
    user_id = x_user_id or "default_user"
    user_message = (request.message or "").strip()

    # 1. Resolve documents: query database for document_ids and merge with direct attachments
    resolved_documents: List[Dict[str, Any]] = []

    if request.document_ids:
        db_docs = (
            db.query(Document)
            .filter(Document.id.in_(request.document_ids), Document.user_id == user_id)
            .all()
        )
        for doc in db_docs:
            resolved_documents.append({
                "id": doc.id,
                "name": doc.filename,
                "type": doc.file_type,
                "text": doc.extracted_text,
                "size": doc.file_size,
            })

    if request.documents:
        existing_ids = {d.get("id") for d in resolved_documents if d.get("id")}
        for d in request.documents:
            if d.id and d.id in existing_ids:
                continue
            resolved_documents.append({
                "id": d.id,
                "name": d.name,
                "type": d.type,
                "text": d.extracted_text or "",
                "size": d.size,
            })

    has_docs = bool(resolved_documents)
    has_images = bool(request.images)

    if not user_message and not has_docs and not has_images:
        raise HTTPException(status_code=400, detail="Message or attachment cannot be empty")

    session_id = request.session_id or f"session-{int(datetime.now().timestamp() * 1000)}"
    formatted_time = datetime.now().strftime("%I:%M %p").lstrip("0")

    # Determine display message for conversation history
    if user_message:
        display_message = user_message
    else:
        names = []
        if resolved_documents:
            names.extend([d["name"] for d in resolved_documents])
        if request.images:
            names.extend([img.name for img in request.images])
        display_message = f"Analyze attached: {', '.join(names)}"

    # Requirement 2: Check for PDF requests and ambiguous "provide the PDF" inquiries
    is_pdf_requested, is_ambiguous = analyze_pdf_intent(user_message, has_docs)

    if is_pdf_requested and is_ambiguous:
        clarification_text = (
            "Which document or topic would you like me to generate as a PDF? "
            "Please specify the document title or topic, or attach an existing file from your library using the **+** button."
        )
        # Save user message and clarification reply to PostgreSQL
        try:
            conversation = (
                db.query(Conversation).filter(Conversation.session_id == session_id).first()
            )
            if not conversation:
                conversation = Conversation(
                    session_id=session_id,
                    title=display_message[:30] + ("..." if len(display_message) > 30 else ""),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                db.add(conversation)
                db.flush()
            else:
                conversation.updated_at = datetime.utcnow()

            db.add(Message(conversation_id=conversation.id, role="user", content=display_message, timestamp=formatted_time, created_at=datetime.utcnow()))
            db.add(Message(conversation_id=conversation.id, role="assistant", content=clarification_text, timestamp=formatted_time, created_at=datetime.utcnow()))
            db.commit()
        except Exception as db_err:
            db.rollback()
            print(f"[Warning] Failed to persist clarification: {sanitize_error_message(db_err)}")

        return ChatResponse(
            reply=clarification_text,
            session_id=session_id,
            timestamp=formatted_time,
        )

    # 2. Read and validate Gemini API Key
    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not gemini_api_key:
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY is missing. Please define your GEMINI_API_KEY in the backend/.env file.",
        )

    # 3. Read Gemini Model (default: gemini-3.5-flash-lite)
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip() or "gemini-3.5-flash-lite"

    # 4. Build Gemini contents payload with RAG retrieval
    contents_payload = []
    doc_sections = []

    for doc in resolved_documents:
        doc_name = doc["name"]
        doc_type = doc["type"]
        raw_text = doc["text"]

        if raw_text and raw_text.strip():
            # Apply RAG retrieval to pull the most relevant excerpts
            context_text, is_filtered = retrieve_relevant_context(
                document_text=raw_text,
                user_query=user_message,
                max_context_chars=3500,
                top_k=4,
            )
            mode_tag = "Relevant Excerpts via RAG" if is_filtered else "Complete Document"
            header = f"=== Attached Document: {doc_name} (Format: {doc_type}, {mode_tag}) ==="
            doc_sections.append(f"{header}\n{context_text}\n=== End of {doc_name} ===")
        else:
            header = f"=== Attached Document: {doc_name} (Format: {doc_type}) ==="
            doc_sections.append(f"{header}\n[Document content was empty or unextractable]\n=== End of {doc_name} ===")

    prompt_parts = []
    if doc_sections:
        prompt_parts.append(
            "The user has attached the following document context extracted via Document Intelligence:\n\n"
            + "\n\n".join(doc_sections)
        )

    if user_message:
        prompt_parts.append(f"User Request: {user_message}")
    elif resolved_documents and not request.images:
        prompt_parts.append("User Request: Please analyze the attached document(s) and provide a concise summary, key points, and useful insights.")
    elif request.images and not resolved_documents:
        prompt_parts.append("User Request: Please describe and analyze the attached image(s) in detail.")
    else:
        prompt_parts.append("User Request: Please analyze the attached files and provide a detailed summary.")

    if is_pdf_requested:
        prompt_parts.append(
            "\n[Instruction: The user has requested a downloadable PDF document. Structure the response professionally with a title, markdown headings (##, ###), bullet points, and data tables where applicable so it can be formatted cleanly into a PDF document.]"
        )

    contents_payload.append("\n\n".join(prompt_parts))

    if request.images:
        for img in request.images:
            try:
                raw_b64 = img.base64_data
                if "," in raw_b64:
                    raw_b64 = raw_b64.split(",", 1)[1]
                img_bytes = base64.b64decode(raw_b64)
                contents_payload.append(genai_types.Part.from_bytes(data=img_bytes, mime_type=img.mime_type))
            except Exception as b64_err:
                contents_payload.append(f"[Note: Image {img.name} could not be processed: {str(b64_err)}]")

    gemini_contents = contents_payload if (has_docs or has_images) else user_message

    # Module 5: Load user's saved preferences for personalization
    pref_record = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
    pref_style = pref_record.response_style if pref_record else "balanced"
    pref_lang = pref_record.response_language if pref_record else "English"
    pref_custom = pref_record.custom_instructions if pref_record else None

    # Comprehensive system instruction removing text-only disclaimers, enforcing grounding, and applying user preferences
    system_instruction = build_aethermind_system_prompt(
        has_docs=has_docs,
        response_style=pref_style,
        response_language=pref_lang,
        custom_instructions=pref_custom,
    )

    # 5. Generate response with Google Gemini
    try:
        client = genai.Client(api_key=gemini_api_key)
        try:
            response = client.models.generate_content(
                model=gemini_model,
                contents=gemini_contents,
                config=genai_types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.7,
                ),
            )
        except genai_errors.APIError as api_err:
            # If primary model is experiencing high demand (503), automatically fallback to gemini-3.8-flash
            if api_err.code == 503 and gemini_model != "gemini-3.8-flash":
                response = client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=gemini_contents,
                    config=genai_types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.7,
                    ),
                )
            else:
                raise api_err

        reply_text = response.text
        if not reply_text:
            raise HTTPException(
                status_code=502,
                detail="The Gemini model returned an empty response. Please try rephrasing your message.",
            )

    except HTTPException:
        raise
    except genai_errors.APIError as e:
        err_msg = str(e)
        if gemini_api_key and gemini_api_key in err_msg:
            err_msg = err_msg.replace(gemini_api_key, "[REDACTED]")
        # Requirement 10: If Gemini quota is exceeded, return clean 429 without crashing
        if e.code == 429 or "RESOURCE_EXHAUSTED" in err_msg or "quota" in err_msg.lower():
            raise HTTPException(
                status_code=429,
                detail="Google Gemini API rate limit or quota exceeded. Please wait a moment before sending another message, or check your API quota at https://ai.google.dev.",
            )
        raise HTTPException(
            status_code=502,
            detail=f"Google Gemini API error ({e.code}): {err_msg}",
        )
    except Exception as e:
        err_msg = str(e)
        if gemini_api_key and gemini_api_key in err_msg:
            err_msg = err_msg.replace(gemini_api_key, "[REDACTED]")
        raise HTTPException(
            status_code=502,
            detail=f"Failed to communicate with Gemini API: {err_msg}",
        )

    # 5b. Generate real PDF if requested (Requirements 2 & 8)
    if is_pdf_requested:
        try:
            if resolved_documents:
                doc_title = resolved_documents[0]["name"].rsplit(".", 1)[0].replace("_", " ").title()
                doc_subtitle = f"Source Document: {resolved_documents[0]['name']}"
            else:
                clean_q = re.sub(
                    r"(?i)\b(generate|create|make|provide|export|download|as|a|the|pdf|report|of|for|please)\b",
                    "",
                    user_message,
                ).strip()
                doc_title = clean_q.title() if clean_q else "AetherMind Document Report"
                doc_subtitle = "Generated via AetherMind AI Chat"

            pdf_info = generate_pdf_document(
                title=doc_title,
                content=reply_text,
                author="AetherMind Document Intelligence",
                subtitle=doc_subtitle,
            )

            size_str = (
                f"{pdf_info['file_size'] / 1024:.1f} KB"
                if pdf_info['file_size'] >= 1024
                else f"{pdf_info['file_size']} B"
            )
            pdf_link_block = (
                f"\n\n---\n"
                f"### 📄 Downloadable PDF Generated\n"
                f"Your requested PDF document has been created and is ready for download:\n\n"
                f"- **Document:** [{pdf_info['filename']}]({pdf_info['download_url']})\n"
                f"- **File Size:** {size_str}\n"
                f"- **Engine:** ReportLab PDF Engine\n\n"
                f"[📥 Download {pdf_info['filename']}]({pdf_info['download_url']})"
            )
            reply_text += pdf_link_block
        except Exception as pdf_gen_err:
            print(f"[Warning] PDF generation failed: {pdf_gen_err}")
            reply_text += f"\n\n*(Note: PDF file generation encountered an issue: {sanitize_error_message(pdf_gen_err)}. The complete content is displayed above.)*"

    # 6. Save user message and Gemini reply to PostgreSQL
    try:
        conversation = (
            db.query(Conversation).filter(Conversation.session_id == session_id).first()
        )
        if not conversation:
            session_title = (
                display_message[:30] + "..." if len(display_message) > 30 else display_message
            )
            conversation = Conversation(
                session_id=session_id,
                title=session_title,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(conversation)
            db.flush()
        else:
            conversation.updated_at = datetime.utcnow()

        # Save user message
        user_record = Message(
            conversation_id=conversation.id,
            role="user",
            content=display_message,
            timestamp=formatted_time,
            created_at=datetime.utcnow(),
        )
        db.add(user_record)

        # Save assistant message
        assistant_record = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=reply_text,
            timestamp=formatted_time,
            created_at=datetime.utcnow(),
        )
        db.add(assistant_record)

        db.commit()

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail=(
                f"Failed to persist chat messages to PostgreSQL: {sanitize_error_message(e)}. "
                "The response was generated, but could not be saved to the database."
            ),
        )

    return ChatResponse(
        reply=reply_text,
        session_id=session_id,
        timestamp=formatted_time,
    )


@app.get(
    "/api/conversations/search",
    response_model=SearchResponse,
    summary="Search conversations and messages",
    description="Searches saved conversation titles and message contents in PostgreSQL.",
)
def search_conversations(
    q: str = "",
    db: Session = Depends(get_db),
):
    """
    Module 5: Chat and message search
    - Searches saved conversation titles and message contents in PostgreSQL.
    - Returns matching conversation titles, session IDs, and surrounding message snippets.
    - Handles empty queries, no results, and database errors safely.
    """
    clean_q = (q or "").strip()
    if not clean_q:
        return SearchResponse(query="", total_matches=0, results=[])

    search_pattern = f"%{clean_q}%"
    results: List[SearchMatchItem] = []

    try:
        # 1. Search in conversation titles
        title_matches = (
            db.query(Conversation)
            .filter(Conversation.title.ilike(search_pattern))
            .order_by(Conversation.updated_at.desc())
            .limit(15)
            .all()
        )
        for conv in title_matches:
            snippet_text = conv.title or "Untitled Conversation"
            results.append(
                SearchMatchItem(
                    conversation_id=conv.id,
                    session_id=conv.session_id,
                    conversation_title=conv.title or "Untitled Conversation",
                    updated_at=conv.updated_at.isoformat() if conv.updated_at else None,
                    matched_in="title",
                    snippet=snippet_text,
                    role=None,
                    timestamp=None,
                )
            )

        # 2. Search in message contents
        message_matches = (
            db.query(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .filter(Message.content.ilike(search_pattern))
            .order_by(Message.created_at.desc())
            .limit(30)
            .all()
        )

        for msg in message_matches:
            conv = msg.conversation
            if not conv:
                continue

            content = msg.content
            lower_content = content.lower()
            lower_q = clean_q.lower()
            match_idx = lower_content.find(lower_q)

            if match_idx != -1:
                start = max(0, match_idx - 40)
                end = min(len(content), match_idx + len(clean_q) + 60)
                prefix = "..." if start > 0 else ""
                suffix = "..." if end < len(content) else ""
                snippet = f"{prefix}{content[start:end].strip()}{suffix}"
            else:
                snippet = content[:100] + ("..." if len(content) > 100 else "")

            results.append(
                SearchMatchItem(
                    conversation_id=conv.id,
                    session_id=conv.session_id,
                    conversation_title=conv.title or "Untitled Conversation",
                    updated_at=conv.updated_at.isoformat() if conv.updated_at else None,
                    matched_in="message",
                    snippet=snippet,
                    role=msg.role,
                    timestamp=msg.timestamp,
                )
            )

        return SearchResponse(
            query=clean_q,
            total_matches=len(results),
            results=results,
        )
    except Exception as e:
        safe_err = sanitize_error_message(e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to execute search: {safe_err}",
        )


@app.get(
    "/api/conversations/{session_id}/messages",
    response_model=ConversationMessagesResponse,
)
@app.get(
    "/api/conversations/{session_id}",
    response_model=ConversationMessagesResponse,
)
@app.get(
    "/api/chat/messages/{session_id}",
    response_model=ConversationMessagesResponse,
    include_in_schema=False,
)
def get_conversation_messages(session_id: str, db: Session = Depends(get_db)):
    """
    Retrieve stored messages for a conversation session from PostgreSQL.
    Matches Requirement 7: Add an API endpoint to retrieve messages for a conversation using its session ID.
    """
    conversation = (
        db.query(Conversation).filter(Conversation.session_id == session_id).first()
    )
    if not conversation:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation with session_id '{session_id}' not found in database.",
        )

    formatted_messages = [
        MessageItemResponse(
            id=msg.id,
            role=msg.role,
            sender=msg.role,
            content=msg.content,
            timestamp=msg.timestamp,
        )
        for msg in conversation.messages
    ]

    return ConversationMessagesResponse(
        session_id=conversation.session_id,
        title=conversation.title,
        created_at=conversation.created_at.isoformat() if conversation.created_at else None,
        updated_at=conversation.updated_at.isoformat() if conversation.updated_at else None,
        messages=formatted_messages,
    )


@app.get(
    "/api/conversations",
    response_model=List[ConversationSummaryResponse],
)
def list_conversations(db: Session = Depends(get_db)):
    """List all saved conversations ordered by latest update."""
    conversations = (
        db.query(Conversation).order_by(Conversation.updated_at.desc()).all()
    )
    return [
        ConversationSummaryResponse(
            id=conv.id,
            session_id=conv.session_id,
            title=conv.title,
            created_at=conv.created_at.isoformat() if conv.created_at else None,
            updated_at=conv.updated_at.isoformat() if conv.updated_at else None,
            message_count=len(conv.messages),
        )
        for conv in conversations
    ]


@app.delete("/api/conversations/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(session_id: str, db: Session = Depends(get_db)):
    """Delete a conversation and its messages from PostgreSQL."""
    conversation = (
        db.query(Conversation).filter(Conversation.session_id == session_id).first()
    )
    if not conversation:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation with session_id '{session_id}' not found.",
        )
    db.delete(conversation)
    db.commit()
    return None


@app.get("/api/preferences", response_model=UserPreferenceResponse)
def get_user_preferences(
    x_user_id: Optional[str] = Header(default="default_user", alias="X-User-ID"),
    db: Session = Depends(get_db),
):
    """
    Module 5: Retrieve saved user preferences from PostgreSQL.
    If none exist yet, automatically initializes and returns default preferences.
    """
    user_id = x_user_id or "default_user"
    pref = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
    if not pref:
        pref = UserPreference(
            user_id=user_id,
            response_style="balanced",
            response_language="English",
            custom_instructions=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        try:
            db.add(pref)
            db.commit()
            db.refresh(pref)
        except Exception as db_err:
            db.rollback()
            print(f"[Warning] Failed to initialize default preferences: {sanitize_error_message(db_err)}")

    return UserPreferenceResponse(
        user_id=pref.user_id,
        response_style=pref.response_style,
        response_language=pref.response_language,
        custom_instructions=pref.custom_instructions,
        created_at=pref.created_at.isoformat() if pref.created_at else None,
        updated_at=pref.updated_at.isoformat() if pref.updated_at else None,
    )


@app.put("/api/preferences", response_model=UserPreferenceResponse)
def update_user_preferences(
    payload: UserPreferenceUpdate,
    x_user_id: Optional[str] = Header(default="default_user", alias="X-User-ID"),
    db: Session = Depends(get_db),
):
    """
    Module 5: Upsert user preferences in PostgreSQL.
    Validates response_style (concise, balanced, detailed) and language.
    """
    user_id = x_user_id or "default_user"
    pref = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()

    if not pref:
        pref = UserPreference(
            user_id=user_id,
            response_style=payload.response_style,
            response_language=payload.response_language,
            custom_instructions=payload.custom_instructions,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(pref)
    else:
        pref.response_style = payload.response_style
        pref.response_language = payload.response_language
        pref.custom_instructions = payload.custom_instructions
        pref.updated_at = datetime.utcnow()

    try:
        db.commit()
        db.refresh(pref)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save preferences: {sanitize_error_message(e)}",
        )

    return UserPreferenceResponse(
        user_id=pref.user_id,
        response_style=pref.response_style,
        response_language=pref.response_language,
        custom_instructions=pref.custom_instructions,
        created_at=pref.created_at.isoformat() if pref.created_at else None,
        updated_at=pref.updated_at.isoformat() if pref.updated_at else None,
    )


@app.get("/api/documents/info")
def get_documents_info():
    """
    Returns supported document formats, size limits, and text extraction capabilities.
    """
    return {
        "status": "ready",
        "supported_formats": [
            {"extension": ".pdf", "name": "PDF Document", "library": "PyMuPDF"},
            {"extension": ".docx", "name": "Word Document", "library": "python-docx"},
            {"extension": ".txt", "name": "Plain Text", "library": "Standard Unicode"},
            {"extension": ".csv", "name": "CSV Spreadsheet", "library": "pandas"},
        ],
        "max_size_bytes": MAX_FILE_SIZE_BYTES,
        "max_size_mb": MAX_FILE_SIZE_BYTES // (1024 * 1024),
    }


@app.post(
    "/api/documents/upload",
    response_model=DocumentUploadResponse,
    summary="Upload and extract text from document",
    description="Uploads a PDF, DOCX, TXT, or CSV file, extracts text, and stores document in PostgreSQL.",
)
async def upload_document(
    file: UploadFile = File(..., description="Document file to extract text from"),
    x_user_id: Optional[str] = Header(default="default_user", alias="X-User-ID"),
    db: Session = Depends(get_db),
):
    """
    Module 2: Document Intelligence
    1. Validates file presence, filename, extension, and file size.
    2. Extracts clean text using PyMuPDF (PDF), python-docx (DOCX), Unicode (TXT), or pandas (CSV).
    3. Persists document metadata, extracted text, and user ownership in PostgreSQL.
    4. Handles empty, corrupt, or unsupported files with descriptive error messages.
    5. Never calls Gemini or touches external credentials.
    """
    if not file or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file was provided in the upload request.",
        )

    filename = file.filename.strip()

    try:
        content_bytes = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to read uploaded file: {str(e)}",
        )

    try:
        result = parse_document(filename=filename, file_bytes=content_bytes)

        # Generate persistent document ID
        doc_id = f"doc-{int(datetime.utcnow().timestamp() * 1000)}-{uuid.uuid4().hex[:6]}"
        user_id = x_user_id or "default_user"
        formatted_upload_time = datetime.now().strftime("%I:%M %p").lstrip("0")

        # Persist to PostgreSQL documents table
        try:
            doc_record = Document(
                id=doc_id,
                filename=result["filename"],
                file_type=result["file_type"],
                file_size=result["file_size"],
                extracted_text=result["extracted_text"],
                doc_metadata=result["metadata"],
                user_id=user_id,
                created_at=datetime.utcnow(),
            )
            db.add(doc_record)
            db.commit()
        except Exception as db_err:
            db.rollback()
            print(f"[Warning] Failed to persist document to database: {sanitize_error_message(db_err)}")

        return DocumentUploadResponse(
            status="success",
            id=doc_id,
            filename=result["filename"],
            file_type=result["file_type"],
            file_size=result["file_size"],
            extracted_text=result["extracted_text"],
            metadata=result["metadata"],
            uploaded_at=formatted_upload_time,
        )
    except DocumentParsingError as dpe:
        raise HTTPException(status_code=dpe.status_code, detail=dpe.message)
    except Exception as e:
        clean_err = sanitize_error_message(str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing document '{filename}': {clean_err}",
        )


@app.get(
    "/api/documents",
    response_model=List[DocumentItemResponse],
    summary="List uploaded documents for authorized user",
)
def list_documents(
    x_user_id: Optional[str] = Header(default="default_user", alias="X-User-ID"),
    db: Session = Depends(get_db),
):
    """
    List all documents uploaded by the authorized user.
    Enforces user isolation (Requirement 11).
    """
    user_id = x_user_id or "default_user"
    docs = (
        db.query(Document)
        .filter(Document.user_id == user_id)
        .order_by(Document.created_at.desc())
        .all()
    )
    return [
        DocumentItemResponse(
            id=d.id,
            filename=d.filename,
            file_type=d.file_type,
            file_size=d.file_size,
            extracted_text=d.extracted_text[:600] if d.extracted_text else "",
            metadata=d.doc_metadata or {},
            uploaded_at=d.created_at.strftime("%I:%M %p").lstrip("0"),
        )
        for d in docs
    ]


@app.get(
    "/api/documents/{document_id}",
    response_model=DocumentItemResponse,
    summary="Get single document by ID",
)
def get_document(
    document_id: str,
    x_user_id: Optional[str] = Header(default="default_user", alias="X-User-ID"),
    db: Session = Depends(get_db),
):
    """
    Retrieve full document content and metadata by ID.
    Enforces user ownership check (Requirement 11).
    """
    user_id = x_user_id or "default_user"
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == user_id)
        .first()
    )
    if not doc:
        raise HTTPException(
            status_code=404,
            detail=f"Document '{document_id}' not found or access unauthorized.",
        )
    return DocumentItemResponse(
        id=doc.id,
        filename=doc.filename,
        file_type=doc.file_type,
        file_size=doc.file_size,
        extracted_text=doc.extracted_text,
        metadata=doc.doc_metadata or {},
        uploaded_at=doc.created_at.strftime("%I:%M %p").lstrip("0"),
    )


@app.delete(
    "/api/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete document by ID",
)
def delete_document(
    document_id: str,
    x_user_id: Optional[str] = Header(default="default_user", alias="X-User-ID"),
    db: Session = Depends(get_db),
):
    """
    Delete document from PostgreSQL by ID for the authorized user.
    """
    user_id = x_user_id or "default_user"
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == user_id)
        .first()
    )
    if not doc:
        raise HTTPException(
            status_code=404,
            detail=f"Document '{document_id}' not found or access unauthorized.",
        )
    db.delete(doc)
    db.commit()
    return None


@app.post(
    "/api/documents/{document_id}/summarize",
    response_model=DocumentSummaryResponse,
    summary="Generate document summary and extract key information",
)
def summarize_document_endpoint(
    document_id: str,
    x_user_id: Optional[str] = Header(default="default_user", alias="X-User-ID"),
    db: Session = Depends(get_db),
):
    """
    Requirement 7: Add document summarization and key-information extraction.
    1. Retrieves document from PostgreSQL.
    2. Invokes Google Gemini with structured extraction prompt.
    3. Extracts summary, key points, key entities, and key metrics.
    4. Handles Gemini quota errors gracefully.
    """
    import json

    user_id = x_user_id or "default_user"
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == user_id)
        .first()
    )
    if not doc:
        raise HTTPException(
            status_code=404,
            detail=f"Document '{document_id}' not found or access unauthorized.",
        )

    if not doc.extracted_text or not doc.extracted_text.strip():
        raise HTTPException(
            status_code=400,
            detail=f"Document '{doc.filename}' contains no readable text to summarize.",
        )

    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not gemini_api_key:
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY is not configured.",
        )

    gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip() or "gemini-3.5-flash-lite"

    doc_text_sample = doc.extracted_text[:8000]

    prompt = (
        f"You are AetherMind's Document Intelligence Analyst. Analyze the following document content and extract structured insights.\n\n"
        f"Document: {doc.filename} (Format: {doc.file_type})\n\n"
        f"--- Document Content ---\n{doc_text_sample}\n--- End Content ---\n\n"
        f"Respond in valid JSON format with exactly the following keys:\n"
        f"{{\n"
        f"  \"summary\": \"A concise 2-3 sentence executive summary of the document.\",\n"
        f"  \"key_points\": [\"3-5 major takeaways or key findings from the document\"],\n"
        f"  \"key_entities\": [\"Key people, organizations, subjects, or topics mentioned\"],\n"
        f"  \"metrics\": [\"Key numbers, statistics, scores, dates, or measurements found\"]\n"
        f"}}"
    )

    try:
        client = genai.Client(api_key=gemini_api_key)
        try:
            response = client.models.generate_content(
                model=gemini_model,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
        except genai_errors.APIError as api_err:
            if api_err.code == 503 and gemini_model != "gemini-3.8-flash":
                response = client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.2,
                    ),
                )
            else:
                raise api_err

        raw_text = response.text.strip()
        parsed = json.loads(raw_text)

        return DocumentSummaryResponse(
            document_id=doc.id,
            filename=doc.filename,
            summary=parsed.get("summary", "Summary extracted successfully."),
            key_points=parsed.get("key_points", []),
            key_entities=parsed.get("key_entities", []),
            metrics=parsed.get("metrics", []),
        )

    except genai_errors.APIError as e:
        err_msg = str(e)
        if e.code == 429 or "RESOURCE_EXHAUSTED" in err_msg or "quota" in err_msg.lower():
            raise HTTPException(
                status_code=429,
                detail="Gemini API rate limit or quota exceeded while generating summary. Please wait a moment and try again.",
            )
        raise HTTPException(status_code=502, detail=f"Gemini API error: {err_msg}")
    except Exception as e:
        # Fallback to extractive overview if JSON parsing or response had issues
        lines = [l.strip() for l in doc.extracted_text.splitlines() if l.strip()][:5]
        return DocumentSummaryResponse(
            document_id=doc.id,
            filename=doc.filename,
            summary=f"Overview of {doc.filename}: Document contains {len(doc.extracted_text.split())} words in {doc.file_type.upper()} format.",
            key_points=lines if lines else ["Document ingested successfully."],
            key_entities=[doc.filename, doc.file_type.upper()],
            metrics=[f"{len(doc.extracted_text)} characters", f"{len(doc.extracted_text.split())} words"],
        )


# ==============================================================================
# PDF Generation & Download Endpoints (Requirement 2 & 8)
# ==============================================================================

@app.get("/api/pdf/download/{pdf_id}", summary="Download generated PDF file")
def download_pdf_endpoint(pdf_id: str):
    """
    Requirements 2 & 8: Download a real PDF generated via ReportLab.
    Returns the physical PDF file with application/pdf media type.
    """
    pdf_info = get_generated_pdf(pdf_id)
    if not pdf_info or not os.path.exists(pdf_info["file_path"]):
        raise HTTPException(
            status_code=404,
            detail=f"Generated PDF with ID '{pdf_id}' was not found or has expired.",
        )
    return FileResponse(
        path=pdf_info["file_path"],
        media_type="application/pdf",
        filename=pdf_info["filename"],
    )


@app.post("/api/pdf/generate", response_model=PDFGenerateResponse, summary="Generate downloadable PDF from text content")
def generate_pdf_endpoint(req: PDFGenerateRequest):
    """
    Requirement 2: Generate a real downloadable PDF from requested content using ReportLab.
    """
    if not req.content or not req.content.strip():
        raise HTTPException(status_code=400, detail="Content cannot be empty for PDF generation.")
    try:
        result = generate_pdf_document(
            title=req.title,
            content=req.content,
            filename=req.filename,
            subtitle=req.subtitle,
        )
        return PDFGenerateResponse(
            status="success",
            pdf_id=result["pdf_id"],
            filename=result["filename"],
            file_size=result["file_size"],
            title=result["title"],
            download_url=result["download_url"],
            created_at=result["created_at"],
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate PDF document: {sanitize_error_message(e)}",
        )


@app.post("/api/documents/{document_id}/export-pdf", response_model=PDFGenerateResponse, summary="Export uploaded document to formatted PDF")
def export_document_pdf(
    document_id: str,
    x_user_id: Optional[str] = Header(default="default_user", alias="X-User-ID"),
    db: Session = Depends(get_db),
):
    """
    Generate and download a real PDF export of any document in the Document library.
    """
    user_id = x_user_id or "default_user"
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == user_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found.")
    if not doc.extracted_text or not doc.extracted_text.strip():
        raise HTTPException(status_code=400, detail="Document contains no text to export.")

    base_name = doc.filename.rsplit(".", 1)[0]
    try:
        result = generate_pdf_document(
            title=f"Document Export: {doc.filename}",
            content=doc.extracted_text,
            filename=f"{base_name}_export.pdf",
            author="AetherMind Document Intelligence",
            subtitle=f"Original Format: {doc.file_type.upper()} • Ingested: {doc.created_at.strftime('%Y-%m-%d %H:%M')}",
        )
        return PDFGenerateResponse(
            status="success",
            pdf_id=result["pdf_id"],
            filename=result["filename"],
            file_size=result["file_size"],
            title=result["title"],
            download_url=result["download_url"],
            created_at=result["created_at"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export document to PDF: {sanitize_error_message(e)}")


@app.post("/api/test/persistence")
def test_persistence_endpoint(db: Session = Depends(get_db)):
    """
    Safe test endpoint to verify database message persistence independently of Gemini API.
    Inserts a test conversation with both a user message and a clearly marked mock assistant reply,
    commits to PostgreSQL, and retrieves them.
    Does not delete existing data or invoke Gemini API.
    """
    timestamp_id = int(datetime.utcnow().timestamp() * 1000)
    session_id = f"test-persist-{timestamp_id}"
    formatted_time = datetime.now().strftime("%I:%M %p").lstrip("0")

    user_text = "Test user message: Testing PostgreSQL persistence independently of Gemini."
    assistant_text = "[TEST_MOCK_REPLY] Verified assistant response persisted to PostgreSQL without calling Gemini API."

    # 1. Create conversation record
    conversation = Conversation(
        session_id=session_id,
        title="Diagnostic Persistence Test",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(conversation)
    db.flush()

    # 2. Add user message
    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=user_text,
        timestamp=formatted_time,
        created_at=datetime.utcnow(),
    )
    db.add(user_msg)

    # 3. Add assistant message (clearly marked test reply)
    assistant_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=assistant_text,
        timestamp=formatted_time,
        created_at=datetime.utcnow(),
    )
    db.add(assistant_msg)

    # Commit records
    db.commit()

    # 4. Retrieve back from database
    retrieved = (
        db.query(Conversation).filter(Conversation.session_id == session_id).first()
    )

    return {
        "status": "success",
        "description": "Database persistence verified independently of Gemini API",
        "session_id": retrieved.session_id,
        "conversation_id": retrieved.id,
        "title": retrieved.title,
        "messages_persisted": len(retrieved.messages),
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "timestamp": m.timestamp,
            }
            for m in retrieved.messages
        ],
    }

