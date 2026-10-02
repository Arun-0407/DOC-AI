from pydantic import BaseModel, ConfigDict
from typing import Optional, Any
from uuid import UUID
from datetime import datetime


class UploadResponse(BaseModel):
    id: UUID
    project_id: UUID
    filename: str
    file_type: str
    file_size: int
    parsed_metadata: Optional[Any] = None
    uploaded_by: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UploadListResponse(BaseModel):
    id: UUID
    filename: str
    file_type: str
    file_size: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
