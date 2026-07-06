"""FastAPI 依赖：从请求中解析当前用户。

支持两种来源，与 rswaste-platform 一致：
1. `Authorization: Bearer <jwt>`（首选）
2. Cookie `__user_token__`（备用，跨系统 SSO 使用）
"""

from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from bizbuddy_rag.auth.models import User
from bizbuddy_rag.auth.security import verify_token
from bizbuddy_rag.auth.service import UserService
from bizbuddy_rag.db import AuthSessionLocal


def get_auth_db() -> Iterator[Session]:
    """buildingai 库的会话依赖。未配置时立刻 503。"""
    if AuthSessionLocal is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AUTH_DATABASE_URL 未配置，认证功能不可用",
        )
    db = AuthSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _extract_token(
    authorization: str | None,
    cookie_token: str | None,
) -> str | None:
    """从 header/cookie 里拿到 raw token 字符串。"""
    token: str | None = None
    if authorization:
        token = authorization.strip()
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
    if not token and cookie_token:
        token = cookie_token.strip()
    return token or None


def get_optional_user(
    authorization: str | None = Header(default=None),
    cookie_token: str | None = Cookie(default=None, alias="__user_token__"),
    db: Session = Depends(get_auth_db),
) -> User | None:
    """如果带了合法 token 就返回 User，否则返回 None，不抛异常。

    用于「登录可选」的接口（例如可匿名使用但登录后附加个性化的接口）。
    """
    token = _extract_token(authorization, cookie_token)
    if token is None:
        return None
    payload = verify_token(token)
    if payload is None:
        return None
    user_id_raw = payload.get("sub") or payload.get("id")
    if not user_id_raw:
        return None
    try:
        user_id = UUID(str(user_id_raw))
    except ValueError:
        return None
    user = UserService.get_by_id(db, user_id)
    if user is None or not user.is_active:
        return None
    return user


def get_current_user(
    authorization: str | None = Header(default=None),
    cookie_token: str | None = Cookie(default=None, alias="__user_token__"),
    db: Session = Depends(get_auth_db),
) -> User:
    """必需登录：未登录 401，用户禁用 403。"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="未登录或登录已过期",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = _extract_token(authorization, cookie_token)
    if token is None:
        raise credentials_exception
    payload = verify_token(token)
    if payload is None:
        raise credentials_exception
    user_id_raw = payload.get("sub") or payload.get("id")
    if not user_id_raw:
        raise credentials_exception
    try:
        user_id = UUID(str(user_id_raw))
    except ValueError as exc:
        raise credentials_exception from exc
    user = UserService.get_by_id(db, user_id)
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )
    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """语义化封装，供路由用。"""
    return current_user
