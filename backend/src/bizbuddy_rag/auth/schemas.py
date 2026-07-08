"""Pydantic schemas for auth endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class UserLogin(BaseModel):
    """登录请求。"""

    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class UserResponse(BaseModel):
    """用户信息返回体。"""

    id: UUID
    username: str
    nickname: str | None = None
    avatar: str | None = None
    email: str | None = None
    phone: str | None = None
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    """JWT token 返回体。"""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenWithUser(Token):
    """token + 当前用户信息。"""

    user: UserResponse


class LoginResponse(BaseModel):
    """登录响应，包一层 success/message 与 rswaste 保持一致。"""

    success: bool
    message: str
    data: TokenWithUser | None = None
