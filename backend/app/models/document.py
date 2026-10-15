import uuid
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON
from app.db.database import Base


class Document(Base):
    """
    SQLAlchemy model representing an uploaded and extracted document in PostgreSQL.
    Stores the extracted text and metadata so chat sessions can retrieve documents by document_id.
    """
    __tablename__ = "documents"

    id = Column(String(64), primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(32), nullable=False)
    file_size = Column(Integer, nullable=False)
    extracted_text = Column(Text, nullable=False)
    doc_metadata = Column(JSON, nullable=True)
    user_id = Column(String(64), default="default_user", index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
