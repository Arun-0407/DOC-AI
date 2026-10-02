import time
from collections import defaultdict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException
from app.models.user import User
from app.schemas.user import UserCreate
from app.core.security import hash_password, verify_password
from app.core.exceptions import BadRequestException, UnauthorizedException
from uuid import UUID

# ── Simple in-memory rate limiter for login attempts ─────────────────────────
# Max 5 failed attempts per email per 5 minutes
_login_attempts: dict = defaultdict(list)
_MAX_ATTEMPTS = 5
_WINDOW_SECONDS = 300  # 5 minutes


def _check_rate_limit(email: str) -> None:
    """Raise HTTP 429 if too many recent failed login attempts for this email."""
    now = time.time()
    # Keep only attempts within the window
    attempts = [t for t in _login_attempts[email] if now - t < _WINDOW_SECONDS]
    _login_attempts[email] = attempts
    if len(attempts) >= _MAX_ATTEMPTS:
        wait = int(_WINDOW_SECONDS - (now - attempts[0]))
        raise HTTPException(
            status_code=429,
            detail=f"Too many login attempts. Please wait {wait} seconds before trying again.",
        )


def _record_failed_attempt(email: str) -> None:
    _login_attempts[email].append(time.time())


def _clear_attempts(email: str) -> None:
    _login_attempts.pop(email, None)


async def register_user(db: AsyncSession, user_data: UserCreate) -> User:
    result = await db.execute(select(User).filter(User.email == user_data.email))
    if result.scalars().first():
        raise BadRequestException("Email already registered")
        
    user = User(
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        full_name=user_data.full_name
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    # Check rate limit before touching the DB
    _check_rate_limit(email)

    result = await db.execute(select(User).filter(User.email == email))
    user = result.scalars().first()

    if not user or not verify_password(password, user.password_hash):
        # Record failed attempt
        _record_failed_attempt(email)
        raise UnauthorizedException("Incorrect email or password")

    # Successful login — clear any recorded failures
    _clear_attempts(email)
    return user

async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User:
    result = await db.execute(select(User).filter(User.id == user_id))
    return result.scalars().first()

async def get_user_by_email(db: AsyncSession, email: str) -> User:
    result = await db.execute(select(User).filter(User.email == email))
    return result.scalars().first()
