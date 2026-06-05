"""向量嵌入服务."""

from openai import OpenAI

from bizbuddy_rag.config import settings
from bizbuddy_rag.utils.exceptions import EmbeddingError


class EmbeddingService:
    """基于 OpenAI 的文本嵌入服务."""

    def __init__(self) -> None:
        """初始化 OpenAI 客户端."""
        if not settings.openai_api_key:
            raise EmbeddingError("OPENAI_API_KEY 未配置")
        self.client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,
        )
        self.model = settings.openai_embedding_model

    def embed(self, text: str) -> list[float]:
        """对单条文本生成向量.

        Args:
            text: 输入文本.

        Returns:
            向量数组.

        Raises:
            EmbeddingError: 嵌入失败.
        """
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text,
            )
            return response.data[0].embedding
        except Exception as exc:
            raise EmbeddingError(f"嵌入失败: {exc}") from exc

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量生成向量.

        Args:
            texts: 输入文本列表.

        Returns:
            向量列表.

        Raises:
            EmbeddingError: 嵌入失败.
        """
        if not texts:
            return []
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=texts,
            )
            return [item.embedding for item in response.data]
        except Exception as exc:
            raise EmbeddingError(f"批量嵌入失败: {exc}") from exc
