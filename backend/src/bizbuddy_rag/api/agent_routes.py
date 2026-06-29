"""Agent 中心路由."""

from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from bizbuddy_rag.db import SessionLocal
from bizbuddy_rag.db.models import Agent
from bizbuddy_rag.db.repository import AgentRepository
from bizbuddy_rag.models import (
    AgentCategoryStat,
    AgentCreate,
    AgentOut,
    AgentUpdate,
)

router = APIRouter(prefix="/agents", tags=["agents"])


def get_db() -> Iterator[Session]:
    """获取数据库会话依赖."""
    db = SessionLocal()
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
    )


@router.get("", response_model=list[AgentOut])
async def list_agents(
    category: str | None = None,
    source: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
) -> list[AgentOut]:
    """列出 Agent."""
    repo = AgentRepository(db)
    agents = repo.list_agents(
        category=category,
        source=source,
        search=search,
        only_enabled=True,
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
    update_data: dict[str, object] = {
        "name": payload.name,
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
    db: Session = Depends(get_db),
) -> list[AgentCategoryStat]:
    """Agent 分类统计."""
    repo = AgentRepository(db)
    rows = repo.category_stats()
    return [AgentCategoryStat(label=row[0], count=row[1]) for row in rows]
