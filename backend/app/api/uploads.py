import logging
import os
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.deps import assert_owner_or_admin, get_current_user
from app.config import settings
from app.core.exceptions import ForbiddenException, NotFoundException
from app.database import get_db
from app.models.project import Project
from app.models.upload import Upload
from app.models.user import User
from app.schemas.upload import UploadListResponse, UploadResponse
from app.utils.file_utils import detect_abap_type, extract_zip, read_file_content, save_upload_file
from app.utils.sap_extractor import SAPObjectExtractor

_extractor = SAPObjectExtractor()
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/uploads", tags=["Uploads"])

BLOCKED_EXTENSIONS = {".exe", ".dll", ".bat", ".sh", ".cmd", ".msi", ".dmg", ".bin", ".iso"}


def _check_extension(filename: str) -> None:
    ext = os.path.splitext(filename)[1].lower()
    if ext in BLOCKED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type '{ext}' is not allowed")


async def _get_project_or_403(db: AsyncSession, project_id: UUID, current_user: User) -> Project:
    result = await db.execute(select(Project).filter(Project.id == project_id))
    project = result.scalars().first()
    if not project:
        raise NotFoundException("Project not found")
    assert_owner_or_admin(project.owner_id, current_user)
    return project


async def _get_upload_or_403(db: AsyncSession, upload_id: UUID, current_user: User) -> Upload:
    result = await db.execute(select(Upload).filter(Upload.id == upload_id))
    upload = result.scalars().first()
    if not upload:
        raise NotFoundException("Upload not found")
    assert_owner_or_admin(upload.uploaded_by, current_user)
    return upload


@router.post("/file", response_model=UploadResponse)
async def upload_file(
    project_id: UUID = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _check_extension(file.filename or "")
    await _get_project_or_403(db, project_id, current_user)
    try:
        logger.info("Uploading file: %s, project: %s", file.filename, project_id)
        file_path = await save_upload_file(file, settings.UPLOAD_DIR)
        content = read_file_content(file_path)
        file_type = detect_abap_type(content, file.filename)
        parsed_metadata = _extractor.extract(content, file_type, file.filename)
        upload = Upload(
            project_id=project_id,
            filename=file.filename,
            file_type=file_type,
            file_size=len(content.encode("utf-8")),
            content=content,
            parsed_metadata=parsed_metadata,
            uploaded_by=current_user.id,
        )
        db.add(upload)
        await db.commit()
        await db.refresh(upload)
        logger.info("Upload successful: %s", upload.id)
        return upload
    except (NotFoundException, ForbiddenException, HTTPException):
        raise
    except Exception as exc:
        logger.error("Upload failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}")


@router.post("/zip", response_model=UploadResponse)
async def upload_zip(
    project_id: UUID = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_project_or_403(db, project_id, current_user)
    try:
        logger.info("Uploading ZIP: %s, project: %s", file.filename, project_id)
        extracted = await extract_zip(file, settings.UPLOAD_DIR)
        if not extracted:
            raise HTTPException(status_code=400, detail="ZIP file is empty or contains no readable files")

        uploads = []
        for item in extracted:
            content = item["content"]
            file_type = detect_abap_type(content, item["filename"])
            parsed_metadata = _extractor.extract(content, file_type, item["filename"])
            upload = Upload(
                project_id=project_id,
                filename=item["filename"],
                file_type=file_type,
                file_size=len(content.encode("utf-8")),
                content=content,
                parsed_metadata=parsed_metadata,
                uploaded_by=current_user.id,
            )
            db.add(upload)
            uploads.append(upload)

        await db.commit()
        for u in uploads:
            await db.refresh(u)
        logger.info("ZIP upload: %d files extracted", len(uploads))
        return uploads[0]
    except (NotFoundException, ForbiddenException, HTTPException):
        raise
    except Exception as exc:
        logger.error("ZIP upload failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"ZIP upload failed: {exc}")


@router.get("/project/{project_id}", response_model=List[UploadListResponse])
async def list_uploads(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_project_or_403(db, project_id, current_user)
    result = await db.execute(
        select(Upload)
        .filter(Upload.project_id == project_id)
        .order_by(Upload.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{id}", response_model=UploadResponse)
async def get_upload(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _get_upload_or_403(db, id, current_user)


@router.delete("/{id}")
async def delete_upload(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    upload = await _get_upload_or_403(db, id, current_user)
    await db.delete(upload)
    await db.commit()
    return {"message": "Upload deleted successfully"}
