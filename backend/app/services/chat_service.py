from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import UUID
from app.models.chat import ChatMessage
from app.models.upload import Upload
from app.services.ai_service import AIService


async def process_chat(db: AsyncSession, upload_id: UUID, user_id: UUID, message: str) -> str:
    # 1. Get upload content first
    result = await db.execute(select(Upload).filter(Upload.id == upload_id))
    upload = result.scalars().first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found. Please select a valid upload.")
    source_code = upload.content or ""

    # 2. Get existing chat history (BEFORE saving new user message)
    hist_result = await db.execute(
        select(ChatMessage)
        .filter(ChatMessage.upload_id == upload_id)
        .order_by(ChatMessage.created_at.asc())
    )
    history = hist_result.scalars().all()

    # 3. Build messages list for AI (history + new user message)
    messages = [{"role": msg.role, "content": msg.content} for msg in history]
    messages.append({"role": "user", "content": message})

    # 4. Call AI
    ai = AIService()
    response_text = await ai.chat_with_code(messages, source_code)

    # 5. Save user message to DB
    user_msg = ChatMessage(
        upload_id=upload_id,
        user_id=user_id,
        role="user",
        content=message
    )
    db.add(user_msg)

    # 6. Save AI response to DB
    ai_msg = ChatMessage(
        upload_id=upload_id,
        user_id=user_id,
        role="assistant",
        content=response_text
    )
    db.add(ai_msg)
    await db.commit()

    return response_text
