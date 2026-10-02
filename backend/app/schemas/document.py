from pydantic import BaseModel, ConfigDict
from typing import Optional, Any, Dict
from uuid import UUID
from datetime import datetime


class DocumentGenerateRequest(BaseModel):
    upload_id: UUID
    project_id: UUID
    title: Optional[str] = None


class DocumentResponse(BaseModel):
    id: UUID
    project_id: UUID
    upload_id: UUID
    title: Optional[str] = None
    status: str
    generation_step: Optional[str] = ""
    cover_data: Optional[Dict] = None
    business_view: Optional[Dict] = None
    technical_view: Optional[Dict] = None
    source_analysis: Optional[Dict] = None
    database_analysis: Optional[Dict] = None
    api_dependency: Optional[Dict] = None
    process_flow: Optional[Dict] = None
    diagrams: Optional[Dict] = None
    integration_view: Optional[Dict] = None
    security_review: Optional[Dict] = None
    performance_review: Optional[Dict] = None
    reference_data: Optional[Dict] = None
    modification_history: Optional[Dict] = None
    ai_recommendations: Optional[Dict] = None
    generated_by: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    id: UUID
    title: Optional[str] = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentStatusResponse(BaseModel):
    """Lightweight response for polling generation progress."""
    id: UUID
    status: str                          # queued | fetching | generating | completed | failed
    generation_step: Optional[str] = ""  # human-readable current step label
    progress: int = 0                    # 0-100 derived from step

    model_config = ConfigDict(from_attributes=True)


class DocumentSectionResponse(BaseModel):
    section_name: str
    data: Dict
