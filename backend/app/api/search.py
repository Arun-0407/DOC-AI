from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, outerjoin
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.deps import get_current_user
from app.database import get_db
from app.models.document import Document
from app.models.upload import Upload
from app.models.user import User

router = APIRouter(prefix="/api/search", tags=["Search"])


@router.get("")
@router.get("/", include_in_schema=False)
async def search_documents(
    query: str,
    project_id: Optional[UUID] = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Search documents by title, upload filename, or document type.
    Supports pagination via page/limit query params.
    """
    q = f"%{query}%"
    stmt = (
        select(Document)
        .outerjoin(Upload, Document.upload_id == Upload.id)
        .filter(Document.generated_by == current_user.id)
        .filter(
            or_(
                Document.title.ilike(q),
                Document.doc_type.ilike(q),
                Upload.filename.ilike(q),
            )
        )
        .order_by(Document.created_at.desc())
    )

    if project_id:
        stmt = stmt.filter(Document.project_id == project_id)

    stmt = stmt.offset((page - 1) * limit).limit(limit)

    result = await db.execute(stmt)
    docs = result.scalars().all()
    return {
        "results": docs,
        "page": page,
        "limit": limit,
        "query": query,
        "total": len(docs),
    }
