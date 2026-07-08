"""Pydantic models for industry knowledge skill query APIs."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class IndustryKnowledgeRetrieveRequest(BaseModel):
    """Request body for retrieving industry knowledge segments."""

    skill_id: UUID = Field(..., description="Industry knowledge skill ID")
    query: str = Field(..., min_length=1, description="User query")
    top_k: int | None = Field(default=None, ge=1, le=20, description="Top K chunks")


class IndustryKnowledgeReference(BaseModel):
    """Retrieved evidence chunk returned by skill query APIs."""

    segment_id: str
    score: float
    chunk_index: int
    content: str
    document_id: UUID | None = None
    dataset_id: UUID | None = None
    source: str | None = None
    subdir: str | None = None
    metadata: dict[str, Any] | None = None


class IndustryKnowledgeRetrieveResponse(BaseModel):
    """Response body for retrieval-only requests."""

    items: list[IndustryKnowledgeReference]
    debug: dict[str, Any]


class IndustryKnowledgeQueryRequest(IndustryKnowledgeRetrieveRequest):
    """Request body for retrieve-and-answer requests."""

    pass


class IndustryKnowledgeQueryResponse(BaseModel):
    """Response body for industry knowledge question answering."""

    query_log_id: UUID
    answer: str
    references: list[IndustryKnowledgeReference]
    debug: dict[str, Any]


class IndustryKnowledgeFeedbackRequest(BaseModel):
    """Request body for feedback on a skill query answer."""

    query_log_id: UUID
    rating: int | None = Field(default=None, ge=1, le=5)
    is_helpful: bool | None = None
    comment: str | None = None
    tags: dict[str, Any] | None = None


class IndustryKnowledgeFeedbackResponse(BaseModel):
    """Response body after feedback is stored."""

    feedback_id: UUID
    saved: bool = True
