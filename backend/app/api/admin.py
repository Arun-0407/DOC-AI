"""
Admin API — user management and system statistics.
All endpoints require the 'admin' role.
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.security import hash_password
from app.database import get_db
from app.models.document import Document
from app.models.project import Project
from app.models.upload import Upload
from app.models.user import User
from app.schemas.user import UserResponse

router = APIRouter(prefix="/api/admin", tags=["Admin"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class AdminUserUpdate(BaseModel):
    role: Optional[str] = None          # "user" | "admin"
    is_active: Optional[bool] = None
    full_name: Optional[str] = None
    new_password: Optional[str] = None  # admin can reset any user's password


class AdminUserResponse(UserResponse):
    is_active: bool
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class StatsResponse(BaseModel):
    total_users: int
    active_users: int
    total_projects: int
    total_uploads: int
    total_documents: int
    documents_completed: int
    documents_failed: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=StatsResponse)
async def get_system_stats(
    _: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Return high-level system statistics."""
    total_users = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
    active_users = (await db.execute(select(func.count()).select_from(User).where(User.is_active == True))).scalar() or 0
    total_projects = (await db.execute(select(func.count()).select_from(Project).where(Project.status == "active"))).scalar() or 0
    total_uploads = (await db.execute(select(func.count()).select_from(Upload))).scalar() or 0
    total_documents = (await db.execute(select(func.count()).select_from(Document))).scalar() or 0
    documents_completed = (await db.execute(select(func.count()).select_from(Document).where(Document.status == "completed"))).scalar() or 0
    documents_failed = (await db.execute(select(func.count()).select_from(Document).where(Document.status == "failed"))).scalar() or 0

    return StatsResponse(
        total_users=total_users,
        active_users=active_users,
        total_projects=total_projects,
        total_uploads=total_uploads,
        total_documents=total_documents,
        documents_completed=documents_completed,
        documents_failed=documents_failed,
    )


@router.get("/users", response_model=List[AdminUserResponse])
async def list_all_users(
    _: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    search: Optional[str] = Query(default=None),
):
    """List all users with optional search by email or name."""
    stmt = select(User).order_by(User.created_at.desc())
    if search:
        q = f"%{search}%"
        stmt = stmt.where(
            (User.email.ilike(q)) | (User.full_name.ilike(q))
        )
    stmt = stmt.offset((page - 1) * limit).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/users/{user_id}", response_model=AdminUserResponse)
async def get_user(
    user_id: UUID,
    _: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific user by ID."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
async def update_user(
    user_id: UUID,
    data: AdminUserUpdate,
    current_admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Update a user's role, active status, name, or password."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent admin from demoting themselves accidentally
    if str(user_id) == str(current_admin.id) and data.role and data.role != "admin":
        raise HTTPException(status_code=400, detail="You cannot change your own role")

    if data.role is not None:
        if data.role not in ("user", "admin"):
            raise HTTPException(status_code=422, detail="Role must be 'user' or 'admin'")
        user.role = data.role

    if data.is_active is not None:
        user.is_active = data.is_active

    if data.full_name is not None:
        user.full_name = data.full_name.strip()

    if data.new_password is not None:
        if len(data.new_password) < 8:
            raise HTTPException(status_code=422, detail="Password must be at least 8 characters")
        user.password_hash = hash_password(data.new_password)

    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/users/{user_id}")
async def deactivate_user(
    user_id: UUID,
    current_admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate (soft-delete) a user account."""
    if str(user_id) == str(current_admin.id):
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = False
    await db.commit()
    return {"message": f"User {user.email} has been deactivated"}


@router.post("/users/{user_id}/activate")
async def activate_user(
    user_id: UUID,
    _: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Re-activate a previously deactivated user account."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = True
    await db.commit()
    return {"message": f"User {user.email} has been activated"}
