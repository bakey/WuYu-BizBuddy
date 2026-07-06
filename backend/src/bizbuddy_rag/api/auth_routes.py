"""认证路由。

前端不做登录页，登录跳转 rswaste 的 https://www.wuyullm.com/login。
但仍保留：
- /auth/login  用于本地调试 / curl；也可给 rswaste 复用
- /auth/me     前端 boot 时拉当前用户信息
- /auth/logout 清 cookie
"""

from datetime import timedelta

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from bizbuddy_rag.auth.deps import (
    get_auth_db,
    get_current_active_user,
)
from bizbuddy_rag.auth.models import User
from bizbuddy_rag.auth.schemas import (
    LoginResponse,
    TokenWithUser,
    UserLogin,
    UserResponse,
)
from bizbuddy_rag.auth.security import create_access_token
from bizbuddy_rag.auth.service import UserService
from bizbuddy_rag.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: UserLogin, db: Session = Depends(get_auth_db)) -> LoginResponse:
    """用户名密码登录，返回 JWT。"""
    user = UserService.authenticate(db, payload.username, payload.password)
    if user is None:
        return LoginResponse(success=False, message="用户名或密码错误")

    token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    return LoginResponse(
        success=True,
        message="登录成功",
        data=TokenWithUser(
            access_token=token,
            token_type="bearer",
            expires_in=settings.access_token_expire_minutes * 60,
            user=UserResponse.model_validate(user),
        ),
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_active_user)) -> UserResponse:
    """获取当前登录用户信息。"""
    return UserResponse.model_validate(current_user)


@router.post("/logout")
def logout(response: Response) -> dict[str, object]:
    """清 cookie。JWT 本身无状态无法失效，客户端自行删本地 token 即可。"""
    response.delete_cookie(key="__user_token__", path="/", httponly=True)
    return {"success": True, "message": "登出成功"}
