"""FastAPI 路由."""

from collections.abc import AsyncGenerator, Iterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from bizbuddy_rag import __version__
from bizbuddy_rag.api.industry_knowledge_routes import (
    router as industry_knowledge_router,
)
from bizbuddy_rag.db import SessionLocal, init_db
from bizbuddy_rag.db.repository import DocumentRepository
from bizbuddy_rag.models import (
    DocumentCreate,
    DocumentOut,
    HealthResponse,
    QueryRequest,
    RAGResponse,
    RetrievedChunk,
    RetrieveRequest,
)
from bizbuddy_rag.services import EmbeddingService, LLMService, RAGService
from bizbuddy_rag.utils.exceptions import RAGException

router = APIRouter()
router.include_router(industry_knowledge_router)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """应用生命周期：启动时初始化数据库."""
    init_db()
    yield


def get_db() -> Iterator[Session]:
    """获取数据库会话依赖."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_rag_service() -> RAGService:
    """获取 RAG 服务依赖."""
    return RAGService(
        embedding_service=EmbeddingService(),
        llm_service=LLMService(),
    )


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """健康检查."""
    return HealthResponse(status="ok", version=__version__)


@router.post("/documents", response_model=DocumentOut)
async def create_document(
    payload: DocumentCreate,
    db: Session = Depends(get_db),
) -> DocumentOut:
    """上传文档并生成向量."""
    try:
        embedding_service = EmbeddingService()
        embedding = embedding_service.embed(payload.content)
    except RAGException as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    repo = DocumentRepository(db)
    doc = repo.create(
        content=payload.content,
        embedding=embedding,
        source=payload.source,
        metadata=payload.metadata,
    )
    # 不能用 DocumentOut.model_validate(doc)：SQLAlchemy 把 ``metadata`` 占用为
    # 表元数据注册表，ORM 列的真实属性名是 ``metadata_``，直接 validate 会取到
    # MetaData() 对象导致校验失败。这里显式构造。
    return DocumentOut(
        id=doc.id,
        content=doc.content,
        source=doc.source,
        metadata=doc.metadata_,
    )


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> list[DocumentOut]:
    """列出文档."""
    repo = DocumentRepository(db)
    docs = repo.list_all(limit=limit, offset=offset)
    return [
        DocumentOut(
            id=doc.id,
            content=doc.content,
            source=doc.source,
            metadata=doc.metadata_,
        )
        for doc in docs
    ]


@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: int,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    """删除文档."""
    repo = DocumentRepository(db)
    if not repo.delete(doc_id):
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"deleted": True}


@router.post("/retrieve", response_model=list[RetrievedChunk])
async def retrieve(
    payload: RetrieveRequest,
    db: Session = Depends(get_db),
    rag: RAGService = Depends(get_rag_service),
) -> list[RetrievedChunk]:
    """向量检索."""
    try:
        return rag.retrieve(db, payload.query, top_k=payload.top_k)
    except RAGException as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/query", response_model=RAGResponse)
async def query(
    payload: QueryRequest,
    db: Session = Depends(get_db),
    rag: RAGService = Depends(get_rag_service),
) -> RAGResponse:
    """RAG 问答."""
    try:
        answer, refs = await rag.answer(db, payload.prompt, top_k=payload.top_k)
    except RAGException as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return RAGResponse(answer=answer, references=refs)


async def _stream_answer(
    rag: RAGService,
    db: Session,
    payload: QueryRequest,
) -> AsyncGenerator[str]:
    """流式生成 SSE 数据."""
    import json

    try:
        async for event, data in rag.answer_stream(
            db, payload.prompt, top_k=payload.top_k
        ):
            if event == "references":
                chunks: list[RetrievedChunk] = data
                refs = [ref.model_dump() for ref in chunks]
                yield f"event: references\ndata: {json.dumps(refs, ensure_ascii=False)}\n\n"
            elif event == "delta":
                delta: str = data
                yield f"event: delta\ndata: {json.dumps({'delta': delta}, ensure_ascii=False)}\n\n"
        yield "event: done\ndata: [DONE]\n\n"
    except RAGException as exc:
        yield f"event: error\ndata: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"


@router.post("/query/stream")
async def query_stream(
    payload: QueryRequest,
    db: Session = Depends(get_db),
    rag: RAGService = Depends(get_rag_service),
) -> StreamingResponse:
    """RAG 流式问答 (SSE)."""
    return StreamingResponse(
        _stream_answer(rag, db, payload),
        media_type="text/event-stream",
    )
