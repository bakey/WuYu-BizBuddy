"""用户 ORM。

映射到 buildingai 数据库的 public.user 表，字段结构与 rswaste-platform 中
app/models/user.py 保持一致。BizBuddy 只做读 + 校验密码 + 更新登录时间，
用户创建/删除仍由 rswaste 或数据库管理员完成。
"""

from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

# 独立 Base，隔离 auth 用户表与 bizbuddy 业务表；避免 create_all 误建。
AuthBase = declarative_base()


class User(AuthBase):
    """buildingai.public.user。"""

    __tablename__ = "user"
    __table_args__ = {"schema": "public"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String, nullable=False, unique=True)
    password = Column(String, nullable=False)
    nickname = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    avatar = Column(String, nullable=True)
    source = Column(String, nullable=False, default="0")

    status = Column(Integer, nullable=False, default=1)
    is_root = Column(String, nullable=False, default="0")

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    @property
    def is_active(self) -> bool:
        """未删除且 status=1 视为激活。"""
        return self.status == 1 and self.deleted_at is None

    @property
    def is_superuser(self) -> bool:
        """is_root='1' 为超级用户。"""
        return self.is_root == "1"

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} username={self.username!r}>"
