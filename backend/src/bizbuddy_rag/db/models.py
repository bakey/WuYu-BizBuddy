"""SQLAlchemy 数据模型."""

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Column, Integer, String, Text
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
