from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
from typing import Optional
from uuid import UUID
from datetime import datetime


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v

    @field_validator("full_name")
    @classmethod
    def full_name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Full name cannot be empty")
        return v.strip()


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    """Schema for PATCH /api/auth/me — all fields optional."""
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    current_password: Optional[str] = None   # required when changing password
    new_password: Optional[str] = None

    @field_validator("full_name")
    @classmethod
    def full_name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("Full name cannot be empty")
        return v.strip() if v else v

    @field_validator("new_password")
    @classmethod
    def new_password_strength(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if len(v) < 8:
            raise ValueError("New password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("New password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("New password must contain at least one digit")
        return v


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str
    role: str
    avatar_url: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse
