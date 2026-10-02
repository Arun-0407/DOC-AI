import uuid
from sqlalchemy import Column, String, Text, DateTime, BigInteger, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base

class Upload(Base):
    __tablename__ = 'uploads'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey('projects.id', ondelete='CASCADE'))
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50))
    file_size = Column(BigInteger)
    content = Column(Text)
    parsed_metadata = Column(JSON)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    created_at = Column(DateTime, server_default=func.now())

    project = relationship("Project", back_populates="uploads")
    uploader = relationship("User", back_populates="uploads")
    documents = relationship("Document", back_populates="upload")
    chat_messages = relationship("ChatMessage", back_populates="upload")
