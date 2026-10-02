from pydantic import BaseModel, ConfigDict, model_validator
from typing import Optional
from uuid import UUID
from datetime import datetime


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    module: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    module: Optional[str] = None
    status: Optional[str] = None


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    module: Optional[str] = None
    status: str
    owner_id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    upload_count: Optional[int] = 0
    document_count: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode='before')
    @classmethod
    def compute_counts(cls, values):
        # When building from a SQLAlchemy ORM object, compute counts from relationships
        if hasattr(values, 'uploads'):
            try:
                values.__dict__['upload_count'] = len(values.uploads)
            except Exception:
                pass
        if hasattr(values, 'documents'):
            try:
                values.__dict__['document_count'] = len(values.documents)
            except Exception:
                pass
        return values
