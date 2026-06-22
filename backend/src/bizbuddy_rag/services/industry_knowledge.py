"""Industry knowledge skill query service."""

from time import perf_counter
from typing import Any
from uuid import UUID

from bizbuddy_rag.config import settings
from bizbuddy_rag.db.industry_knowledge_repository import (
    IndustryKnowledgeRepository,
    IndustryKnowledgeSegment,
    IndustryKnowledgeSkill,
)
from bizbuddy_rag.industry_models import (
    IndustryKnowledgeReference,
    IndustryKnowledgeRetrieveResponse,
    IndustryKnowledgeQueryResponse,
)
from bizbuddy_rag.services.llm import LLMService
from bizbuddy_rag.utils.exceptions import RAGException


NO_CONTEXT_ANSWER = "当前知识库中没有检索到足够相关的资料，无法基于已有资料回答。"


class IndustryKnowledgeQueryService:
    """Online retrieval and QA flow for industry knowledge skills."""

    def __init__(
        self,
        repository: IndustryKnowledgeRepository,
        llm_service: LLMService | None = None,
    ) -> None:
        self.repository = repository
        self.llm_service = llm_service

    def retrieve(
        self,
        *,
        skill_id: UUID,
        query: str,
        top_k: int | None = None,
    ) -> IndustryKnowledgeRetrieveResponse:
        """Retrieve evidence chunks for one enabled skill."""
        skill = self._get_skill(skill_id)
        resolved_top_k = self._resolve_top_k(top_k, skill)
        segments = self._retrieve_segments(skill, query, resolved_top_k)
        references = [self._to_reference(segment) for segment in segments]
        return IndustryKnowledgeRetrieveResponse(
            items=references,
            debug=self._build_debug(
                skill=skill,
                query=query,
                top_k=resolved_top_k,
                retrieved_count=len(references),
                context_length=sum(len(item.content) for item in references),
            ),
        )

    async def answer(
        self,
        *,
        skill_id: UUID,
        query: str,
        top_k: int | None = None,
    ) -> IndustryKnowledgeQueryResponse:
        """Retrieve evidence, generate an answer, and persist query logs."""
        if self.llm_service is None:
            raise RAGException("LLM service is required for query answering")

        started_at = perf_counter()
        skill = self._get_skill(skill_id)
        resolved_top_k = self._resolve_top_k(top_k, skill)
        segments = self._retrieve_segments(skill, query, resolved_top_k)
        context = self._format_context(segments, skill.max_context_chars)
        debug = self._build_debug(
            skill=skill,
            query=query,
            top_k=resolved_top_k,
            retrieved_count=len(segments),
            context_length=len(context),
        )

        if not segments:
            answer_text = NO_CONTEXT_ANSWER
            status = "no_context"
        else:
            answer_text = await self.llm_service.chat(
                query,
                context,
                system_prompt=skill.system_prompt,
            )
            status = "success"

        latency_ms = int((perf_counter() - started_at) * 1000)
        query_log_id = self.repository.create_query_log(
            skill_id=skill.id,
            dataset_id=skill.dataset_id,
            query_text=query,
            answer_text=answer_text,
            retrieval_mode=skill.retrieval_mode,
            top_k=resolved_top_k,
            retrieved_count=len(segments),
            latency_ms=latency_ms,
            model_id=self.llm_service.model,
            status=status,
            error=None,
            debug={**debug, "latency_ms": latency_ms},
        )
        self.repository.create_query_references(query_log_id, segments)

        return IndustryKnowledgeQueryResponse(
            query_log_id=query_log_id,
            answer=answer_text,
            references=[self._to_reference(segment) for segment in segments],
            debug={**debug, "latency_ms": latency_ms},
        )

    def create_feedback(
        self,
        *,
        query_log_id: UUID,
        rating: int | None,
        is_helpful: bool | None,
        comment: str | None,
        tags: dict[str, Any] | None,
    ) -> UUID:
        """Persist feedback for one query answer."""
        return self.repository.create_feedback(
            query_log_id=query_log_id,
            rating=rating,
            is_helpful=is_helpful,
            comment=comment,
            tags=tags,
        )

    def _get_skill(self, skill_id: UUID) -> IndustryKnowledgeSkill:
        skill = self.repository.get_enabled_skill(skill_id)
        if skill is None:
            raise RAGException("Industry knowledge skill does not exist or is disabled")
        return skill

    def _resolve_top_k(
        self,
        requested_top_k: int | None,
        skill: IndustryKnowledgeSkill,
    ) -> int:
        top_k = requested_top_k or skill.top_k or settings.industry_default_top_k
        return min(top_k, settings.industry_max_top_k)

    def _retrieve_segments(
        self,
        skill: IndustryKnowledgeSkill,
        query: str,
        top_k: int,
    ) -> list[IndustryKnowledgeSegment]:
        if skill.retrieval_mode != "fulltext":
            raise RAGException(
                f"Unsupported industry retrieval mode: {skill.retrieval_mode}"
            )
        return self.repository.retrieve_fulltext(skill.dataset_id, query, top_k)

    def _format_context(
        self,
        segments: list[IndustryKnowledgeSegment],
        max_context_chars: int,
    ) -> str:
        parts: list[str] = []
        total_chars = 0
        for idx, segment in enumerate(segments, start=1):
            part = f"[{idx}] {segment.content}"
            if total_chars + len(part) > max_context_chars:
                break
            parts.append(part)
            total_chars += len(part)
        return "\n\n".join(parts)

    def _build_debug(
        self,
        *,
        skill: IndustryKnowledgeSkill,
        query: str,
        top_k: int,
        retrieved_count: int,
        context_length: int,
    ) -> dict[str, Any]:
        return {
            "skill_id": str(skill.id),
            "dataset_id": str(skill.dataset_id),
            "query": query,
            "retrieval_mode": skill.retrieval_mode,
            "top_k": top_k,
            "retrieved_count": retrieved_count,
            "context_length": context_length,
            "max_context_chars": skill.max_context_chars,
        }

    def _to_reference(
        self,
        segment: IndustryKnowledgeSegment,
    ) -> IndustryKnowledgeReference:
        return IndustryKnowledgeReference(
            segment_id=segment.segment_id,
            document_id=segment.document_id,
            dataset_id=segment.dataset_id,
            chunk_index=segment.chunk_index,
            content=segment.content,
            score=segment.score,
            metadata=segment.metadata,
        )
