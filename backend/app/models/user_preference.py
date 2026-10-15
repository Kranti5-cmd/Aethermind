from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text
from app.db.database import Base


class UserPreference(Base):
    """
    SQLAlchemy model representing saved user preferences for AI personalization.
    Module 5: Personalized AI Assistant
    Stores response style (concise, balanced, detailed), preferred language,
    and optional custom instructions scoped to user_id.
    """
    __tablename__ = "user_preferences"

    user_id = Column(String(64), primary_key=True, index=True)
    response_style = Column(String(32), default="balanced", nullable=False)  # 'concise', 'balanced', 'detailed'
    response_language = Column(String(64), default="English", nullable=False)
    custom_instructions = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
