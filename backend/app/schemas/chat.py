from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime


class ChatRequest(BaseModel):
    upload_id: UUID
    message: str


class ChatMessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
