import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserLogin, TokenResponse, UserResponse, UserUpdate
from app.services.auth_service import register_user, authenticate_user
from app.services.email_service import send_password_reset_email

router = APIRouter(prefix='/api/auth', tags=['Authentication'])


# ── Schemas for password reset ────────────────────────────────────────────────
class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


@router.post('/register', response_model=TokenResponse)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    user = await register_user(db, user_data)
    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(access_token=token, token_type="bearer", user=user)


@router.post('/login', response_model=TokenResponse)
async def login(user_data: UserLogin, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, user_data.email, user_data.password)
    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(access_token=token, token_type="bearer", user=user)


@router.get('/me', response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch('/me', response_model=UserResponse)
async def update_me(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the current user's profile (name, avatar, password)."""
    # If changing password, current_password is required
    if data.new_password:
        if not data.current_password:
            raise HTTPException(status_code=422, detail="current_password is required to set a new password")
        if not verify_password(data.current_password, current_user.password_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        current_user.password_hash = hash_password(data.new_password)

    if data.full_name is not None:
        current_user.full_name = data.full_name
    if data.avatar_url is not None:
        current_user.avatar_url = data.avatar_url

    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.post('/refresh', response_model=TokenResponse)
async def refresh(current_user: User = Depends(get_current_user)):
    token = create_access_token({"sub": str(current_user.id)})
    return TokenResponse(access_token=token, token_type="bearer", user=current_user)


@router.post('/logout')
async def logout(current_user: User = Depends(get_current_user)):
    """
    Server-side logout.
    Client must also clear localStorage (handled by frontend authStore).
    Returns 200 — token invalidation is handled client-side since we use stateless JWT.
    """
    return JSONResponse(
        status_code=200,
        content={"message": "Logged out successfully"}
    )


# ── Forgot Password ───────────────────────────────────────────────────────────
@router.post('/forgot-password')
async def forgot_password(
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Step 1 — Request a password reset.
    Always returns 200 (even if email not found) to prevent user enumeration.
    Sends a reset link to the user's email valid for PASSWORD_RESET_EXPIRY_MINUTES.
    """
    result = await db.execute(select(User).filter(User.email == body.email))
    user: User | None = result.scalars().first()

    if user and user.is_active:
        # Generate a secure random token
        token = secrets.token_urlsafe(48)
        expires = datetime.now(timezone.utc) + timedelta(
            minutes=settings.PASSWORD_RESET_EXPIRY_MINUTES
        )
        user.password_reset_token = token
        user.password_reset_expires = expires
        await db.commit()

        # Send email (non-blocking best-effort)
        await send_password_reset_email(
            to_email=user.email,
            full_name=user.full_name or user.email,
            reset_token=token,
        )

    # Always respond with the same message to prevent enumeration attacks
    return JSONResponse(
        status_code=200,
        content={
            "message": (
                "If that email address is registered, you will receive a "
                "password reset link shortly."
            )
        },
    )


# ── Validate Reset Token ──────────────────────────────────────────────────────
@router.get('/reset-password/validate')
async def validate_reset_token(token: str, db: AsyncSession = Depends(get_db)):
    """
    Step 1b — Check whether a reset token is still valid (used by the frontend
    to show the form vs. an expired-link screen).
    """
    result = await db.execute(
        select(User).filter(User.password_reset_token == token)
    )
    user: User | None = result.scalars().first()

    if not user or not user.password_reset_expires:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

    expires = user.password_reset_expires
    # Make expires offset-aware if it came back naive
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) > expires:
        raise HTTPException(status_code=400, detail="Reset token has expired. Please request a new one.")

    return {"valid": True, "email": user.email}


# ── Reset Password ────────────────────────────────────────────────────────────
@router.post('/reset-password')
async def reset_password(
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Step 2 — Set the new password using the token from the email link.
    """
    if len(body.new_password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters.")

    result = await db.execute(
        select(User).filter(User.password_reset_token == body.token)
    )
    user: User | None = result.scalars().first()

    if not user or not user.password_reset_expires:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

    expires = user.password_reset_expires
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) > expires:
        raise HTTPException(status_code=400, detail="Reset token has expired. Please request a new one.")

    # Apply new password and clear the reset token
    user.password_hash = hash_password(body.new_password)
    user.password_reset_token = None
    user.password_reset_expires = None
    await db.commit()

    return JSONResponse(
        status_code=200,
        content={"message": "Password reset successfully. You can now sign in with your new password."},
    )
