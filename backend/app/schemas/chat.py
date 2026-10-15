from pydantic import BaseModel, Field
from typing import Optional, List


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User's prompt or message")
    session_id: Optional[str] = Field(None, description="Current chat session ID")


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
