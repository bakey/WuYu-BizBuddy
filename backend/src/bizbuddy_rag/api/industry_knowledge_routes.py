"""
`/retrieve、/query、/feedback 三个接口如何进入 service，异常如何转成 HTTP 返回

这三个接口进入 service 的方式都一样：
    FastAPI 收到 HTTP 请求后，先把请求体解析成 payload，
    再通过 Depends(get_db) 注入数据库会话 db，
    然后在接口函数里手动创建 IndustryKnowledgeQueryService 并调用对应方法。
"""

# 模块说明：这里集中定义行业知识库相关的接口路由。
"""Industry knowledge skill query routes."""

# 导入 Iterator，用来标注 get_db 这种生成器函数的返回类型。
from collections.abc import Iterator

# 导入 FastAPI 路由、依赖注入和 HTTP 异常工具。
from fastapi import APIRouter, Depends, HTTPException
# 导入 SQLAlchemy 的数据库会话类型，用于类型标注。
from sqlalchemy.orm import Session

# 导入本项目封装好的数据库 Session 工厂（业务库 + 向量库）。
from bizbuddy_rag.db import GufeiVecSessionLocal, SessionLocal
from bizbuddy_rag.db.industry_knowledge_repository import (
    # 导入行业知识库的数据访问层，负责读写数据库。
    IndustryKnowledgeRepository,
)
# 导入本地 bge-m3 向量服务，供向量检索生成 query 向量。
from bizbuddy_rag.services.bge_embedding import BgeM3EmbeddingService
# 导入本地 bge-reranker 重排服务，供向量多召回后精排。
from bizbuddy_rag.services.reranker import BgeRerankerService
from bizbuddy_rag.industry_models import (
    # 反馈接口的请求体模型。
    IndustryKnowledgeFeedbackRequest,
    # 反馈接口的响应体模型。
    IndustryKnowledgeFeedbackResponse,
    # 问答接口的请求体模型。
    IndustryKnowledgeQueryRequest,
    # 问答接口的响应体模型。
    IndustryKnowledgeQueryResponse,
    # 检索接口的请求体模型。
    IndustryKnowledgeRetrieveRequest,
    # 检索接口的响应体模型。
    IndustryKnowledgeRetrieveResponse,
)
# 导入业务服务，封装检索、问答和反馈逻辑。
from bizbuddy_rag.services.industry_knowledge import IndustryKnowledgeQueryService
# 导入大模型服务，供问答接口生成回答。
from bizbuddy_rag.services.llm import LLMService
# 导入项目自定义异常，用于转换成 HTTP 错误。
from bizbuddy_rag.utils.exceptions import RAGException

# 创建路由分组，统一加上接口前缀和文档标签。
router = APIRouter(prefix="/industry-knowledge", tags=["industry-knowledge"])


# 函数作用：作为 FastAPI 的数据库依赖，为每个请求创建一个数据库 Session，并在请求结束后自动关闭。
def get_db() -> Iterator[Session]:
    # 函数说明：为每个请求提供一个数据库连接会话。
    """Yield a database session."""
    # 创建一个新的数据库 Session。
    db = SessionLocal()
    try:
        # 把 Session 交给 FastAPI 的依赖注入系统和接口函数使用。
        yield db
    finally:
        # 请求处理结束后关闭 Session，释放数据库连接。
        db.close()


# 函数作用：为每个请求提供一个 gufei_vec 向量库 Session；未配置向量库时返回 None。
def get_vector_db() -> Iterator[Session | None]:
    """Yield a gufei_vec session, or None when vector DB is not configured."""
    # 向量库未配置时直接产出 None，全文检索请求不受影响。
    if GufeiVecSessionLocal is None:
        yield None
        return
    # 创建向量库 Session。
    db = GufeiVecSessionLocal()
    try:
        # 把向量库 Session 交给依赖注入系统使用。
        yield db
    finally:
        # 请求结束后关闭向量库 Session。
        db.close()


# 函数作用：处理“只检索行业知识证据片段”的接口，不调用大模型，只返回匹配到的知识片段和调试信息。
# 注册 POST /industry-knowledge/retrieve 接口，并声明响应模型。
@router.post("/retrieve", response_model=IndustryKnowledgeRetrieveResponse)
async def retrieve_industry_knowledge(
    # FastAPI 会把请求 JSON 解析成这个 Pydantic 请求模型。
    payload: IndustryKnowledgeRetrieveRequest,
    # 通过 Depends 调用 get_db，自动注入业务库 Session。
    db: Session = Depends(get_db),
    # 注入向量库 Session（未配置时为 None）。
    vector_db: Session | None = Depends(get_vector_db),
) -> IndustryKnowledgeRetrieveResponse:
    # 接口说明：只检索证据片段，不调用大模型生成回答。
    """Retrieve evidence chunks for an industry knowledge skill."""
    try:
        # 创建行业知识查询服务，准备执行检索逻辑。
        service = IndustryKnowledgeQueryService(
            # 用业务库和向量库 Session 创建数据仓库实例。
            repository=IndustryKnowledgeRepository(db, vector_db=vector_db),
            # 注入向量服务，供向量检索模式生成 query 向量。
            embedding_service=BgeM3EmbeddingService(),
            # 注入重排服务，供启用重排的向量 skill 精排。
            reranker_service=BgeRerankerService(),
        # 服务对象初始化完成。
        )
        return service.retrieve(
            # 从请求体中取出要检索的技能 ID。
            skill_id=payload.skill_id,
            # 从请求体中取出用户查询文本。
            query=payload.query,
            # 从请求体中取出需要返回的候选片段数量。
            top_k=payload.top_k,
        # 返回检索结果，FastAPI 会按 response_model 序列化响应。
        )
    except RAGException as exc:
        # 业务异常转成 400，表示请求参数或业务条件不满足。
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# 函数作用：处理“行业知识问答”的接口，先检索相关知识片段，再调用大模型生成回答，并保存查询日志和引用记录。
# 注册 POST /industry-knowledge/query 接口，并声明响应模型。
@router.post("/query", response_model=IndustryKnowledgeQueryResponse)
async def query_industry_knowledge(
    # FastAPI 会把请求 JSON 解析成问答请求模型。
    payload: IndustryKnowledgeQueryRequest,
    # 注入业务库 Session，用于读取配置和保存查询记录。
    db: Session = Depends(get_db),
    # 注入向量库 Session（未配置时为 None）。
    vector_db: Session | None = Depends(get_vector_db),
) -> IndustryKnowledgeQueryResponse:
    # 接口说明：先检索证据，再调用大模型生成回答，并保存引用记录。
    """Retrieve chunks, call the LLM, and persist query references."""
    try:
        # 创建行业知识查询服务，准备执行完整问答流程。
        service = IndustryKnowledgeQueryService(
            # 注入数据仓库（业务库 + 向量库），用于检索知识和持久化日志。
            repository=IndustryKnowledgeRepository(db, vector_db=vector_db),
            # 注入大模型服务，用于基于检索结果生成回答。
            llm_service=LLMService(),
            # 注入向量服务，供向量检索模式生成 query 向量。
            embedding_service=BgeM3EmbeddingService(),
            # 注入重排服务，供启用重排的向量 skill 精排。
            reranker_service=BgeRerankerService(),
        # 服务对象初始化完成。
        )
        return await service.answer(
            # 从请求体中取出要查询的技能 ID。
            skill_id=payload.skill_id,
            # 从请求体中取出用户问题。
            query=payload.query,
            # 从请求体中取出要检索的证据片段数量。
            top_k=payload.top_k,
        # 等待异步问答流程完成，并返回回答结果。
        )
    except RAGException as exc:
        # 问答流程异常转成 500，表示服务端处理失败。
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# 函数作用：处理“用户反馈”的接口，把用户对某次问答结果的评分、是否有帮助、评论和标签保存到数据库。
# 注册 POST /industry-knowledge/feedback 接口，并声明响应模型。
@router.post("/feedback", response_model=IndustryKnowledgeFeedbackResponse)
async def create_industry_knowledge_feedback(
    # FastAPI 会把请求 JSON 解析成反馈请求模型。
    payload: IndustryKnowledgeFeedbackRequest,
    # 注入数据库 Session，用于写入反馈数据。
    db: Session = Depends(get_db),
) -> IndustryKnowledgeFeedbackResponse:
    # 接口说明：保存用户对某次行业知识回答的反馈。
    """Store user feedback for one industry knowledge answer."""
    try:
        # 创建行业知识查询服务，准备执行反馈保存逻辑。
        service = IndustryKnowledgeQueryService(
            # 注入数据仓库，用于把反馈写入数据库。
            repository=IndustryKnowledgeRepository(db)
        # 服务对象初始化完成。
        )
        feedback_id = service.create_feedback(
            # 反馈对应的问答日志 ID。
            query_log_id=payload.query_log_id,
            # 用户给出的评分。
            rating=payload.rating,
            # 用户是否认为回答有帮助。
            is_helpful=payload.is_helpful,
            # 用户填写的文字评论。
            comment=payload.comment,
            # 用户选择或提交的反馈标签。
            tags=payload.tags,
        # 调用服务保存反馈，并拿到新反馈记录的 ID。
        )
        # 封装响应体，把反馈 ID 返回给客户端。
        return IndustryKnowledgeFeedbackResponse(feedback_id=feedback_id)
    except RAGException as exc:
        # 反馈保存失败时转成 400，提示客户端请求或业务数据有问题。
        raise HTTPException(status_code=400, detail=str(exc)) from exc
