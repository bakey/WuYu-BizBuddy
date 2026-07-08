"""向量嵌入服务."""

import hashlib
import math
import random

from openai import OpenAI

from bizbuddy_rag.config import settings
from bizbuddy_rag.utils.exceptions import EmbeddingError


class EmbeddingService:
    """基于 OpenAI 的文本嵌入服务；mock_ai=true 时使用确定性伪向量."""

    def __init__(self) -> None:
        """初始化 OpenAI 客户端或 mock 模式."""
        self.mock = settings.mock_ai
        if not self.mock and not settings.openai_api_key:
            raise EmbeddingError("OPENAI_API_KEY 未配置")
        self.client = None
        if not self.mock:
            self.client = OpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url or None,
            )
        self.model = settings.openai_embedding_model

    def _mock_vector(self, text: str, dim: int = 1536) -> list[float]:
        """生成确定性、已归一化的伪向量.

        相同文本总是得到相同向量，方便本地无 API Key 时调试流程。
        注意：该向量没有真实语义，仅用于端到端流程验证。
        """
        seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)
        rng = random.Random(seed)
        vec = [rng.uniform(-1.0, 1.0) for _ in range(dim)]
        norm = math.sqrt(sum(x * x for x in vec))
        if norm == 0:
            norm = 1.0
        return [x / norm for x in vec]

    def embed(self, text: str) -> list[float]:
        """对单条文本生成向量.

        Args:
            text: 输入文本.

        Returns:
            向量数组.

        Raises:
            EmbeddingError: 嵌入失败.
        """
        if self.mock:
            return self._mock_vector(text)
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
        if self.mock:
            return [self._mock_vector(text) for text in texts]
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=texts,
            )
            return [item.embedding for item in response.data]
        except Exception as exc:
            raise EmbeddingError(f"批量嵌入失败: {exc}") from exc
