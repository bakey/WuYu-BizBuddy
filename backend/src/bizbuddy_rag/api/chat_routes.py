"""聊天任务历史路由."""

from collections.abc import Iterator
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from bizbuddy_rag.db import SessionLocal
from bizbuddy_rag.db.models import ChatTask
from bizbuddy_rag.db.repository import ChatTaskRepository
from bizbuddy_rag.models import ChatTaskCreate, ChatTaskOut, ChatTaskUpdate

router = APIRouter(prefix="/chat", tags=["chat"])


def get_db() -> Iterator[Session]:
    """获取数据库会话依赖."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _format_dt(value: datetime | None) -> str | None:
    """格式化 datetime 为 ISO 字符串."""
    if value is None:
        return None
    return value.astimezone(UTC).isoformat()


def _task_out(task: ChatTask) -> ChatTaskOut:
    """把 ORM 对象转换为输出模型."""
    return ChatTaskOut(
        id=task.id,
        title=task.title,
        meta=task.meta,
        pin=task.pin,
        pinned=task.pinned,
        active=task.active,
        agent_name=task.agent_name,
        agent_icon=task.agent_icon,
        created_at=_format_dt(task.created_at),
        updated_at=_format_dt(task.updated_at),
    )


@router.get("/tasks", response_model=list[ChatTaskOut])
async def list_tasks(
    limit: int = 200,
    db: Session = Depends(get_db),
) -> list[ChatTaskOut]:
    """列出聊天任务历史."""
    repo = ChatTaskRepository(db)
    tasks = repo.list_tasks(limit=limit)
    return [_task_out(t) for t in tasks]


@router.post("/tasks", response_model=ChatTaskOut, status_code=201)
async def create_task(
    payload: ChatTaskCreate,
    db: Session = Depends(get_db),
) -> ChatTaskOut:
    """创建聊天任务."""
    repo = ChatTaskRepository(db)
    task = repo.create(
        title=payload.title,
        meta=payload.meta,
        pin=payload.pin or "",
        pinned=payload.pinned,
        agent_name=payload.agent_name,
        agent_icon=payload.agent_icon,
    )
    return _task_out(task)


@router.get("/tasks/{task_id}", response_model=ChatTaskOut)
async def get_task(
    task_id: int,
    db: Session = Depends(get_db),
) -> ChatTaskOut:
    """获取单个任务详情."""
    repo = ChatTaskRepository(db)
    task = repo.get_by_id(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _task_out(task)


@router.put("/tasks/{task_id}", response_model=ChatTaskOut)
async def update_task(
    task_id: int,
    payload: ChatTaskUpdate,
    db: Session = Depends(get_db),
) -> ChatTaskOut:
    """更新聊天任务."""
    repo = ChatTaskRepository(db)
    task = repo.update(
        task_id=task_id,
        title=payload.title,
        meta=payload.meta,
        pin=payload.pin,
        pinned=payload.pinned,
        active=payload.active,
    )
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _task_out(task)


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    """删除聊天任务."""
    repo = ChatTaskRepository(db)
    if not repo.delete(task_id):
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"deleted": True}


@router.post("/tasks/{task_id}/activate", response_model=ChatTaskOut)
async def activate_task(
    task_id: int,
    db: Session = Depends(get_db),
) -> ChatTaskOut:
    """激活指定任务."""
    repo = ChatTaskRepository(db)
    task = repo.activate(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _task_out(task)


@router.post("/tasks/{task_id}/pin", response_model=ChatTaskOut)
async def toggle_pin_task(
    task_id: int,
    db: Session = Depends(get_db),
) -> ChatTaskOut:
    """切换任务置顶状态."""
    repo = ChatTaskRepository(db)
    task = repo.toggle_pin(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _task_out(task)
