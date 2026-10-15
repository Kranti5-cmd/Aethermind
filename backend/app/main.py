import os
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, status
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
from app.models import Conversation, Message
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    MessageItemResponse,
    ConversationMessagesResponse,
    ConversationSummaryResponse,
)


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


@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest, db: Session = Depends(get_db)):
    """
    POST /api/chat endpoint.
    1. Validates the incoming message.
    2. Generates genuine response using official Google Gen AI SDK (Gemini).
    3. Persists both the user message and the Gemini response to PostgreSQL.
    4. Returns clear errors if Gemini or PostgreSQL operations fail.
    """
    user_message = request.message.strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    session_id = request.session_id or f"session-{int(datetime.now().timestamp() * 1000)}"
    formatted_time = datetime.now().strftime("%I:%M %p").lstrip("0")

    # 1. Read and validate Gemini API Key
    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not gemini_api_key:
        raise HTTPException(
            status_code=500,
            detail="GEMINI_API_KEY is missing. Please define your GEMINI_API_KEY in the backend/.env file.",
        )

    # 2. Read Gemini Model (default: gemini-3.5-flash)
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash").strip() or "gemini-3.5-flash"

    # 3. Generate response with Google Gemini
    try:
        client = genai.Client(api_key=gemini_api_key)
        try:
            response = client.models.generate_content(
                model=gemini_model,
                contents=user_message,
                config=genai_types.GenerateContentConfig(
                    system_instruction=(
                        "You are AetherMind, an intelligent AI knowledge assistant and personal "
                        "conversation partner. Provide clear, accurate, and structured responses."
                    ),
                    temperature=0.7,
                ),
            )
        except genai_errors.APIError as api_err:
            # If primary model is experiencing high demand (503), automatically fallback to gemini-3.5-flash-lite
            if api_err.code == 503 and gemini_model != "gemini-3.5-flash-lite":
                response = client.models.generate_content(
                    model="gemini-3.5-flash-lite",
                    contents=user_message,
                    config=genai_types.GenerateContentConfig(
                        system_instruction=(
                            "You are AetherMind, an intelligent AI knowledge assistant and personal "
                            "conversation partner. Provide clear, accurate, and structured responses."
                        ),
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

    # 4. Save user message and Gemini reply to PostgreSQL
    try:
        conversation = (
            db.query(Conversation).filter(Conversation.session_id == session_id).first()
        )
        if not conversation:
            session_title = (
                user_message[:30] + "..." if len(user_message) > 30 else user_message
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
            content=user_message,
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
    "/api/conversations/{session_id}/messages",
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

