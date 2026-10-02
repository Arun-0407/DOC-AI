import io
import re
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.api.deps import assert_owner_or_admin, get_current_user
from app.core.exceptions import NotFoundException
from app.database import get_db
from app.models.document import Document
from app.models.user import User
from app.services.docx_service import generate_docx
from app.services.html_service import generate_html
from app.services.pdf_service import generate_pdf

router = APIRouter(prefix="/api/export", tags=["Export"])


def _safe_filename(name: str, ext: str) -> str:
    safe = re.sub(r"[^\w\s\-.]", "", name or "document").strip().replace(" ", "_") or "document"
    safe = safe[:80]
    encoded = quote(f"{name or 'document'}.{ext}", safe="")
    return f'attachment; filename="{safe}.{ext}"; filename*=UTF-8\'\'{encoded}'


async def _load_doc_with_parsed(document_id: UUID, db: AsyncSession, current_user: User) -> Document:
    """Load document, enforce ownership, and attach parsed_metadata."""
    result = await db.execute(
        select(Document).options(selectinload(Document.upload))
        .filter(Document.id == document_id)
    )
    doc = result.scalars().first()
    if not doc:
        raise NotFoundException("Document not found")
    assert_owner_or_admin(doc.generated_by, current_user)
    parsed_meta = {}
    if doc.upload and doc.upload.parsed_metadata:
        pm = doc.upload.parsed_metadata
        parsed_meta = pm if isinstance(pm, dict) else {}
    doc._parsed_metadata = parsed_meta  # type: ignore
    return doc


@router.get("/{document_id}/pdf")
async def export_pdf(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = await _load_doc_with_parsed(document_id, db, current_user)
    pdf_bytes = generate_pdf(doc)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": _safe_filename(doc.title, "pdf")},
    )


@router.get("/{document_id}/docx")
async def export_docx(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = await _load_doc_with_parsed(document_id, db, current_user)
    docx_bytes = generate_docx(doc)
    return StreamingResponse(
        io.BytesIO(docx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": _safe_filename(doc.title, "docx")},
    )


@router.get("/{document_id}/html")
async def export_html(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = await _load_doc_with_parsed(document_id, db, current_user)
    html_content = generate_html(doc)
    return StreamingResponse(
        io.BytesIO(html_content.encode("utf-8")),
        media_type="text/html",
        headers={"Content-Disposition": _safe_filename(doc.title, "html")},
    )
