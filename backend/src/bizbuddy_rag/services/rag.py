"""RAG 服务."""

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.orm import Session

from bizbuddy_rag.config import settings
from bizbuddy_rag.db.repository import DocumentRepository
from bizbuddy_rag.models import RetrievedChunk
from bizbuddy_rag.services.embedding import EmbeddingService
from bizbuddy_rag.services.llm import LLMService
from bizbuddy_rag.utils.exceptions import RAGException


def _cast_metadata(value: object) -> dict[str, object] | None:
    """安全地将 metadata 列值转换为字典.

    Args:
        value: 数据库列值.

    Returns:
        字典或 None.
    """
    if isinstance(value, dict):
        return value
    return None


class RAGService:
    """检索增强生成服务."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        llm_service: LLMService,
    ) -> None:
        """初始化 RAG 服务.

        Args:
            embedding_service: 嵌入服务.
            llm_service: 大模型服务.
        """
        self.embedding_service = embedding_service
        self.llm_service = llm_service

    def _format_context(self, chunks: list[RetrievedChunk]) -> str:
        """将检索结果格式化为上下文.

        Args:
            chunks: 检索到的文档块.

        Returns:
            上下文文本.
        """
        parts: list[str] = []
        for idx, chunk in enumerate(chunks, start=1):
            parts.append(f"[{idx}] {chunk.content}")
        return "\n\n".join(parts)

    def retrieve(
        self, db: Session, query: str, top_k: int | None = None
    ) -> list[RetrievedChunk]:
        """向量检索文档.

        Args:
            db: 数据库会话.
            query: 查询文本.
            top_k: 返回数量，默认使用配置值.

        Returns:
            检索结果.

        Raises:
            RAGException: 检索失败.
        """
        top_k = top_k or settings.rag_top_k
        try:
            query_vector = self.embedding_service.embed(query)
        except Exception as exc:
            raise RAGException(f"查询嵌入失败: {exc}") from exc

        repo = DocumentRepository(db)
        rows = repo.search_similar(
            embedding=query_vector,
            top_k=top_k,
            threshold=settings.rag_similarity_threshold,
        )
        return [
            RetrievedChunk(
                content=str(doc.content),
                source=str(doc.source) if doc.source is not None else None,
                score=score,
                metadata=_cast_metadata(doc.metadata_),
            )
            for doc, score in rows
        ]

    async def answer(
        self, db: Session, prompt: str, top_k: int | None = None
    ) -> tuple[str, list[RetrievedChunk]]:
        """RAG 回答.

        Args:
            db: 数据库会话.
            prompt: 用户问题.
            top_k: 返回数量.

        Returns:
            (回答文本, 参考资料).
        """
        chunks = self.retrieve(db, prompt, top_k)
        context = self._format_context(chunks)
        answer_text = await self.llm_service.chat(prompt, context)
        return answer_text, chunks

    async def answer_stream(
        self, db: Session, prompt: str, top_k: int | None = None
    ) -> AsyncGenerator[tuple[str, Any]]:
        """RAG 流式回答.

        首先 yield 参考资料，随后 yield 每个文本片段.

        Args:
            db: 数据库会话.
            prompt: 用户问题.
            top_k: 返回数量.

        Yields:
            ("references", chunks) 或 ("delta", text).
        """
        chunks = self.retrieve(db, prompt, top_k)
        context = self._format_context(chunks)
        references: tuple[str, Any] = ("references", chunks)
        yield references
        async for delta in self.llm_service.chat_stream(prompt, context):
            delta_event: tuple[str, Any] = ("delta", delta)
            yield delta_event
