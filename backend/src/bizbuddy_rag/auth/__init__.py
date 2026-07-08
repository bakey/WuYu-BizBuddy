"""认证模块。

与 WuYu-rswaste-platform 共用 buildingai.public.user 表。
使用相同的 SECRET_KEY / HS256 / bcrypt，保证 token 两边互验。
"""

from bizbuddy_rag.auth.deps import (
    get_current_active_user,
    get_current_user,
    get_optional_user,
)
from bizbuddy_rag.auth.models import User
from bizbuddy_rag.auth.schemas import LoginResponse, UserLogin, UserResponse
from bizbuddy_rag.auth.security import (
    create_access_token,
    get_password_hash,
    verify_password,
    verify_token,
)
from bizbuddy_rag.auth.service import UserService

__all__ = [
    "LoginResponse",
    "User",
    "UserLogin",
    "UserResponse",
    "UserService",
    "create_access_token",
    "get_current_active_user",
    "get_current_user",
    "get_optional_user",
    "get_password_hash",
    "verify_password",
    "verify_token",
]
