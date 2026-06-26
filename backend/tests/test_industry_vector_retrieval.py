"""Tests for gufei_vec vector retrieval in the repository layer.

这些测试不连真实数据库，用假的向量库 Session 验证：
- SET ivfflat.probes 是否正确内联整数；
- 检索结果是否正确映射成 IndustryKnowledgeSegment；
- score_threshold 是否按 cosine 相似度过滤；
- 未配置向量库时是否报错。
不依赖 sentence-transformers / torch。
"""

import pytest

from bizbuddy_rag.db.industry_knowledge_repository import IndustryKnowledgeRepository


class _FakeMappingResult:
    """模拟 SQLAlchemy 执行结果的 .mappings().all() 链式调用。"""

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def mappings(self) -> "_FakeMappingResult":
        return self

    def all(self) -> list[dict]:
        return self._rows


class _FakeVectorSession:
    """模拟只读向量库 Session：记录执行过的 SQL，并对 SELECT 返回预设行。"""

    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.executed_sql: list[str] = []

    def execute(self, statement, params=None):
        sql = str(statement)
        self.executed_sql.append(sql)
        # SET 语句不返回业务数据。
        if sql.strip().upper().startswith("SET"):
            return _FakeMappingResult([])
        return _FakeMappingResult(self.rows)


def _row(segment_id: str, score: float) -> dict:
    return {
        "id": segment_id,
        "subdir": "html_md",
        "source": f"/data/html_md/{segment_id}.md",
        "chunk_idx": 1,
        "n_chunks": 5,
        "txt": "生活垃圾焚烧设施运行单位应当建立运行台账。",
        "score": score,
    }


def test_retrieve_vector_maps_rows_and_filters_by_threshold() -> None:
    """高于阈值的片段被保留并正确映射，低于阈值的被过滤。"""
    session = _FakeVectorSession([_row("md5a", 0.90), _row("md5b", 0.40)])
    repo = IndustryKnowledgeRepository(db=None, vector_db=session)  # type: ignore[arg-type]

    segments = repo.retrieve_vector(
        query_vector_literal="[0.1,0.2,0.3]",
        top_k=5,
        subdir="html_md",
        probes=7,
        score_threshold=0.5,
    )

    assert len(segments) == 1
    seg = segments[0]
    assert seg.segment_id == "md5a"
    assert seg.score == 0.90
    assert seg.subdir == "html_md"
    assert seg.source == "/data/html_md/md5a.md"
    assert seg.document_id is None
    assert seg.dataset_id is None
    assert seg.metadata == {
        "source": "/data/html_md/md5a.md",
        "subdir": "html_md",
        "chunk_idx": 1,
        "n_chunks": 5,
    }
    # probes 必须以整数内联到 SET 语句中。
    assert any("SET ivfflat.probes = 7" in sql for sql in session.executed_sql)


def test_retrieve_vector_threshold_zero_keeps_all() -> None:
    """阈值为 0 时不过滤任何片段。"""
    session = _FakeVectorSession([_row("md5a", 0.90), _row("md5b", 0.10)])
    repo = IndustryKnowledgeRepository(db=None, vector_db=session)  # type: ignore[arg-type]

    segments = repo.retrieve_vector(
        query_vector_literal="[0.1]",
        top_k=5,
        subdir="html_md",
        probes=5,
        score_threshold=0.0,
    )

    assert [s.segment_id for s in segments] == ["md5a", "md5b"]


def test_retrieve_vector_without_vector_db_raises() -> None:
    """未配置向量库时应明确报错，而不是静默返回空。"""
    repo = IndustryKnowledgeRepository(db=None, vector_db=None)  # type: ignore[arg-type]
    with pytest.raises(RuntimeError):
        repo.retrieve_vector(
            query_vector_literal="[]",
            top_k=5,
            subdir="html_md",
            probes=5,
            score_threshold=0.0,
        )
