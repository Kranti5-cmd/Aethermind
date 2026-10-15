from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class DocumentUploadResponse(BaseModel):
    """Response model for uploaded document text extraction."""
    status: str = Field("success", description="Status of the extraction")
    id: str = Field(..., description="Unique document ID in database")
    filename: str = Field(..., description="Original name of the uploaded file")
    file_type: str = Field(..., description="Normalized file format: pdf, docx, txt, csv")
    file_size: int = Field(..., description="File size in bytes")
    extracted_text: str = Field(..., description="Extracted textual content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata such as character count, word count, page count, etc.")
    uploaded_at: Optional[str] = Field(None, description="ISO timestamp or formatted time")


class DocumentItemResponse(BaseModel):
    """Schema for document summaries in document listings."""
    id: str = Field(..., description="Unique document ID")
    filename: str = Field(..., description="Document filename")
    file_type: str = Field(..., description="File format")
    file_size: int = Field(..., description="File size in bytes")
    extracted_text: Optional[str] = Field(None, description="Extracted text preview or full text")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")
    uploaded_at: str = Field(..., description="Upload timestamp")

    class Config:
        from_attributes = True


class DocumentSummaryResponse(BaseModel):
    """Schema for document summarization and key-information extraction (Requirement 7)."""
    document_id: str = Field(..., description="Unique document ID")
    filename: str = Field(..., description="Document filename")
    summary: str = Field(..., description="Concise executive summary of document")
    key_points: List[str] = Field(default_factory=list, description="Extracted key information and takeaways")
    key_entities: List[str] = Field(default_factory=list, description="Key entities, subjects, or participants")
    metrics: List[str] = Field(default_factory=list, description="Extracted numerical figures, measurements, or data metrics")


class DocumentUploadError(BaseModel):
    """Error model for document upload failures."""
    status: str = Field("error", description="Error status")
    detail: str = Field(..., description="Human-readable explanation of why extraction or validation failed")


class PDFGenerateRequest(BaseModel):
    title: str = Field(..., description="Document title for the PDF header")
    content: str = Field(..., description="Markdown or text content to render in the PDF")
    filename: Optional[str] = Field(None, description="Optional custom filename")
    subtitle: Optional[str] = Field(None, description="Optional subtitle or metadata note")


class PDFGenerateResponse(BaseModel):
    status: str = Field("success", description="Status of the PDF generation")
    pdf_id: str = Field(..., description="Unique generated PDF identifier")
    filename: str = Field(..., description="Name of the generated PDF file")
    file_size: int = Field(..., description="PDF size in bytes")
    title: str = Field(..., description="Title of the PDF document")
    download_url: str = Field(..., description="Relative download URL for the PDF")
    created_at: str = Field(..., description="Timestamp of generation")
