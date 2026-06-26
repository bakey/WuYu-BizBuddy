"""Tests for vector retrieval + rerank orchestration in the service layer.

用假的 repository / embedding / reranker 验证：
- 启用重排时按 over_fetch_k 多召回；
- 重排后按重排分数重新排序并截断到 top_k；
- score 被替换为重排分数，原 cosine 分数保留在 metadata.vector_score。
不连数据库，但会导入 service 模块（依赖项目已有的 openai 包）。
"""

from uuid import uuid4

from bizbuddy_rag.db.industry_knowledge_repository import (
    IndustryKnowledgeSegment,
    IndustryKnowledgeSkill,
)
from bizbuddy_rag.services.industry_knowledge import IndustryKnowledgeQueryService


class _FakeRepository:
    """记录 retrieve_vector 收到的 top_k，并返回预设候选片段。"""

    def __init__(self, segments: list[IndustryKnowledgeSegment]) -> None:
        self._segments = segments
        self.requested_top_k: int | None = None

    def retrieve_vector(
        self, *, query_vector_literal, top_k, subdir, probes, score_threshold, min_chars=0
    ):
        self.requested_top_k = top_k
        return list(self._segments)


class _FakeEmbedding:
    def embed_query(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]

    @staticmethod
    def to_pgvector_literal(vector: list[float]) -> str:
        return "[0.1,0.2,0.3]"


class _FakeReranker:
    """按预设分数表对 passages 打分（顺序与输入一致）。"""

    def __init__(self, scores: list[float]) -> None:
        self._scores = scores

    def rerank(self, query: str, passages: list[str]) -> list[float]:
        return self._scores[: len(passages)]


def _segment(seg_id: str, score: float) -> IndustryKnowledgeSegment:
    return IndustryKnowledgeSegment(
        segment_id=seg_id,
        content=f"content-{seg_id}",
        score=score,
        chunk_index=1,
        subdir="html_md",
        metadata={"subdir": "html_md"},
    )


def _vector_skill() -> IndustryKnowledgeSkill:
    return IndustryKnowledgeSkill(
        id=uuid4(),
        retrieval_mode="vector",
        top_k=2,
        max_context_chars=6000,
        system_prompt=None,
        vector_subdir="html_md",
        rerank_enabled=True,
        rerank_over_fetch_k=10,
    )


def test_rerank_reorders_and_truncates_to_top_k() -> None:
    """重排按新分数排序并截断到 top_k，over-fetch 生效，分数写回正确。"""
    candidates = [_segment("s1", 0.90), _segment("s2", 0.80), _segment("s3", 0.70)]
    repo = _FakeRepository(candidates)
    # 重排分数让 s2 最高、s3 次之、s1 最低。
    reranker = _FakeReranker([0.1, 0.9, 0.5])
    service = IndustryKnowledgeQueryService(
        repository=repo,  # type: ignore[arg-type]
        embedding_service=_FakeEmbedding(),  # type: ignore[arg-type]
        reranker_service=reranker,  # type: ignore[arg-type]
    )

    segments = service._retrieve_segments(_vector_skill(), "台账要求", top_k=2)

    # 启用重排时应按 over_fetch_k=10 多召回。
    assert repo.requested_top_k == 10
    # 重排后取 top_k=2，顺序应为 s2、s3。
    assert [s.segment_id for s in segments] == ["s2", "s3"]
    # score 被替换为重排分数。
    assert segments[0].score == 0.9
    assert segments[1].score == 0.5
    # 原 cosine 分数保留在 metadata。
    assert segments[0].metadata["vector_score"] == 0.80
    assert segments[0].metadata["rerank_score"] == 0.9


def test_rerank_disabled_keeps_cosine_order() -> None:
    """未启用重排时按 cosine 顺序截断到 top_k，且不 over-fetch。"""
    candidates = [_segment("s1", 0.90), _segment("s2", 0.80), _segment("s3", 0.70)]
    repo = _FakeRepository(candidates)
    skill = _vector_skill()
    # 关闭重排。
    skill = IndustryKnowledgeSkill(
        id=skill.id,
        retrieval_mode="vector",
        top_k=2,
        max_context_chars=6000,
        system_prompt=None,
        vector_subdir="html_md",
        rerank_enabled=False,
        rerank_over_fetch_k=10,
    )
    service = IndustryKnowledgeQueryService(
        repository=repo,  # type: ignore[arg-type]
        embedding_service=_FakeEmbedding(),  # type: ignore[arg-type]
        reranker_service=_FakeReranker([0.1, 0.9, 0.5]),  # type: ignore[arg-type]
    )

    segments = service._retrieve_segments(skill, "台账要求", top_k=2)

    # 未启用重排，但默认开启来源去重(max_per_source=3>0)也会触发 over-fetch。
    assert repo.requested_top_k == 10
    # 候选 source 均为 None，不被去重，按 cosine 顺序截断到 top_k。
    assert [s.segment_id for s in segments] == ["s1", "s2"]


def test_dedupe_by_source_caps_fragments_from_same_doc() -> None:
    """同一来源的多个碎片应被去重，按默认 max_per_source=3 截断。"""
    same = "/data/html_md/同一篇.md"
    candidates = [
        IndustryKnowledgeSegment(
            segment_id=f"f{i}",
            content=f"片段{i}",
            score=0.9 - i * 0.01,
            chunk_index=i,
            source=same,
        )
        for i in range(5)
    ]
    repo = _FakeRepository(candidates)
    skill = IndustryKnowledgeSkill(
        id=uuid4(),
        retrieval_mode="vector",
        top_k=5,
        max_context_chars=6000,
        system_prompt=None,
        vector_subdir="html_md",
        rerank_enabled=False,
    )
    service = IndustryKnowledgeQueryService(
        repository=repo,  # type: ignore[arg-type]
        embedding_service=_FakeEmbedding(),  # type: ignore[arg-type]
    )

    segments = service._retrieve_segments(skill, "台账要求", top_k=5)

    # 同一 source 默认最多保留 3 条。
    assert len(segments) == 3
    assert [s.segment_id for s in segments] == ["f0", "f1", "f2"]
