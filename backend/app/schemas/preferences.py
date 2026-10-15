from typing import Optional, Literal
from pydantic import BaseModel, Field


class UserPreferenceBase(BaseModel):
    response_style: Literal["concise", "balanced", "detailed"] = Field(
        default="balanced",
        description="Preferred response style: concise, balanced, or detailed",
    )
    response_language: str = Field(
        default="English",
        description="Preferred language for AI responses (e.g. English, Spanish, French, etc.)",
    )
    custom_instructions: Optional[str] = Field(
        default=None,
        description="Optional custom user persona or instructions",
    )


class UserPreferenceUpdate(UserPreferenceBase):
    pass


class UserPreferenceResponse(UserPreferenceBase):
    user_id: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True
