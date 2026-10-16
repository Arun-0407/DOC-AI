from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from uuid import UUID
from app.database import get_db
from app.schemas.chat import ChatRequest, ChatMessageResponse
from app.api.deps import get_current_user
from app.core.exceptions import ForbiddenException, NotFoundException
from app.models.user import User
from app.models.upload import Upload
from app.models.chat import ChatMessage
from app.services.chat_service import process_chat

router = APIRouter(prefix='/api/chat', tags=['AI Chat'])


@router.post('', response_model=ChatMessageResponse)
@router.post('/', response_model=ChatMessageResponse, include_in_schema=False)
async def send_message(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        await process_chat(db, request.upload_id, current_user.id, request.message)
        # Return the last assistant message saved to DB
        result = await db.execute(
            select(ChatMessage)
            .filter(
                ChatMessage.upload_id == request.upload_id,
                ChatMessage.role == 'assistant'
            )
            .order_by(ChatMessage.created_at.desc())
        )
        msg = result.scalars().first()
        if not msg:
            raise HTTPException(status_code=500, detail="AI response was not saved")
        return msg
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


@router.get('/history/{upload_id}', response_model=List[ChatMessageResponse])
async def get_history(
    upload_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify the upload exists and belongs to the current user (or user is admin)
    upload_result = await db.execute(select(Upload).filter(Upload.id == upload_id))
    upload = upload_result.scalars().first()
    if not upload:
        raise NotFoundException("Upload not found")
    if current_user.role != "admin" and upload.uploaded_by != current_user.id:
        raise ForbiddenException("You do not have access to this chat history")

    result = await db.execute(
        select(ChatMessage)
        .filter(ChatMessage.upload_id == upload_id)
        .order_by(ChatMessage.created_at.asc())
    )
    return result.scalars().all()


@router.delete('/history/{upload_id}')
async def clear_history(
    upload_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ChatMessage)
        .filter(
            ChatMessage.upload_id == upload_id,
            ChatMessage.user_id == current_user.id
        )
    )
    messages = result.scalars().all()
    for msg in messages:
        await db.delete(msg)
    await db.commit()
    return {"message": "Chat history cleared"}
