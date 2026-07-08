"""JWT + bcrypt 工具函数。

实现刻意与 WuYu-rswaste-platform 保持字节级一致：
- HS256 + settings.secret_key
- payload {"sub": str(user.id)} 或 {"id": str(user.id)}
- passlib bcrypt，密码截断到 72 字节

这样两边签发的 token 互相能验，用户表也可以共用 bcrypt 哈希。
"""

from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from bizbuddy_rag.config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验明文密码是否匹配 bcrypt 哈希。bcrypt 最多 72 字节，超出截断。"""
    return _pwd_context.verify(plain_password[:72], hashed_password)


def get_password_hash(password: str) -> str:
    """给明文密码生成 bcrypt 哈希。"""
    return _pwd_context.hash(password[:72])


def create_access_token(
    data: dict, expires_delta: timedelta | None = None
) -> str:
    """签发 JWT access token。"""
    to_encode = data.copy()
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    to_encode["exp"] = datetime.now(UTC) + expires_delta
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def verify_token(token: str) -> dict | None:
    """验证 JWT token，返回 payload dict；失败返回 None。"""
    try:
        return jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
    except JWTError:
        return None
