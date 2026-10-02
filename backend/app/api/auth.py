from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.user import UserCreate, UserLogin, TokenResponse, UserResponse
from app.services.auth_service import register_user, authenticate_user
from app.api.deps import get_current_user
from app.core.security import create_access_token
from app.models.user import User

router = APIRouter(prefix='/api/auth', tags=['Authentication'])


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
