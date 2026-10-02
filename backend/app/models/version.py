import uuid
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base

class DocumentVersion(Base):
    __tablename__ = 'document_versions'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey('documents.id', ondelete='CASCADE'))
    version_number = Column(Integer, nullable=False)
    snapshot = Column(JSON, nullable=False)
    change_summary = Column(Text)
    created_by = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    created_at = Column(DateTime, server_default=func.now())

    document = relationship("Document", back_populates="versions")
    creator = relationship("User", back_populates="versions")
