"""用户查询与登录业务逻辑。

BizBuddy 只对 buildingai.public.user 做只读 + 更新 last_login_at；
不新建 / 删除用户，避免与 rswaste-platform 的用户管理产生冲突。
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from bizbuddy_rag.auth.models import User
from bizbuddy_rag.auth.security import verify_password


class UserService:
    """用户查询与认证服务。"""

    @staticmethod
    def get_by_id(db: Session, user_id: UUID) -> User | None:
        return (
            db.query(User)
            .filter(User.id == user_id, User.deleted_at.is_(None))
            .first()
        )

    @staticmethod
    def get_by_username(db: Session, username: str) -> User | None:
        return (
            db.query(User)
            .filter(User.username == username, User.deleted_at.is_(None))
            .first()
        )

    @staticmethod
    def authenticate(db: Session, username: str, password: str) -> User | None:
        """校验用户名密码，成功返回 User 并更新 last_login_at。"""
        user = UserService.get_by_username(db, username)
        if user is None or not user.is_active:
            return None
        if not verify_password(password, user.password):
            return None
        user.last_login_at = datetime.now(UTC)
        db.commit()
        return user
