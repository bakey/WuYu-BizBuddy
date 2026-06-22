"""Industry knowledge skill query routes."""

from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from bizbuddy_rag.db import SessionLocal
from bizbuddy_rag.db.industry_knowledge_repository import (
    IndustryKnowledgeRepository,
)
from bizbuddy_rag.industry_models import (
    IndustryKnowledgeFeedbackRequest,
    IndustryKnowledgeFeedbackResponse,
    IndustryKnowledgeQueryRequest,
    IndustryKnowledgeQueryResponse,
    IndustryKnowledgeRetrieveRequest,
    IndustryKnowledgeRetrieveResponse,
)
from bizbuddy_rag.services.industry_knowledge import IndustryKnowledgeQueryService
from bizbuddy_rag.services.llm import LLMService
from bizbuddy_rag.utils.exceptions import RAGException

router = APIRouter(prefix="/industry-knowledge", tags=["industry-knowledge"])


def get_db() -> Iterator[Session]:
    """Yield a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/retrieve", response_model=IndustryKnowledgeRetrieveResponse)
async def retrieve_industry_knowledge(
    payload: IndustryKnowledgeRetrieveRequest,
    db: Session = Depends(get_db),
) -> IndustryKnowledgeRetrieveResponse:
    """Retrieve evidence chunks for an industry knowledge skill."""
    try:
        service = IndustryKnowledgeQueryService(
            repository=IndustryKnowledgeRepository(db)
        )
        return service.retrieve(
            skill_id=payload.skill_id,
            query=payload.query,
            top_k=payload.top_k,
        )
    except RAGException as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/query", response_model=IndustryKnowledgeQueryResponse)
async def query_industry_knowledge(
    payload: IndustryKnowledgeQueryRequest,
    db: Session = Depends(get_db),
) -> IndustryKnowledgeQueryResponse:
    """Retrieve chunks, call the LLM, and persist query references."""
    try:
        service = IndustryKnowledgeQueryService(
            repository=IndustryKnowledgeRepository(db),
            llm_service=LLMService(),
        )
        return await service.answer(
            skill_id=payload.skill_id,
            query=payload.query,
            top_k=payload.top_k,
        )
    except RAGException as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/feedback", response_model=IndustryKnowledgeFeedbackResponse)
async def create_industry_knowledge_feedback(
    payload: IndustryKnowledgeFeedbackRequest,
    db: Session = Depends(get_db),
) -> IndustryKnowledgeFeedbackResponse:
    """Store user feedback for one industry knowledge answer."""
    try:
        service = IndustryKnowledgeQueryService(
            repository=IndustryKnowledgeRepository(db)
        )
        feedback_id = service.create_feedback(
            query_log_id=payload.query_log_id,
            rating=payload.rating,
            is_helpful=payload.is_helpful,
            comment=payload.comment,
            tags=payload.tags,
        )
        return IndustryKnowledgeFeedbackResponse(feedback_id=feedback_id)
    except RAGException as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
