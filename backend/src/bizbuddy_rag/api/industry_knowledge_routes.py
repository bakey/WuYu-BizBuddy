"""Industry knowledge skill query routes.

`/retrieve`、`/query`、`/feedback` 三个接口进入 service 的方式都一样：
FastAPI 收到 HTTP 请求后，先把请求体解析成 payload，
再通过 Depends(get_db) 注入数据库会话 db，
然后在接口函数里手动创建 IndustryKnowledgeQueryService 并调用对应方法。
异常由路由层捕获并转成 HTTP 错误返回。
"""

from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from bizbuddy_rag.db import GufeiVecSessionLocal, SessionLocal
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
from bizbuddy_rag.services.bge_embedding import BgeM3EmbeddingService
from bizbuddy_rag.services.industry_knowledge import IndustryKnowledgeQueryService
from bizbuddy_rag.services.llm import LLMService
from bizbuddy_rag.services.reranker import BgeRerankerService
from bizbuddy_rag.utils.exceptions import RAGException

router = APIRouter(prefix="/industry-knowledge", tags=["industry-knowledge"])


def get_db() -> Iterator[Session]:
    """为每个请求提供一个数据库 Session，请求结束后自动关闭."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_vector_db() -> Iterator[Session | None]:
    """为每个请求提供一个 gufei_vec 向量库 Session；未配置时返回 None."""
    if GufeiVecSessionLocal is None:
        yield None
        return
    db = GufeiVecSessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/retrieve", response_model=IndustryKnowledgeRetrieveResponse)
async def retrieve_industry_knowledge(
    payload: IndustryKnowledgeRetrieveRequest,
    db: Session = Depends(get_db),
    vector_db: Session | None = Depends(get_vector_db),
) -> IndustryKnowledgeRetrieveResponse:
    """只检索证据片段，不调用大模型生成回答."""
    try:
        service = IndustryKnowledgeQueryService(
            repository=IndustryKnowledgeRepository(db, vector_db=vector_db),
            embedding_service=BgeM3EmbeddingService(),
            reranker_service=BgeRerankerService(),
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
    vector_db: Session | None = Depends(get_vector_db),
) -> IndustryKnowledgeQueryResponse:
    """先检索证据，再调用大模型生成回答，并保存引用记录."""
    try:
        service = IndustryKnowledgeQueryService(
            repository=IndustryKnowledgeRepository(db, vector_db=vector_db),
            llm_service=LLMService(),
            embedding_service=BgeM3EmbeddingService(),
            reranker_service=BgeRerankerService(),
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
    """保存用户对某次行业知识回答的反馈."""
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
