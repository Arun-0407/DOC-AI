from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.deps import get_current_user
from app.database import get_db
from app.models.document import Document
from app.models.user import User

router = APIRouter(prefix="/api/search", tags=["Search"])


@router.get("")
@router.get("/", include_in_schema=False)
async def search_documents(
    query: str,
    project_id: Optional[UUID] = None,
    page: int = 1,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Document).filter(Document.generated_by == current_user.id)

    if project_id:
        stmt = stmt.filter(Document.project_id == project_id)

    stmt = stmt.filter(or_(Document.title.ilike(f"%{query}%")))
    stmt = stmt.offset((page - 1) * limit).limit(limit)

    result = await db.execute(stmt)
    return result.scalars().all()
