"""Agent 中心路由."""

from collections.abc import AsyncGenerator, Iterator
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from bizbuddy_rag.db import GufeiVecSessionLocal, SessionLocal
from bizbuddy_rag.db.execution_repository import ExecutionRepository
from bizbuddy_rag.db.industry_knowledge_repository import (
    IndustryKnowledgeRepository,
)
from bizbuddy_rag.db.models import Agent
from bizbuddy_rag.db.repository import AgentRepository
from bizbuddy_rag.models import (
    AgentCategoryStat,
    AgentCreate,
    AgentExecutionCreate,
    AgentExecutionDetailOut,
    AgentExecutionOut,
    AgentOut,
    AgentTeamMemberCreate,
    AgentTeamMemberOut,
    AgentUpdate,
    QueryRequest,
    RAGResponse,
    RetrievedChunk,
)
from bizbuddy_rag.services import EmbeddingService, LLMService
from bizbuddy_rag.services.agent_framework import AgentExecutor
from bizbuddy_rag.services.agent_framework.formatter import ReportFormatter
from bizbuddy_rag.services.bge_embedding import BgeM3EmbeddingService
from bizbuddy_rag.services.industry_knowledge import IndustryKnowledgeQueryService
from bizbuddy_rag.services.rag import RAGService
from bizbuddy_rag.services.reranker import BgeRerankerService
from bizbuddy_rag.utils.exceptions import RAGException

router = APIRouter(prefix="/agents", tags=["agents"])


def get_db() -> Iterator[Session]:
    """获取数据库会话依赖."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_vector_db() -> Iterator[Session | None]:
    """获取 gufei_vec 向量库 Session；未配置时返回 None."""
    if GufeiVecSessionLocal is None:
        yield None
        return
    db = GufeiVecSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _agent_out(agent: Agent) -> AgentOut:
    """把 ORM 对象转换为输出模型."""
    tag = None
    if agent.tag_label and agent.tag_cls:
        tag = {"label": agent.tag_label, "cls": agent.tag_cls}
    return AgentOut(
        id=agent.id,
        name=agent.name,
        agent_type=agent.agent_type,
        icon=agent.icon,
        bg=agent.bg,
        color=agent.color,
        desc=agent.desc,
        skills=list(agent.skills) if agent.skills else [],
        users=agent.users,
        rating=float(agent.rating) if agent.rating else 0.0,
        featured=agent.featured,
        category=agent.category,
        tag=tag,
        source=agent.source,
        enabled=agent.enabled,
        system_prompt=agent.system_prompt,
        default_top_k=agent.default_top_k,
        retrieval_mode=agent.retrieval_mode,
        industry_skill_id=str(agent.industry_skill_id) if agent.industry_skill_id else None,
        config=agent.config if isinstance(agent.config, dict) else None,
    )


@router.get("", response_model=list[AgentOut])
async def list_agents(
    category: str | None = None,
    source: str | None = None,
    search: str | None = None,
    include_system: bool = False,
    db: Session = Depends(get_db),
) -> list[AgentOut]:
    """列出 Agent。

    默认排除 category='system' 的内部组件（composite Agent 的 orchestrator/worker/reviewer），
    传 include_system=true 才返回全部（管理面板/系统巡检用）。
    """
    repo = AgentRepository(db)
    agents = repo.list_agents(
        category=category,
        source=source,
        search=search,
        only_enabled=True,
        include_system=include_system,
    )
    return [_agent_out(a) for a in agents]


@router.post("", response_model=AgentOut, status_code=201)
async def create_agent(
    payload: AgentCreate,
    db: Session = Depends(get_db),
) -> AgentOut:
    """创建 Agent."""
    repo = AgentRepository(db)
    agent = repo.create(
        name=payload.name,
        agent_type=payload.agent_type,
        icon=payload.icon,
        bg=payload.bg,
        color=payload.color,
        desc=payload.desc,
        skills=payload.skills,
        users=payload.users,
        rating=payload.rating,
        featured=payload.featured,
        category=payload.category,
        tag_label=payload.tag.label if payload.tag else None,
        tag_cls=payload.tag.cls if payload.tag else None,
        source=payload.source,
        enabled=payload.enabled,
        system_prompt=payload.system_prompt,
        default_top_k=payload.default_top_k,
        retrieval_mode=payload.retrieval_mode,
        industry_skill_id=payload.industry_skill_id,
        config=payload.config,
    )
    return _agent_out(agent)


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(
    agent_id: int,
    db: Session = Depends(get_db),
) -> AgentOut:
    """获取 Agent 详情."""
    repo = AgentRepository(db)
    agent = repo.get_by_id(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    return _agent_out(agent)


@router.put("/{agent_id}", response_model=AgentOut)
async def update_agent(
    agent_id: int,
    payload: AgentUpdate,
    db: Session = Depends(get_db),
) -> AgentOut:
    """更新 Agent."""
    repo = AgentRepository(db)
    update_data: dict[str, Any] = {
        "name": payload.name,
        "agent_type": payload.agent_type,
        "icon": payload.icon,
        "bg": payload.bg,
        "color": payload.color,
        "desc": payload.desc,
        "skills": payload.skills,
        "users": payload.users,
        "rating": str(payload.rating) if payload.rating is not None else None,
        "featured": payload.featured,
        "category": payload.category,
        "tag_label": payload.tag.label if payload.tag else None,
        "tag_cls": payload.tag.cls if payload.tag else None,
        "source": payload.source,
        "enabled": payload.enabled,
        "system_prompt": payload.system_prompt,
        "default_top_k": payload.default_top_k,
        "retrieval_mode": payload.retrieval_mode,
        "industry_skill_id": payload.industry_skill_id,
        "config": payload.config,
    }
    update_data = {k: v for k, v in update_data.items() if v is not None}
    agent = repo.update(agent_id, **update_data)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    return _agent_out(agent)


@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: int,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    """删除 Agent."""
    repo = AgentRepository(db)
    if not repo.delete(agent_id):
        raise HTTPException(status_code=404, detail="Agent 不存在")
    return {"deleted": True}


@router.get("/stats/categories", response_model=list[AgentCategoryStat])
async def category_stats(
    include_system: bool = False,
    db: Session = Depends(get_db),
) -> list[AgentCategoryStat]:
    """Agent 分类统计。默认不含 system 内部组件。"""
    repo = AgentRepository(db)
    rows = repo.category_stats(include_system=include_system)
    return [AgentCategoryStat(label=row[0], count=row[1]) for row in rows]


@router.get("/{agent_id}/team", response_model=list[AgentTeamMemberOut])
async def list_team_members(
    agent_id: int,
    db: Session = Depends(get_db),
) -> list[AgentTeamMemberOut]:
    """列出复合 Agent 的团队成员."""
    repo = AgentRepository(db)
    agent = repo.get_by_id(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    rows = repo.list_team_members(agent_id)
    return [
        AgentTeamMemberOut(
            id=row["id"],
            agent_id=row["agent_id"],
            member_agent_id=row["member_agent_id"],
            member_name=row["member_name"],
            member_icon=row["member_icon"],
            role=row["role"],
            step_template=row["step_template"] if isinstance(row["step_template"], dict) else {},
            order_index=row["order_index"],
        )
        for row in rows
    ]


@router.post("/{agent_id}/team", response_model=AgentTeamMemberOut, status_code=201)
async def add_team_member(
    agent_id: int,
    payload: AgentTeamMemberCreate,
    db: Session = Depends(get_db),
) -> AgentTeamMemberOut:
    """为复合 Agent 添加团队成员."""
    repo = AgentRepository(db)
    agent = repo.get_by_id(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    if agent.agent_type != "composite":
        raise HTTPException(status_code=400, detail="只有 composite Agent 可以添加团队成员")
    member = repo.get_by_id(payload.member_agent_id)
    if member is None:
        raise HTTPException(status_code=404, detail="成员 Agent 不存在")
    row = repo.create_team_member(
        agent_id=agent_id,
        member_agent_id=payload.member_agent_id,
        role=payload.role,
        step_template=payload.step_template,
        order_index=payload.order_index,
    )
    return AgentTeamMemberOut(
        id=row["id"],
        agent_id=row["agent_id"],
        member_agent_id=row["member_agent_id"],
        member_name=member.name,
        member_icon=member.icon,
        role=row["role"],
        step_template=row["step_template"] if isinstance(row["step_template"], dict) else {},
        order_index=row["order_index"],
    )


@router.delete("/{agent_id}/team/{member_id}")
async def remove_team_member(
    agent_id: int,
    member_id: int,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    """移除团队成员."""
    repo = AgentRepository(db)
    agent = repo.get_by_id(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    deleted = repo.delete_team_member(agent_id, member_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="团队成员不存在")
    return {"deleted": True}


@router.get("/{agent_id}/executions", response_model=list[AgentExecutionOut])
async def list_agent_executions(
    agent_id: int,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> list[AgentExecutionOut]:
    """列出 Agent 执行记录."""
    repo = ExecutionRepository(db)
    rows = repo.list_executions(agent_id=agent_id, limit=limit, offset=offset)
    return [
        AgentExecutionOut(
            id=str(row["id"]),
            agent_id=row["agent_id"],
            agent_name=row["agent_name"],
            user_query=row["user_query"],
            status=row["status"],
            revision_count=row["revision_count"],
            created_at=str(row["created_at"]) if row["created_at"] else None,
            updated_at=str(row["updated_at"]) if row["updated_at"] else None,
        )
        for row in rows
    ]


@router.get("/executions/{execution_id}", response_model=AgentExecutionDetailOut)
async def get_execution_detail(
    execution_id: str,
    db: Session = Depends(get_db),
) -> AgentExecutionDetailOut:
    """获取执行记录详情."""
    from uuid import UUID

    repo = ExecutionRepository(db)
    execution = repo.get_execution(UUID(execution_id))
    if execution is None:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    steps = repo.get_execution_steps(UUID(execution_id))
    reviews = repo.get_execution_reviews(UUID(execution_id))
    return AgentExecutionDetailOut(
        id=str(execution["id"]),
        agent_id=execution["agent_id"],
        agent_name=execution["agent_name"],
        user_query=execution["user_query"],
        status=execution["status"],
        final_answer=execution["final_answer"],
        plan_json=execution["plan_json"] if isinstance(execution["plan_json"], dict) else {},
        revision_count=execution["revision_count"],
        steps=steps,
        reviews=reviews,
        created_at=str(execution["created_at"]) if execution["created_at"] else None,
        updated_at=str(execution["updated_at"]) if execution["updated_at"] else None,
    )


@router.post("/{agent_id}/execute", response_model=RAGResponse)
async def agent_execute(
    agent_id: int,
    payload: AgentExecutionCreate,
    db: Session = Depends(get_db),
    vector_db: Session | None = Depends(get_vector_db),
) -> RAGResponse:
    """执行复合 Agent（非流式）."""
    agent_repo = AgentRepository(db)
    agent = agent_repo.get_by_id(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    if agent.agent_type != "composite":
        raise HTTPException(status_code=400, detail="该 Agent 不是复合 Agent，请使用 /query")

    executor = AgentExecutor(db, vector_db, agent_repo)
    result = await executor.run(
        composite_agent_id=agent_id,
        user_query=payload.prompt,
        top_k=payload.top_k,
    )
    return RAGResponse(
        answer=result.final_answer,
        references=[
            RetrievedChunk(
                content=ref.get("content", ""),
                source=ref.get("source"),
                score=ref.get("score", 0.0),
                metadata=ref.get("metadata"),
            )
            for ref in result.references
        ],
    )


def _build_rag_service() -> RAGService:
    """创建 RAG 服务实例."""
    return RAGService(
        embedding_service=EmbeddingService(),
        llm_service=LLMService(),
    )


def _build_industry_service(
    db: Session, vector_db: Session | None
) -> IndustryKnowledgeQueryService:
    """创建行业知识查询服务实例."""
    return IndustryKnowledgeQueryService(
        repository=IndustryKnowledgeRepository(db, vector_db=vector_db),
        llm_service=LLMService(),
        embedding_service=BgeM3EmbeddingService(),
        reranker_service=BgeRerankerService(),
    )


@router.post("/{agent_id}/query", response_model=RAGResponse)
async def agent_query(
    agent_id: int,
    payload: QueryRequest,
    db: Session = Depends(get_db),
    vector_db: Session | None = Depends(get_vector_db),
) -> RAGResponse:
    """根据 Agent 配置执行问答."""
    agent_repo = AgentRepository(db)
    agent = agent_repo.get_by_id(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent 不存在")

    try:
        if agent.retrieval_mode == "formatter":
            formatter = ReportFormatter()
            formatted = await formatter.format(payload.prompt)
            return RAGResponse(answer=formatted, references=[])

        if agent.retrieval_mode == "industry_knowledge":
            if not agent.industry_skill_id:
                raise RAGException("该 Agent 未配置行业知识 skill")
            service = _build_industry_service(db, vector_db)
            result = await service.answer(
                skill_id=UUID(str(agent.industry_skill_id)),
                query=payload.prompt,
                top_k=payload.top_k or agent.default_top_k,
            )
            return RAGResponse(
                answer=result.answer,
                references=[
                    RetrievedChunk(
                        content=ref.content,
                        source=ref.source,
                        score=ref.score,
                        metadata=ref.metadata,
                    )
                    for ref in result.references
                ],
            )

        # 默认 basic_rag
        rag = _build_rag_service()
        answer, refs = await rag.answer(
            db,
            payload.prompt,
            top_k=payload.top_k or agent.default_top_k,
        )
        return RAGResponse(answer=answer, references=refs)
    except RAGException as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def _stream_agent_answer(
    agent: Agent,
    payload: QueryRequest,
    db: Session,
    vector_db: Session | None,
) -> AsyncGenerator[str]:
    """根据 Agent 配置流式生成 SSE 数据."""
    import json

    try:
        if agent.retrieval_mode == "formatter":
            formatter = ReportFormatter()
            formatted = await formatter.format(payload.prompt)
            chunk_size = 12
            for i in range(0, len(formatted), chunk_size):
                chunk = formatted[i : i + chunk_size]
                payload = json.dumps({"delta": chunk}, ensure_ascii=False)
                yield f"event: delta\ndata: {payload}\n\n"
            yield "event: done\ndata: [DONE]\n\n"
            return

        if agent.retrieval_mode == "industry_knowledge":
            if not agent.industry_skill_id:
                raise RAGException("该 Agent 未配置行业知识 skill")
            service = _build_industry_service(db, vector_db)
            result = service.retrieve(
                skill_id=UUID(str(agent.industry_skill_id)),
                query=payload.prompt,
                top_k=payload.top_k or agent.default_top_k,
            )
            refs = [
                RetrievedChunk(
                    content=ref.content,
                    source=ref.source,
                    score=ref.score,
                    metadata=ref.metadata,
                )
                for ref in result.items
            ]
            refs_dump = [r.model_dump() for r in refs]
            yield f"event: references\ndata: {json.dumps(refs_dump, ensure_ascii=False)}\n\n"

            context = "\n\n".join(f"[{i + 1}] {r.content}" for i, r in enumerate(refs))
            llm = LLMService()
            async for delta in llm.chat_stream(
                payload.prompt, context, agent.system_prompt
            ):
                yield f"event: delta\ndata: {json.dumps({'delta': delta}, ensure_ascii=False)}\n\n"
        else:
            rag = _build_rag_service()
            async for event, data in rag.answer_stream(
                db,
                payload.prompt,
                top_k=payload.top_k or agent.default_top_k,
            ):
                if event == "references":
                    chunks: list[RetrievedChunk] = data
                    refs = [ref.model_dump() for ref in chunks]
                    yield f"event: references\ndata: {json.dumps(refs, ensure_ascii=False)}\n\n"
                elif event == "delta":
                    delta: str = data
                    delta_payload = json.dumps({"delta": delta}, ensure_ascii=False)
                    yield f"event: delta\ndata: {delta_payload}\n\n"
        yield "event: done\ndata: [DONE]\n\n"
    except RAGException as exc:
        yield f"event: error\ndata: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"


@router.post("/{agent_id}/execute/stream")
async def agent_execute_stream(
    agent_id: int,
    payload: AgentExecutionCreate,
    db: Session = Depends(get_db),
    vector_db: Session | None = Depends(get_vector_db),
) -> object:
    """执行复合 Agent（SSE 流式）."""
    from fastapi.responses import StreamingResponse

    agent_repo = AgentRepository(db)
    agent = agent_repo.get_by_id(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    if agent.agent_type != "composite":
        raise HTTPException(status_code=400, detail="该 Agent 不是复合 Agent，请使用 /query/stream")

    async def event_stream() -> AsyncGenerator[str]:
        import json

        executor = AgentExecutor(db, vector_db, agent_repo)
        try:
            async for event, data in executor.execute_stream(
                composite_agent_id=agent_id,
                user_query=payload.prompt,
                top_k=payload.top_k,
            ):
                payload_json = json.dumps(data, ensure_ascii=False, default=str)
                yield f"event: {event}\ndata: {payload_json}\n\n"
        except Exception as exc:
            yield f"event: error\ndata: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/{agent_id}/query/stream")
async def agent_query_stream(
    agent_id: int,
    payload: QueryRequest,
    db: Session = Depends(get_db),
    vector_db: Session | None = Depends(get_vector_db),
) -> object:
    """根据 Agent 配置流式问答 (SSE)."""
    from fastapi.responses import StreamingResponse

    agent_repo = AgentRepository(db)
    agent = agent_repo.get_by_id(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent 不存在")

    return StreamingResponse(
        _stream_agent_answer(agent, payload, db, vector_db),
        media_type="text/event-stream",
    )
