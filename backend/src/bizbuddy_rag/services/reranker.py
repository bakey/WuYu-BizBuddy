"""本地 bge-reranker 重排服务（cross-encoder）。

向量召回（bi-encoder）速度快但精度有限：IVFFlat 在低 probes 下召回不全，
且语义相近不等于真正相关。重排阶段用 cross-encoder 对 (query, chunk) 成对打分，
能显著提升 top_k 的精确性——对政策法规这种"必须命中正确依据"的场景收益最大。

典型用法：向量先多召回 over_fetch_k 条候选，再用本服务重排，截断到 top_k。

模型按进程懒加载一次并长期持有：未启用重排的 skill 不会触发加载。
"""

from threading import Lock

from bizbuddy_rag.config import settings
from bizbuddy_rag.utils.exceptions import RAGException

# 进程级单例模型与加载锁。
_model = None
_model_lock = Lock()


def _get_model():
    """懒加载并返回进程级 bge-reranker cross-encoder 单例。"""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                try:
                    # 延迟导入，避免未启用重排的环境被迫加载重依赖。
                    from sentence_transformers import CrossEncoder
                except ImportError as exc:
                    raise RAGException(
                        "sentence-transformers 未安装，无法使用重排"
                    ) from exc
                _model = CrossEncoder(
                    settings.bge_reranker_model_path,
                    device=settings.bge_reranker_device,
                )
    return _model


class BgeRerankerService:
    """基于本地 bge-reranker 的重排服务。"""

    def rerank(self, query: str, passages: list[str]) -> list[float]:
        """对 (query, passage) 成对打分，返回与 passages 等长的相关性分数列表。

        Args:
            query: 用户查询文本。
            passages: 候选片段正文列表。

        Returns:
            每个候选的重排分数，顺序与输入 passages 一致。

        Raises:
            RAGException: 模型缺失或打分失败。
        """
        if not passages:
            return []
        try:
            model = _get_model()
            pairs = [[query, passage] for passage in passages]
            scores = model.predict(pairs)
            return [float(score) for score in scores]
        except RAGException:
            raise
        except Exception as exc:
            raise RAGException(f"bge-reranker 重排失败: {exc}") from exc
