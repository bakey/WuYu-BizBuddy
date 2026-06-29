"""Database access for industry knowledge skill query.

涉及的表：
- industry_knowledge_skills：查 skill 配置
- datasets_segments：查知识 chunks（全文检索）
- industry_knowledge_query_logs：写一次问答执行日志
- industry_knowledge_query_references：写这次问答引用了哪些 chunks
- industry_knowledge_feedback：写用户对这次问答的反馈
"""

import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from bizbuddy_rag.config import settings


@dataclass(frozen=True)
class IndustryKnowledgeSkill:
    """Skill configuration loaded from industry_knowledge_skills."""

    id: UUID
    retrieval_mode: str
    top_k: int
    max_context_chars: int
    system_prompt: str | None
    dataset_id: UUID | None = None
    vector_subdir: str | None = None
    score_threshold: float | None = None
    ivfflat_probes: int | None = None
    rerank_enabled: bool | None = None
    rerank_over_fetch_k: int | None = None


@dataclass(frozen=True)
class IndustryKnowledgeSegment:
    """Retrieved chunk from datasets_segments (fulltext) or gufei_vec (vector)."""

    segment_id: str
    content: str
    score: float
    chunk_index: int
    document_id: UUID | None = None
    dataset_id: UUID | None = None
    source: str | None = None
    subdir: str | None = None
    metadata: dict[str, Any] | None = None


class IndustryKnowledgeRepository:
    """Repository for skill query configuration, retrieval, logs, and feedback."""

    def __init__(self, db: Session, vector_db: Session | None = None) -> None:
        """初始化 repository.

        Args:
            db: 业务库 Session（skill、日志、引用、反馈）。
            vector_db: gufei_vec 向量库 Session；仅向量检索使用。
        """
        self.db = db
        self.vector_db = vector_db

    def get_enabled_skill(self, skill_id: UUID) -> IndustryKnowledgeSkill | None:
        """根据 skill_id 查询已启用的行业知识技能配置."""
        row = self.db.execute(
            text(
                """
                SELECT
                  id,
                  dataset_id,
                  retrieval_mode,
                  top_k,
                  max_context_chars,
                  system_prompt,
                  score_threshold,
                  vector_subdir,
                  ivfflat_probes,
                  rerank_enabled,
                  rerank_over_fetch_k
                FROM wuyu_industry.industry_knowledge_skills
                WHERE id = :skill_id
                  AND enabled = true
                """
            ),
            {"skill_id": skill_id},
        ).mappings().first()

        if row is None:
            return None

        return IndustryKnowledgeSkill(
            id=row["id"],
            dataset_id=row["dataset_id"],
            retrieval_mode=row["retrieval_mode"],
            top_k=row["top_k"],
            max_context_chars=row["max_context_chars"],
            system_prompt=row["system_prompt"],
            vector_subdir=row["vector_subdir"],
            score_threshold=row["score_threshold"],
            ivfflat_probes=row["ivfflat_probes"],
            rerank_enabled=row["rerank_enabled"],
            rerank_over_fetch_k=row["rerank_over_fetch_k"],
        )

    def retrieve_fulltext(
        self,
        dataset_id: UUID,
        query: str,
        top_k: int,
    ) -> list[IndustryKnowledgeSegment]:
        """在指定数据集中用 PostgreSQL 全文检索查找相关 chunks."""
        rows = self.db.execute(
            text(
                """
                SELECT
                  id AS segment_id,
                  document_id,
                  dataset_id,
                  chunk_index,
                  content,
                  metadata,
                  ts_rank(
                    to_tsvector(CAST(:fulltext_config AS regconfig), content),
                    plainto_tsquery(CAST(:fulltext_config AS regconfig), :query)
                  ) AS score
                FROM public.datasets_segments
                WHERE dataset_id = :dataset_id
                  AND enabled = 1
                  AND status = 'completed'
                  AND to_tsvector(CAST(:fulltext_config AS regconfig), content)
                    @@ plainto_tsquery(CAST(:fulltext_config AS regconfig), :query)
                ORDER BY score DESC, chunk_index ASC
                LIMIT :top_k
                """
            ),
            {
                "dataset_id": dataset_id,
                "query": query,
                "top_k": top_k,
                "fulltext_config": settings.industry_fulltext_config,
            },
        ).mappings().all()

        return [
            IndustryKnowledgeSegment(
                segment_id=str(row["segment_id"]),
                content=row["content"],
                score=float(row["score"]),
                chunk_index=row["chunk_index"],
                document_id=row["document_id"],
                dataset_id=row["dataset_id"],
                metadata=row["metadata"] if isinstance(row["metadata"], dict) else None,
            )
            for row in rows
        ]

    def retrieve_vector(
        self,
        *,
        query_vector_literal: str,
        top_k: int,
        subdir: str | None,
        probes: int,
        score_threshold: float,
        min_chars: int = 0,
    ) -> list[IndustryKnowledgeSegment]:
        """在 gufei_vec.chunks 上做 bge-m3 + IVFFlat 余弦相似度检索."""
        if self.vector_db is None:
            raise RuntimeError("向量库 gufei_vec 未配置，无法执行向量检索")

        self.vector_db.execute(text(f"SET ivfflat.probes = {int(probes)}"))

        rows = self.vector_db.execute(
            text(
                """
                SELECT
                  id,
                  subdir,
                  source,
                  chunk_idx,
                  n_chunks,
                  txt,
                  1 - ((embedding::halfvec(1024)) <=> CAST(:qvec AS halfvec(1024)))
                    AS score
                FROM chunks
                WHERE (:subdir IS NULL OR subdir = :subdir)
                  AND char_length(txt) >= :min_chars
                ORDER BY (embedding::halfvec(1024)) <=> CAST(:qvec AS halfvec(1024))
                LIMIT :top_k
                """
            ),
            {
                "qvec": query_vector_literal,
                "subdir": subdir,
                "top_k": top_k,
                "min_chars": min_chars,
            },
        ).mappings().all()

        segments: list[IndustryKnowledgeSegment] = []
        for row in rows:
            score = float(row["score"])
            if score_threshold and score < score_threshold:
                continue
            segments.append(
                IndustryKnowledgeSegment(
                    segment_id=str(row["id"]),
                    content=row["txt"],
                    score=score,
                    chunk_index=row["chunk_idx"],
                    source=row["source"],
                    subdir=row["subdir"],
                    metadata={
                        "source": row["source"],
                        "subdir": row["subdir"],
                        "chunk_idx": row["chunk_idx"],
                        "n_chunks": row["n_chunks"],
                    },
                )
            )
        return segments

    def create_query_log(
        self,
        *,
        skill_id: UUID,
        dataset_id: UUID | None,
        query_text: str,
        answer_text: str,
        retrieval_mode: str,
        top_k: int,
        retrieved_count: int,
        latency_ms: int | None,
        model_id: str | None,
        status: str,
        error: str | None,
        debug: dict[str, Any],
    ) -> UUID:
        """写入一次问答执行日志，并返回新创建的 query_log_id."""
        row = self.db.execute(
            text(
                """
                INSERT INTO wuyu_industry.industry_knowledge_query_logs (
                  skill_id,
                  dataset_id,
                  query_text,
                  answer_text,
                  retrieval_mode,
                  top_k,
                  retrieved_count,
                  latency_ms,
                  model_id,
                  status,
                  error,
                  debug
                )
                VALUES (
                  :skill_id,
                  :dataset_id,
                  :query_text,
                  :answer_text,
                  :retrieval_mode,
                  :top_k,
                  :retrieved_count,
                  :latency_ms,
                  :model_id,
                  :status,
                  :error,
                  CAST(:debug AS jsonb)
                )
                RETURNING id
                """
            ),
            {
                "skill_id": skill_id,
                "dataset_id": dataset_id,
                "query_text": query_text,
                "answer_text": answer_text,
                "retrieval_mode": retrieval_mode,
                "top_k": top_k,
                "retrieved_count": retrieved_count,
                "latency_ms": latency_ms,
                "model_id": model_id,
                "status": status,
                "error": error,
                "debug": json.dumps(debug, ensure_ascii=False),
            },
        ).first()
        self.db.commit()
        return row[0]

    def create_query_references(
        self,
        query_log_id: UUID,
        references: list[IndustryKnowledgeSegment],
    ) -> None:
        """把一次问答引用到的知识片段批量写入引用表."""
        if not references:
            return

        self.db.execute(
            text(
                """
                INSERT INTO wuyu_industry.industry_knowledge_query_references (
                  query_log_id,
                  segment_id,
                  document_id,
                  dataset_id,
                  reference_rank,
                  score,
                  content_snapshot,
                  metadata_snapshot
                )
                VALUES (
                  :query_log_id,
                  :segment_id,
                  :document_id,
                  :dataset_id,
                  :reference_rank,
                  :score,
                  :content_snapshot,
                  CAST(:metadata_snapshot AS jsonb)
                )
                """
            ),
            [
                {
                    "query_log_id": query_log_id,
                    "segment_id": segment.segment_id,
                    "document_id": segment.document_id,
                    "dataset_id": segment.dataset_id,
                    "reference_rank": rank,
                    "score": segment.score,
                    "content_snapshot": segment.content,
                    "metadata_snapshot": json.dumps(
                        {
                            **(segment.metadata or {}),
                            "source": segment.source,
                            "subdir": segment.subdir,
                            "chunk_index": segment.chunk_index,
                        },
                        ensure_ascii=False,
                    ),
                }
                for rank, segment in enumerate(references, start=1)
            ],
        )
        self.db.commit()

    def create_feedback(
        self,
        *,
        query_log_id: UUID,
        rating: int | None,
        is_helpful: bool | None,
        comment: str | None,
        tags: dict[str, Any] | None,
    ) -> UUID:
        """写入用户对某次问答的反馈，并返回新创建的 feedback_id."""
        row = self.db.execute(
            text(
                """
                INSERT INTO wuyu_industry.industry_knowledge_feedback (
                  query_log_id,
                  rating,
                  is_helpful,
                  comment,
                  tags
                )
                VALUES (
                  :query_log_id,
                  :rating,
                  :is_helpful,
                  :comment,
                  CAST(:tags AS jsonb)
                )
                RETURNING id
                """
            ),
            {
                "query_log_id": query_log_id,
                "rating": rating,
                "is_helpful": is_helpful,
                "comment": comment,
                "tags": json.dumps(tags or {}, ensure_ascii=False),
            },
        ).first()
        self.db.commit()
        return row[0]
