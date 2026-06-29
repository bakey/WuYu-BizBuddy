"""SQLAlchemy 数据模型."""

from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """ORM 基类."""

    pass


class Document(Base):
    """文档表，存储原始内容和向量."""

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content = Column(Text, nullable=False, comment="原始文档内容")
    embedding = Column(Vector(1536), nullable=True, comment="向量表示")
    source = Column(String(512), nullable=True, comment="文档来源")
    metadata_ = Column("metadata", JSON, nullable=True, comment="附加元数据")


class ChatTask(Base):
    """聊天任务历史表."""

    __tablename__ = "chat_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(512), nullable=False, comment="任务标题")
    meta = Column(String(255), nullable=True, comment="任务副标题")
    pin = Column(String(50), nullable=False, default="", comment="置顶标识样式")
    pinned = Column(Boolean, nullable=False, default=False, comment="是否置顶")
    active = Column(Boolean, nullable=False, default=False, comment="是否当前激活")
    agent_name = Column(String(255), nullable=True, comment="Agent 名称")
    agent_icon = Column(String(50), nullable=True, comment="Agent 图标")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        comment="创建时间",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        comment="更新时间",
    )


class Agent(Base):
    """Agent 表."""

    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True, comment="Agent 名称")
    icon = Column(String(50), nullable=False, comment="图标")
    bg = Column(String(100), nullable=False, comment="背景色")
    color = Column(String(100), nullable=False, comment="文字颜色")
    desc = Column(Text, nullable=False, comment="描述")
    skills = Column(JSON, nullable=False, default=list, comment="技能列表")
    users = Column(String(50), nullable=False, default="0", comment="使用人数")
    rating = Column(String(10), nullable=False, default="0.0", comment="评分")
    featured = Column(Boolean, nullable=False, default=False, comment="是否推荐")
    category = Column(String(100), nullable=False, comment="分类")
    tag_label = Column(String(50), nullable=True, comment="标签文本")
    tag_cls = Column(String(50), nullable=True, comment="标签样式类")
    source = Column(String(50), nullable=False, default="官方 Agent", comment="来源")
    enabled = Column(Boolean, nullable=False, default=True, comment="是否启用")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        comment="创建时间",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        comment="更新时间",
    )
