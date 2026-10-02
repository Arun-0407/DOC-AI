import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base

class Document(Base):
    __tablename__ = 'documents'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey('projects.id', ondelete='CASCADE'))
    upload_id = Column(UUID(as_uuid=True), ForeignKey('uploads.id'))
    title = Column(String(255))
    status = Column(String(50), default='queued')
    generation_step = Column(String(100), default='')
    cover_data = Column(JSON)
    business_view = Column(JSON)
    technical_view = Column(JSON)
    source_analysis = Column(JSON)
    database_analysis = Column(JSON)
    api_dependency = Column(JSON)
    process_flow = Column(JSON)
    diagrams = Column(JSON)
    integration_view = Column(JSON)
    security_review = Column(JSON)
    performance_review = Column(JSON)
    reference_data = Column(JSON)
    modification_history = Column(JSON)
    ai_recommendations = Column(JSON)
    generated_by = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    project = relationship("Project", back_populates="documents")
    upload = relationship("Upload", back_populates="documents")
    versions = relationship("DocumentVersion", back_populates="document")
    generator = relationship("User", back_populates="documents")
