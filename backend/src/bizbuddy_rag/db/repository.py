"""文档数据仓库."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from bizbuddy_rag.db.models import Document


class DocumentRepository:
    """文档数据库操作."""

    def __init__(self, db: Session) -> None:
        """初始化仓库.

        Args:
            db: SQLAlchemy 会话.
        """
        self.db = db

    def create(
        self,
        content: str,
        embedding: list[float],
        source: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> Document:
        """创建文档记录.

        Args:
            content: 文档内容.
            embedding: 向量.
            source: 来源.
            metadata: 元数据.

        Returns:
            创建的文档.
        """
        doc = Document(
            content=content,
            embedding=embedding,
            source=source,
            metadata_=metadata,
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def get_by_id(self, doc_id: int) -> Document | None:
        """按 ID 查询文档.

        Args:
            doc_id: 文档 ID.

        Returns:
            文档或 None.
        """
        return self.db.get(Document, doc_id)

    def list_all(self, limit: int = 100, offset: int = 0) -> Sequence[Document]:
        """列出文档.

        Args:
            limit: 数量限制.
            offset: 偏移量.

        Returns:
            文档列表.
        """
        stmt = select(Document).order_by(Document.id.desc()).limit(limit).offset(offset)
        return self.db.execute(stmt).scalars().all()

    def search_similar(
        self,
        embedding: list[float],
        top_k: int = 5,
        threshold: float = 0.0,
    ) -> Sequence[tuple[Document, float]]:
        """基于向量相似度检索文档.

        Args:
            embedding: 查询向量.
            top_k: 返回数量.
            threshold: 余弦相似度阈值.

        Returns:
            (文档, 相似度) 列表.
        """
        distance = Document.embedding.cosine_distance(embedding)
        stmt = (
            select(Document, distance.label("distance"))
            .order_by(distance.asc())
            .limit(top_k)
        )
        rows = self.db.execute(stmt).all()

        results: list[tuple[Document, float]] = []
        for doc, dist in rows:
            similarity = 1.0 - float(dist)
            if similarity >= threshold:
                results.append((doc, similarity))
        return results

    def delete(self, doc_id: int) -> bool:
        """删除文档.

        Args:
            doc_id: 文档 ID.

        Returns:
            是否成功删除.
        """
        doc = self.get_by_id(doc_id)
        if doc is None:
            return False
        self.db.delete(doc)
        self.db.commit()
        return True
