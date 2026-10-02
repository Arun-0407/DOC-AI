import re
from typing import List
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.deps import assert_owner_or_admin, get_current_user
from app.core.exceptions import NotFoundException
from app.database import get_db
from app.models.document import Document
from app.models.project import Project
from app.models.upload import Upload
from app.models.user import User
from app.models.version import DocumentVersion
from app.schemas.document import (
    DocumentGenerateRequest,
    DocumentListResponse,
    DocumentResponse,
    DocumentSectionResponse,
    DocumentStatusResponse,
)
from app.services.doc_generator import SECTIONS, run_generation

router = APIRouter(prefix="/api/documents", tags=["Documents"])

SECTION_NAMES = {attr for attr, _ in SECTIONS}
STEP_PATTERN = re.compile(r"(\d+)\s*/\s*(\d+)")


async def get_document_or_404(db: AsyncSession, document_id: UUID) -> Document:
    document = (await db.execute(select(Document).filter(Document.id == document_id))).scalars().first()
    if not document:
        raise NotFoundException("Document not found")
    return document


async def get_document_or_403(db: AsyncSession, document_id: UUID, current_user: User) -> Document:
    """Load document and enforce owner-or-admin access."""
    document = await get_document_or_404(db, document_id)
    assert_owner_or_admin(document.generated_by, current_user)
    return document


def step_to_progress(status: str, step: str) -> int:
    if status in ("completed", "failed"):
        return 100
    if status == "queued":
        return 5
    if status == "fetching":
        return 15
    match = STEP_PATTERN.search(step or "")
    if match:
        done, total = int(match.group(1)), int(match.group(2)) or 1
        return 20 + int(done / total * 75)
    return 20 if status == "generating" else 10


@router.post("/generate", response_model=DocumentResponse)
async def generate_docs(
    request: DocumentGenerateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    upload = (await db.execute(select(Upload).filter(Upload.id == request.upload_id))).scalars().first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")
    if upload.project_id != request.project_id:
        raise HTTPException(status_code=400, detail="Upload does not belong to this project")

    # Verify the caller owns the project (or is admin)
    project = (await db.execute(select(Project).filter(Project.id == request.project_id))).scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    assert_owner_or_admin(project.owner_id, current_user)

    document = Document(
        project_id=request.project_id,
        upload_id=request.upload_id,
        title=request.title or f"Documentation - {upload.filename}",
        status="queued",
        generation_step="Queued",
        generated_by=current_user.id,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    background_tasks.add_task(run_generation, document.id, current_user.id)
    return document


@router.get("/project/{project_id}", response_model=List[DocumentListResponse])
async def list_documents(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify the caller owns the project (or is admin)
    project = (await db.execute(select(Project).filter(Project.id == project_id))).scalars().first()
    if not project:
        raise NotFoundException("Project not found")
    assert_owner_or_admin(project.owner_id, current_user)

    result = await db.execute(
        select(Document)
        .filter(Document.project_id == project_id)
        .order_by(Document.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    document = await get_document_or_403(db, id, current_user)
    return DocumentStatusResponse(
        id=document.id,
        status=document.status,
        generation_step=document.generation_step or "",
        progress=step_to_progress(document.status, document.generation_step or ""),
    )


@router.get("/{id}", response_model=DocumentResponse)
async def get_document(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_document_or_403(db, id, current_user)


@router.get("/{id}/section/{section_name}", response_model=DocumentSectionResponse)
async def get_document_section(
    id: UUID,
    section_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if section_name not in SECTION_NAMES:
        raise NotFoundException(f"Unknown section '{section_name}'")
    document = await get_document_or_403(db, id, current_user)
    data = getattr(document, section_name)
    if data is None:
        raise NotFoundException(f"Section '{section_name}' has not been generated")
    return DocumentSectionResponse(section_name=section_name, data=data)


@router.delete("/{id}")
async def delete_document(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    document = await get_document_or_403(db, id, current_user)
    await db.delete(document)
    await db.commit()
    return {"message": "Document deleted"}


@router.get("/{id}/versions")
async def list_versions(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_document_or_403(db, id, current_user)
    result = await db.execute(
        select(DocumentVersion)
        .filter(DocumentVersion.document_id == id)
        .order_by(DocumentVersion.version_number.desc())
    )
    return result.scalars().all()