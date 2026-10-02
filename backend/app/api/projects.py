from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from uuid import UUID
from app.database import get_db
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
from app.api.deps import get_current_user
from app.models.user import User
from app.models.project import Project
from app.core.exceptions import NotFoundException

router = APIRouter(prefix='/api/projects', tags=['Projects'])

@router.post('', response_model=ProjectResponse)
@router.post('/', response_model=ProjectResponse, include_in_schema=False)
async def create_project(data: ProjectCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    project = Project(**data.model_dump(), owner_id=current_user.id)
    db.add(project)
    await db.commit()
    # Reload with relationships so counts work
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.uploads), selectinload(Project.documents))
        .filter(Project.id == project.id)
    )
    project = result.scalars().first()
    return project

@router.get('', response_model=List[ProjectResponse])
@router.get('/', response_model=List[ProjectResponse], include_in_schema=False)
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: Optional[int] = Query(default=1, ge=1),
    limit: Optional[int] = Query(default=50, ge=1, le=100),
):
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.uploads), selectinload(Project.documents))
        .filter(Project.owner_id == current_user.id, Project.status == 'active')
        .order_by(Project.created_at.desc())
    )
    return result.scalars().all()

@router.get('/{id}', response_model=ProjectResponse)
async def get_project(id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.uploads), selectinload(Project.documents))
        .filter(Project.id == id, Project.owner_id == current_user.id)
    )
    project = result.scalars().first()
    if not project:
        raise NotFoundException("Project not found")
    return project

@router.put('/{id}', response_model=ProjectResponse)
async def update_project(id: UUID, data: ProjectUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).filter(Project.id == id, Project.owner_id == current_user.id))
    project = result.scalars().first()
    if not project:
        raise NotFoundException("Project not found")
    
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(project, key, value)
        
    await db.commit()
    await db.refresh(project)
    return project

@router.delete('/{id}')
async def delete_project(id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).filter(Project.id == id, Project.owner_id == current_user.id))
    project = result.scalars().first()
    if not project:
        raise NotFoundException("Project not found")
    
    project.status = 'deleted'
    await db.commit()
    return {"message": "Project deleted successfully"}
