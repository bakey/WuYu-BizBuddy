"""Database access for industry knowledge skill query."""

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
    dataset_id: UUID
    retrieval_mode: str
    top_k: int
    max_context_chars: int
    system_prompt: str | None


@dataclass(frozen=True)
class IndustryKnowledgeSegment:
    """Retrieved chunk from datasets_segments."""

    segment_id: UUID
    document_id: UUID
    dataset_id: UUID
    chunk_index: int
    content: str
    score: float
    metadata: dict[str, Any] | None


class IndustryKnowledgeRepository:
    """Repository for skill query configuration, retrieval, logs, and feedback."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_enabled_skill(self, skill_id: UUID) -> IndustryKnowledgeSkill | None:
        """Return enabled skill config by ID."""
        row = self.db.execute(
            text(
                """
                SELECT
                  id,
                  dataset_id,
                  retrieval_mode,
                  top_k,
                  max_context_chars,
                  system_prompt
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
        )

    def retrieve_fulltext(
        self,
        dataset_id: UUID,
        query: str,
        top_k: int,
    ) -> list[IndustryKnowledgeSegment]:
        """Retrieve chunks with PostgreSQL full-text search."""
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
                segment_id=row["segment_id"],
                document_id=row["document_id"],
                dataset_id=row["dataset_id"],
                chunk_index=row["chunk_index"],
                content=row["content"],
                score=float(row["score"]),
                metadata=row["metadata"] if isinstance(row["metadata"], dict) else None,
            )
            for row in rows
        ]

    def create_query_log(
        self,
        *,
        skill_id: UUID,
        dataset_id: UUID,
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
        """Persist one query execution log and return its ID."""
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
        """Persist retrieved evidence chunks for one query log."""
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
                        segment.metadata or {}, ensure_ascii=False
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
        """Persist user feedback for one query log."""
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
