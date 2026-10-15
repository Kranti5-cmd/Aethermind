from pydantic import BaseModel, Field
from typing import Optional, List


class AttachedDocumentInput(BaseModel):
    id: Optional[str] = Field(None, description="Document ID in database")
    name: str = Field(..., description="Document filename")
    type: str = Field(..., description="File format extension or mime type")
    extracted_text: Optional[str] = Field(None, description="Extracted text from Document Intelligence")
    size: Optional[int] = Field(None, description="File size in bytes")


class AttachedImageInput(BaseModel):
    name: str = Field(..., description="Image filename")
    mime_type: str = Field(..., description="Image MIME type (e.g. image/png, image/jpeg)")
    base64_data: str = Field(..., description="Base64-encoded image data")
    size: Optional[int] = Field(None, description="File size in bytes")


class ChatRequest(BaseModel):
    message: str = Field(default="", description="User's prompt or message")
    session_id: Optional[str] = Field(None, description="Current chat session ID")
    document_ids: Optional[List[str]] = Field(default=None, description="Document IDs in database to retrieve and query")
    documents: Optional[List[AttachedDocumentInput]] = Field(default=None, description="Attached documents")
    images: Optional[List[AttachedImageInput]] = Field(default=None, description="Attached images")


class ChatResponse(BaseModel):
    reply: str = Field(..., description="AetherMind's response")
    session_id: str = Field(..., description="Active chat session ID")
    timestamp: str = Field(..., description="Formatted response timestamp")


class MessageItemResponse(BaseModel):
    id: int = Field(..., description="Unique message ID")
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    sender: str = Field(..., description="Sender compatible with frontend: 'user' or 'assistant'")
    content: str = Field(..., description="Text content of the message")
    timestamp: str = Field(..., description="Formatted message timestamp")

    class Config:
        from_attributes = True


class ConversationMessagesResponse(BaseModel):
    session_id: str = Field(..., description="Session identifier")
    title: Optional[str] = Field(None, description="Title of the conversation")
    created_at: Optional[str] = Field(None, description="ISO timestamp when created")
    updated_at: Optional[str] = Field(None, description="ISO timestamp when last updated")
    messages: List[MessageItemResponse] = Field(default_factory=list, description="Ordered list of messages")


class ConversationSummaryResponse(BaseModel):
    id: int
    session_id: str
    title: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    message_count: int = 0


class SearchMatchItem(BaseModel):
    conversation_id: int
    session_id: str
    conversation_title: str
    updated_at: Optional[str] = None
    matched_in: str = Field(..., description="'title' or 'message'")
    snippet: str
    role: Optional[str] = None
    timestamp: Optional[str] = None


class SearchResponse(BaseModel):
    query: str
    total_matches: int
    results: List[SearchMatchItem]
