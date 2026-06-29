"""本地 bge-m3 向量嵌入服务（用于行业知识向量检索的 query embedding）。

入库侧使用 bge-m3（1024 维）生成 chunk 向量并写入 gufei_vec.chunks.embedding。
在线查询侧必须使用同一个模型把用户问题编码成 query 向量，否则向量空间不一致、召回无意义。

模型按进程懒加载一次并长期持有：
- 全文检索 skill 不会触发模型加载，避免无谓占用内存。
- 第一次向量检索时才加载，之后复用。
"""

from threading import Lock

from bizbuddy_rag.config import settings
from bizbuddy_rag.utils.exceptions import EmbeddingError

# 进程级单例模型与加载锁，保证并发请求只加载一次模型。
_model = None
_model_lock = Lock()


def _get_model():
    """懒加载并返回进程级 bge-m3 模型单例。"""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                try:
                    # 延迟导入，避免未装 sentence-transformers 的环境（如 Windows 开发机）
                    # 在仅用全文检索时也被迫安装 torch 等重依赖。
                    from sentence_transformers import SentenceTransformer
                except ImportError as exc:
                    raise EmbeddingError(
                        "sentence-transformers 未安装，无法使用向量检索"
                    ) from exc
                _model = SentenceTransformer(
                    settings.bge_m3_model_path,
                    device=settings.bge_m3_device,
                )
    return _model


class BgeM3EmbeddingService:
    """基于本地 bge-m3 的 query 向量服务。"""

    def embed_query(self, text: str) -> list[float]:
        """把单条查询文本编码成 1024 维向量。

        Args:
            text: 用户查询文本。

        Returns:
            归一化后的向量数组。

        Raises:
            EmbeddingError: 模型缺失或编码失败。
        """
        try:
            model = _get_model()
            # normalize_embeddings=True 是 bge-m3 的硬性要求，配合 cosine 相似度。
            embedding = model.encode([text], normalize_embeddings=True)[0]
            return [float(x) for x in embedding]
        except EmbeddingError:
            raise
        except Exception as exc:
            raise EmbeddingError(f"bge-m3 query 嵌入失败: {exc}") from exc

    @staticmethod
    def to_pgvector_literal(vector: list[float]) -> str:
        """把向量转成 pgvector 可识别的字面量字符串，例如 [0.123456,...]。"""
        return "[" + ",".join(f"{x:.6f}" for x in vector) + "]"
