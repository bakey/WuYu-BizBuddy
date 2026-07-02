"""文档数据仓库."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from bizbuddy_rag.db.models import Agent, ChatTask, Document, SkillDefinition


class DocumentRepository:
    """文档数据库操作."""

    def __init__(self, db: Session) -> None:
        """初始化仓库.

        Args:
            db: SQLAlchemy 会话.
        """
        self.db = db

    def create(
        self,
        content: str,
        embedding: list[float],
        source: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> Document:
        """创建文档记录.

        Args:
            content: 文档内容.
            embedding: 向量.
            source: 来源.
            metadata: 元数据.

        Returns:
            创建的文档.
        """
        doc = Document(
            content=content,
            embedding=embedding,
            source=source,
            metadata_=metadata,
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def get_by_id(self, doc_id: int) -> Document | None:
        """按 ID 查询文档.

        Args:
            doc_id: 文档 ID.

        Returns:
            文档或 None.
        """
        return self.db.get(Document, doc_id)

    def list_all(self, limit: int = 100, offset: int = 0) -> Sequence[Document]:
        """列出文档.

        Args:
            limit: 数量限制.
            offset: 偏移量.

        Returns:
            文档列表.
        """
        stmt = select(Document).order_by(Document.id.desc()).limit(limit).offset(offset)
        return self.db.execute(stmt).scalars().all()

    def search_similar(
        self,
        embedding: list[float],
        top_k: int = 5,
        threshold: float = 0.0,
    ) -> Sequence[tuple[Document, float]]:
        """基于向量相似度检索文档.

        Args:
            embedding: 查询向量.
            top_k: 返回数量.
            threshold: 余弦相似度阈值.

        Returns:
            (文档, 相似度) 列表.
        """
        distance = Document.embedding.cosine_distance(embedding)
        stmt = (
            select(Document, distance.label("distance"))
            .order_by(distance.asc())
            .limit(top_k)
        )
        rows = self.db.execute(stmt).all()

        results: list[tuple[Document, float]] = []
        for doc, dist in rows:
            similarity = 1.0 - float(dist)
            if similarity >= threshold:
                results.append((doc, similarity))
        return results

    def delete(self, doc_id: int) -> bool:
        """删除文档.

        Args:
            doc_id: 文档 ID.

        Returns:
            是否成功删除.
        """
        doc = self.get_by_id(doc_id)
        if doc is None:
            return False
        self.db.delete(doc)
        self.db.commit()
        return True


class ChatTaskRepository:
    """聊天任务历史数据库操作."""

    def __init__(self, db: Session) -> None:
        """初始化仓库.

        Args:
            db: SQLAlchemy 会话.
        """
        self.db = db

    def create(
        self,
        title: str,
        meta: str | None = None,
        pin: str = "",
        pinned: bool = False,
        agent_name: str | None = None,
        agent_icon: str | None = None,
        agent_id: int | None = None,
    ) -> ChatTask:
        """创建任务.

        Args:
            title: 标题.
            meta: 副标题.
            pin: 置顶标识.
            pinned: 是否置顶.
            agent_name: Agent 名称.
            agent_icon: Agent 图标.
            agent_id: Agent ID.

        Returns:
            创建的任务.
        """
        task = ChatTask(
            title=title,
            meta=meta,
            pin=pin,
            pinned=pinned,
            agent_name=agent_name,
            agent_icon=agent_icon,
            agent_id=agent_id,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def get_by_id(self, task_id: int) -> ChatTask | None:
        """按 ID 查询任务.

        Args:
            task_id: 任务 ID.

        Returns:
            任务或 None.
        """
        return self.db.get(ChatTask, task_id)

    def list_tasks(self, limit: int = 200) -> Sequence[ChatTask]:
        """列出任务，按置顶优先、更新时间倒序.

        Args:
            limit: 数量限制.

        Returns:
            任务列表.
        """
        stmt = (
            select(ChatTask)
            .order_by(ChatTask.pinned.desc(), ChatTask.updated_at.desc())
            .limit(limit)
        )
        return self.db.execute(stmt).scalars().all()

    def update(
        self,
        task_id: int,
        title: str | None = None,
        meta: str | None = None,
        pin: str | None = None,
        pinned: bool | None = None,
        active: bool | None = None,
        agent_id: int | None = None,
    ) -> ChatTask | None:
        """更新任务.

        Args:
            task_id: 任务 ID.
            title: 标题.
            meta: 副标题.
            pin: 置顶标识.
            pinned: 是否置顶.
            active: 是否激活.
            agent_id: Agent ID.

        Returns:
            更新后的任务或 None.
        """
        task = self.get_by_id(task_id)
        if task is None:
            return None
        if title is not None:
            task.title = title
        if meta is not None:
            task.meta = meta
        if pin is not None:
            task.pin = pin
        if pinned is not None:
            task.pinned = pinned
        if active is not None:
            task.active = active
        if agent_id is not None:
            task.agent_id = agent_id
        self.db.commit()
        self.db.refresh(task)
        return task

    def activate(self, task_id: int) -> ChatTask | None:
        """激活指定任务，同时取消其他任务的激活状态.

        Args:
            task_id: 任务 ID.

        Returns:
            激活的任务或 None.
        """
        task = self.get_by_id(task_id)
        if task is None:
            return None
        self.db.query(ChatTask).filter(ChatTask.id != task_id).update(
            {ChatTask.active: False}, synchronize_session=False
        )
        task.active = True
        self.db.commit()
        self.db.refresh(task)
        return task

    def toggle_pin(self, task_id: int) -> ChatTask | None:
        """切换置顶状态.

        Args:
            task_id: 任务 ID.

        Returns:
            切换后的任务或 None.
        """
        task = self.get_by_id(task_id)
        if task is None:
            return None
        task.pinned = not task.pinned
        self.db.commit()
        self.db.refresh(task)
        return task

    def delete(self, task_id: int) -> bool:
        """删除任务.

        Args:
            task_id: 任务 ID.

        Returns:
            是否成功删除.
        """
        task = self.get_by_id(task_id)
        if task is None:
            return False
        self.db.delete(task)
        self.db.commit()
        return True


class SkillRepository:
    """Skill 定义数据仓库."""

    def __init__(self, db: Session) -> None:
        """初始化仓库.

        Args:
            db: SQLAlchemy 会话.
        """
        self.db = db

    def get_by_name(self, name: str) -> SkillDefinition | None:
        """按名称查询 Skill."""
        stmt = select(SkillDefinition).where(
            SkillDefinition.name == name, SkillDefinition.enabled.is_(True)
        )
        return self.db.execute(stmt).scalars().first()

    def list_skills(
        self,
        format: str | None = None,
        only_enabled: bool = True,
        limit: int = 200,
    ) -> Sequence[SkillDefinition]:
        """列出 Skill 定义."""
        stmt = select(SkillDefinition)
        if only_enabled:
            stmt = stmt.where(SkillDefinition.enabled.is_(True))
        if format:
            stmt = stmt.where(SkillDefinition.format == format)
        stmt = stmt.order_by(SkillDefinition.name).limit(limit)
        return self.db.execute(stmt).scalars().all()

    def create(
        self,
        *,
        name: str,
        description: str,
        parameters_schema: dict[str, object] | None = None,
        format: str = "native",
        alias: str | None = None,
        config: dict[str, object] | None = None,
        handler_module: str | None = None,
        enabled: bool = True,
    ) -> SkillDefinition:
        """创建 Skill 定义."""
        skill = SkillDefinition(
            name=name,
            alias=alias,
            format=format,
            description=description,
            parameters_schema=parameters_schema or {},
            config=config or {},
            handler_module=handler_module,
            enabled=enabled,
        )
        self.db.add(skill)
        self.db.commit()
        self.db.refresh(skill)
        return skill


class AgentRepository:
    """Agent 数据仓库."""

    def __init__(self, db: Session) -> None:
        """初始化仓库.

        Args:
            db: SQLAlchemy 会话.
        """
        self.db = db

    def create(
        self,
        *,
        name: str,
        agent_type: str = "simple",
        icon: str,
        bg: str,
        color: str,
        desc: str,
        skills: list[str],
        users: str,
        rating: float,
        featured: bool,
        category: str,
        tag_label: str | None,
        tag_cls: str | None,
        source: str,
        enabled: bool,
        system_prompt: str | None = None,
        default_top_k: int = 5,
        retrieval_mode: str = "basic_rag",
        industry_skill_id: str | None = None,
        config: dict[str, object] | None = None,
    ) -> Agent:
        """创建 Agent."""
        agent = Agent(
            name=name,
            agent_type=agent_type,
            icon=icon,
            bg=bg,
            color=color,
            desc=desc,
            skills=skills,
            users=users,
            rating=str(rating),
            featured=featured,
            category=category,
            tag_label=tag_label,
            tag_cls=tag_cls,
            source=source,
            enabled=enabled,
            system_prompt=system_prompt,
            default_top_k=default_top_k,
            retrieval_mode=retrieval_mode,
            industry_skill_id=industry_skill_id,
            config=config or {},
        )
        self.db.add(agent)
        self.db.commit()
        self.db.refresh(agent)
        return agent

    def get_by_id(self, agent_id: int) -> Agent | None:
        """按 ID 查询 Agent."""
        return self.db.get(Agent, agent_id)

    def list_agents(
        self,
        *,
        category: str | None = None,
        source: str | None = None,
        search: str | None = None,
        only_enabled: bool = True,
        limit: int = 200,
    ) -> Sequence[Agent]:
        """列出 Agent，支持分类、来源、搜索筛选."""
        stmt = select(Agent)
        if only_enabled:
            stmt = stmt.where(Agent.enabled.is_(True))
        if category:
            stmt = stmt.where(Agent.category == category)
        if source:
            stmt = stmt.where(Agent.source == source)
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                Agent.name.ilike(pattern) | Agent.desc.ilike(pattern)
            )
        stmt = stmt.order_by(Agent.featured.desc(), Agent.rating.desc())
        stmt = stmt.limit(limit)
        return self.db.execute(stmt).scalars().all()

    def category_stats(self) -> Sequence[tuple[str, int]]:
        """按分类统计 Agent 数量."""
        from sqlalchemy import func

        stmt = (
            select(Agent.category, func.count(Agent.id))
            .where(Agent.enabled.is_(True))
            .group_by(Agent.category)
            .order_by(func.count(Agent.id).desc())
        )
        return self.db.execute(stmt).all()

    def source_stats(self) -> Sequence[tuple[str, int]]:
        """按来源统计 Agent 数量."""
        from sqlalchemy import func

        stmt = (
            select(Agent.source, func.count(Agent.id))
            .where(Agent.enabled.is_(True))
            .group_by(Agent.source)
            .order_by(func.count(Agent.id).desc())
        )
        return self.db.execute(stmt).all()

    def create_team_member(
        self,
        agent_id: int,
        member_agent_id: int,
        role: str,
        step_template: dict[str, object] | None = None,
        order_index: int = 0,
    ) -> dict[str, object]:
        """为复合 Agent 添加团队成员."""
        from sqlalchemy import text

        result = self.db.execute(
            text(
                """
                INSERT INTO agent_team_members
                  (agent_id, member_agent_id, role, step_template, order_index)
                VALUES
                  (:agent_id, :member_agent_id, :role, :step_template, :order_index)
                RETURNING id, agent_id, member_agent_id, role, step_template, order_index
                """
            ),
            {
                "agent_id": agent_id,
                "member_agent_id": member_agent_id,
                "role": role,
                "step_template": step_template or {},
                "order_index": order_index,
            },
        ).mappings().first()
        self.db.commit()
        return dict(result) if result else {}

    def list_team_members(self, agent_id: int) -> list[dict[str, object]]:
        """列出复合 Agent 的团队成员."""
        from sqlalchemy import text

        rows = self.db.execute(
            text(
                """
                SELECT
                  m.id,
                  m.agent_id,
                  m.member_agent_id,
                  a.name AS member_name,
                  a.icon AS member_icon,
                  a.system_prompt,
                  a.skills,
                  m.role,
                  m.step_template,
                  m.order_index
                FROM agent_team_members m
                JOIN agents a ON a.id = m.member_agent_id
                WHERE m.agent_id = :agent_id
                ORDER BY m.order_index, m.id
                """
            ),
            {"agent_id": agent_id},
        ).mappings().all()
        return [dict(row) for row in rows]

    def delete_team_member(self, agent_id: int, member_id: int) -> bool:
        """删除团队成员."""
        from sqlalchemy import text

        result = self.db.execute(
            text(
                "DELETE FROM agent_team_members WHERE agent_id = :agent_id AND id = :member_id"
            ),
            {"agent_id": agent_id, "member_id": member_id},
        )
        self.db.commit()
        return result.rowcount > 0

    def update(
        self,
        agent_id: int,
        **kwargs: object,
    ) -> Agent | None:
        """更新 Agent."""
        agent = self.get_by_id(agent_id)
        if agent is None:
            return None
        for key, value in kwargs.items():
            if value is not None and hasattr(agent, key):
                setattr(agent, key, value)
        self.db.commit()
        self.db.refresh(agent)
        return agent

    def delete(self, agent_id: int) -> bool:
        """删除 Agent."""
        agent = self.get_by_id(agent_id)
        if agent is None:
            return False
        self.db.delete(agent)
        self.db.commit()
        return True
