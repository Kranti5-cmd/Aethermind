import re
import math
from typing import List, Dict, Any, Tuple, Set, Optional

# Common English stop words to filter out during keyword scoring
STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "aren't", "as", "at", "be", "because", "been", "before", "being", "below", "between", "both",
    "but", "by", "can", "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does",
    "doesn't", "doing", "don't", "down", "during", "each", "few", "for", "from", "further", "had",
    "hadn't", "has", "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her",
    "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i", "i'd",
    "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself",
    "let's", "me", "more", "most", "mustn't", "my", "myself", "no", "nor", "not", "of", "off",
    "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over",
    "own", "same", "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so",
    "some", "such", "than", "that", "that's", "the", "their", "theirs", "them", "themselves",
    "then", "there", "there's", "these", "they", "they'd", "they'll", "they're", "they've",
    "this", "those", "through", "to", "too", "under", "until", "up", "very", "was", "wasn't",
    "we", "we'd", "we'll", "we're", "we've", "were", "weren't", "what", "what's", "when",
    "when's", "where", "where's", "which", "while", "who", "who's", "whom", "why", "why's",
    "with", "won't", "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your",
    "yours", "yourself", "yourselves"
}

SUMMARY_INDICATORS = {
    "summarize", "summary", "overview", "brief", "explain", "describe", "outline",
    "what is", "what are", "main points", "key points", "tell me about", "gist", "all"
}


def tokenize(text: str) -> List[str]:
    """Tokenize alphanumeric words in lowercase."""
    return [w.lower() for w in re.findall(r"\b[a-zA-Z0-9_\-\.]{2,}\b", text)]


def is_summary_query(query: str) -> bool:
    """Check if the user inquiry is asking for a general overview or summary."""
    q_lower = query.lower()
    return any(ind in q_lower for ind in SUMMARY_INDICATORS)


def chunk_document(text: str, chunk_size: int = 700, overlap: int = 150) -> List[Dict[str, Any]]:
    """
    Split document text into structured chunks respecting natural paragraph and line boundaries.
    """
    if not text or not text.strip():
        return []

    # If small enough, return as single chunk
    if len(text) <= chunk_size:
        return [{"index": 0, "text": text.strip(), "char_count": len(text)}]

    # Split by paragraphs or double newlines first
    paragraphs = re.split(r"\n{2,}", text)
    chunks = []
    current_chunk = []
    current_len = 0

    for para in paragraphs:
        para_clean = para.strip()
        if not para_clean:
            continue

        # If a single paragraph is larger than chunk_size, split by sentences or newlines
        if len(para_clean) > chunk_size:
            lines = re.split(r"(?<=[.!?])\s+|\n+", para_clean)
            for line in lines:
                line_clean = line.strip()
                if not line_clean:
                    continue
                if current_len + len(line_clean) > chunk_size and current_chunk:
                    chunk_str = "\n".join(current_chunk)
                    chunks.append({
                        "index": len(chunks),
                        "text": chunk_str,
                        "char_count": len(chunk_str),
                    })
                    # Keep tail of current chunk for overlap
                    overlap_tokens = chunk_str[-overlap:] if len(chunk_str) > overlap else ""
                    current_chunk = [overlap_tokens] if overlap_tokens else []
                    current_len = len(overlap_tokens)

                current_chunk.append(line_clean)
                current_len += len(line_clean) + 1
        else:
            if current_len + len(para_clean) > chunk_size and current_chunk:
                chunk_str = "\n\n".join(current_chunk)
                chunks.append({
                    "index": len(chunks),
                    "text": chunk_str,
                    "char_count": len(chunk_str),
                })
                overlap_text = chunk_str[-overlap:] if len(chunk_str) > overlap else ""
                current_chunk = [overlap_text] if overlap_text else []
                current_len = len(overlap_text)

            current_chunk.append(para_clean)
            current_len += len(para_clean) + 2

    if current_chunk:
        chunk_str = "\n\n".join(current_chunk).strip()
        if chunk_str:
            chunks.append({
                "index": len(chunks),
                "text": chunk_str,
                "char_count": len(chunk_str),
            })

    return chunks


def score_chunk_relevance(chunk: Dict[str, Any], query_terms: Set[str], is_summary: bool) -> float:
    """
    Compute BM25-inspired keyword overlap and term density relevance score.
    """
    chunk_text = chunk["text"]
    chunk_tokens = tokenize(chunk_text)
    if not chunk_tokens:
        return 0.0

    chunk_token_set = set(chunk_tokens)
    score = 0.0

    # Summary query boost: prioritize opening section and closing summary sections
    if is_summary:
        if chunk["index"] == 0:
            score += 4.0
        elif chunk["index"] == 1:
            score += 2.0

    # Keyword match scoring
    matched_terms = 0
    for term in query_terms:
        if term in chunk_token_set:
            matched_terms += 1
            # Term frequency weighting
            count = chunk_tokens.count(term)
            tf = count / len(chunk_tokens)
            score += (1.0 + math.log(1.0 + count)) * (1.0 + tf * 10.0)

    # Coordinated bonus for matching multiple distinct query keywords
    if matched_terms > 1:
        score *= (1.0 + 0.35 * matched_terms)

    return score


def retrieve_relevant_context(
    document_text: str,
    user_query: str,
    max_context_chars: int = 3500,
    top_k: int = 4
) -> Tuple[str, bool]:
    """
    Extract the most relevant document chunks for the user's query using RAG.
    If document is short (< max_context_chars), returns complete text.
    For longer documents, returns top-K ranked chunks ordered by document flow.
    Returns (context_text, is_rag_filtered).
    """
    cleaned_text = (document_text or "").strip()
    if not cleaned_text:
        return "", False

    # Short documents fit directly in context
    if len(cleaned_text) <= max_context_chars:
        return cleaned_text, False

    # Chunk the document
    chunks = chunk_document(cleaned_text, chunk_size=750, overlap=120)
    if not chunks:
        return cleaned_text[:max_context_chars], True

    # Tokenize query and remove stop words
    query_tokens = [w for w in tokenize(user_query) if w not in STOP_WORDS]
    is_summary = is_summary_query(user_query) or len(query_tokens) == 0

    # Score each chunk
    scored_chunks = []
    for c in chunks:
        s = score_chunk_relevance(c, set(query_tokens), is_summary=is_summary)
        scored_chunks.append((s, c))

    # Sort descending by relevance score
    scored_chunks.sort(key=lambda x: x[0], reverse=True)

    # Select top K chunks
    selected = scored_chunks[:top_k]

    # Re-order selected chunks by original document position (index)
    selected.sort(key=lambda x: x[1]["index"])

    # Combine into readable excerpts
    formatted_parts = []
    accumulated_len = 0

    for score, chunk in selected:
        part = f"[Excerpt Section {chunk['index'] + 1}]:\n{chunk['text']}"
        if accumulated_len + len(part) > max_context_chars and formatted_parts:
            break
        formatted_parts.append(part)
        accumulated_len += len(part)

    rag_context = "\n\n---\n\n".join(formatted_parts)
    return rag_context, True


def build_aethermind_system_prompt(
    has_docs: bool = False,
    response_style: str = "balanced",
    response_language: str = "English",
    custom_instructions: Optional[str] = None,
) -> str:
    """
    Returns the comprehensive system prompt for AetherMind.
    Accurately informs the model about its real Document Intelligence,
    upload processing, and ReportLab PDF generation capabilities,
    and removes misleading generic text-only AI disclaimers (Requirement 1).
    Module 5: Integrates personalized response style, language, and custom instructions.
    """
    base_instructions = (
        "You are AetherMind, an advanced AI Knowledge and Document Intelligence Assistant.\n"
        "Your environment includes built-in document processing and real file generation capabilities:\n"
        "1. Document Intelligence: Users can upload, parse, and analyze PDF, Word (.docx), plain text (.txt), and CSV documents. "
        "Files are processed securely on the backend using PyMuPDF, python-docx, and pandas.\n"
        "2. Document Library & Attachments: Users can view uploaded documents on the Documents page, or attach existing files and upload new ones using the '+' button in chat.\n"
        "3. Real PDF Generation: You are connected to a real ReportLab PDF generation engine on the backend. "
        "When users ask you to create, generate, or export a PDF, real downloadable PDF files are generated.\n"
        "CRITICAL BEHAVIORAL RULES:\n"
        "- NEVER state: 'I cannot generate, create, upload, or attach physical PDF files because I am text-based.' "
        "That generic disclaimer is FALSE for AetherMind because our application is integrated with a real PDF generation backend.\n"
        "- When a user asks for a PDF, generate clear, professional, well-structured content with markdown headers (##), bullet points, and tables. Our backend automatically creates the downloadable PDF and provides the user with the verified download link.\n"
        "- If the user only says 'provide the PDF', 'give me the PDF', or 'download the PDF' without specifying which document, topic, or content, ask a concise clarification question: "
        "'Which document or topic would you like me to generate as a PDF? Please specify the document title, content, or attach a file using the + button.'\n"
        "- Never fabricate fake URLs or fake download links. Only refer to real features.\n"
        "- Do not pretend to have long-term memory of facts or biographical history that were never explicitly saved or provided in this conversation.\n"
    )

    personalization_parts = []

    # Style preference
    style_clean = (response_style or "balanced").strip().lower()
    if style_clean == "concise":
        personalization_parts.append(
            "RESPONSE STYLE - CONCISE:\n"
            "- Be direct, succinct, high-density, and to the point.\n"
            "- Omit conversational pleasantries, introductory throat-clearing, and verbose conclusions.\n"
            "- Prefer bullet points and compact explanations. Answer the query immediately."
        )
    elif style_clean == "detailed":
        personalization_parts.append(
            "RESPONSE STYLE - DETAILED:\n"
            "- Provide deep, thorough, comprehensive, and exhaustive coverage of the topic.\n"
            "- Break down concepts step-by-step with clear markdown headings, in-depth context, edge cases, and illustrative code/examples."
        )
    else:
        personalization_parts.append(
            "RESPONSE STYLE - BALANCED:\n"
            "- Provide clear, articulate, and well-rounded explanations with appropriate depth, context, and practical examples."
        )

    # Language preference
    lang_clean = (response_language or "English").strip()
    if lang_clean.lower() != "english":
        personalization_parts.append(
            f"RESPONSE LANGUAGE - {lang_clean.upper()}:\n"
            f"- You MUST generate your response in {lang_clean}.\n"
            f"- Ensure natural, idiomatic vocabulary, professional phrasing, and fluent grammar in {lang_clean}.\n"
            "- Keep code keywords, variable names, syntax, and technical terms in their standard technical format."
        )

    # Custom instructions
    if custom_instructions and custom_instructions.strip():
        personalization_parts.append(
            f"USER CUSTOM INSTRUCTIONS & PERSONA:\n"
            f"{custom_instructions.strip()}"
        )

    personalization_prompt = "\n\n" + "\n\n".join(personalization_parts) + "\n"

    if has_docs:
        doc_instructions = (
            "\nGROUNDED DOCUMENT REASONING RULES:\n"
            "1. Answer the user's questions based strictly on the factual content from the attached document(s).\n"
            "2. Do not invent facts, speculate, or make unsupported claims beyond what is stated in the document context.\n"
            "3. If the answer cannot be found in or deduced from the provided document, explicitly state:\n"
            "   'I could not find the answer to this question in the provided document.'\n"
            "4. Format numerical data, comparisons, and key takeaways clearly using markdown lists and tables.\n"
        )
        return base_instructions + personalization_prompt + doc_instructions
    else:
        general_instructions = (
            "\nCONVERSATION RULES:\n"
            "Provide helpful, accurate, well-formatted, and structured responses. "
            "Use markdown headers, lists, code blocks, and tables where appropriate.\n"
        )
        return base_instructions + personalization_prompt + general_instructions


def build_grounded_system_prompt() -> str:
    """Legacy alias for backward compatibility."""
    return build_aethermind_system_prompt(has_docs=True)
