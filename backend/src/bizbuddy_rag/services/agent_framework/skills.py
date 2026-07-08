"""Skill 抽象与内置 Skill 实现."""

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from bizbuddy_rag.db.industry_knowledge_repository import IndustryKnowledgeRepository
from bizbuddy_rag.services import EmbeddingService, LLMService
from bizbuddy_rag.services.bge_embedding import BgeM3EmbeddingService
from bizbuddy_rag.services.industry_knowledge import IndustryKnowledgeQueryService
from bizbuddy_rag.services.rag import RAGService
from bizbuddy_rag.services.reranker import BgeRerankerService

from .models import SkillResult


class Skill(ABC):
    """Skill 抽象基类."""

    name: str = ""

    @abstractmethod
    async def invoke(
        self, query: str, context: dict[str, Any]
    ) -> SkillResult:
        """执行 Skill.

        Args:
            query: 用户查询.
            context: 执行上下文，可包含 db、vector_db、top_k、skill_id 等.

        Returns:
            Skill 执行结果.
        """


class BasicRAGSkill(Skill):
    """基于本地 documents 表的 RAG Skill."""

    name = "basic_rag"

    def __init__(self) -> None:
        self.rag = RAGService(
            embedding_service=EmbeddingService(),
            llm_service=LLMService(),
        )

    async def invoke(
        self, query: str, context: dict[str, Any]
    ) -> SkillResult:
        db: Session = context["db"]
        top_k = context.get("top_k", 5)
        try:
            chunks = self.rag.retrieve(db, query, top_k=top_k)
            content = "\n\n".join(
                f"[{i + 1}] {chunk.content}" for i, chunk in enumerate(chunks)
            )
            return SkillResult(
                skill_name=self.name,
                success=True,
                content=content,
                references=[
                    {
                        "content": chunk.content,
                        "source": chunk.source,
                        "score": chunk.score,
                        "metadata": chunk.metadata,
                    }
                    for chunk in chunks
                ],
                metadata={"retrieved_count": len(chunks)},
            )
        except Exception as exc:
            return SkillResult(
                skill_name=self.name,
                success=False,
                error=f"basic_rag failed: {exc}",
            )


class IndustryKnowledgeSkillAdapter(Skill):
    """基于行业知识库 gufei_vec 的 Skill.

    仅做检索，不在内部再调一次 LLM 生成小结（那次 LLM 输出对
    Composite Agent 的最终合成没有价值，只会成倍拉高时延）。
    最终答案由 executor 汇总所有 Worker 引用后统一调 LLM 生成。
    """

    name = "industry_knowledge"

    def __init__(self) -> None:
        self.embedding_service = BgeM3EmbeddingService()
        self.reranker_service = BgeRerankerService()

    async def invoke(
        self, query: str, context: dict[str, Any]
    ) -> SkillResult:
        db: Session = context["db"]
        vector_db: Session | None = context.get("vector_db")
        skill_id_raw = context.get("skill_id")
        top_k = context.get("top_k", 5)
        # 允许 executor 预计算 query 向量并注入，避免多 Worker 重复 embed。
        query_vector = context.get("_query_vector")
        if skill_id_raw is None:
            return SkillResult(
                skill_name=self.name,
                success=False,
                error="industry_knowledge skill requires skill_id in context",
            )
        try:
            service = IndustryKnowledgeQueryService(
                repository=IndustryKnowledgeRepository(db, vector_db=vector_db),
                llm_service=None,
                embedding_service=self.embedding_service,
                reranker_service=self.reranker_service,
            )
            result = service.retrieve(
                skill_id=UUID(str(skill_id_raw)),
                query=query,
                top_k=top_k,
                query_vector=query_vector,
            )
            content = "\n\n".join(
                f"[{i + 1}] {ref.content}"
                for i, ref in enumerate(result.items)
            )
            return SkillResult(
                skill_name=self.name,
                success=True,
                content=content,
                references=[
                    {
                        "content": ref.content,
                        "source": ref.source,
                        "score": ref.score,
                        "metadata": ref.metadata,
                    }
                    for ref in result.items
                ],
                metadata={
                    "retrieved_count": len(result.items),
                },
            )
        except Exception as exc:
            return SkillResult(
                skill_name=self.name,
                success=False,
                error=f"industry_knowledge failed: {exc}",
            )


class PolicySearchSkill(Skill):
    """政策检索 Skill：根据 policy_scope 限定检索范围.

    目前复用 industry_knowledge 的 vector_subdir 能力，通过 context 中的
    skill_id 指向对应政策范围的 skill。
    """

    name = "policy_search"

    def __init__(self) -> None:
        self.adapter = IndustryKnowledgeSkillAdapter()

    async def invoke(
        self, query: str, context: dict[str, Any]
    ) -> SkillResult:
        policy_scope = context.get("policy_scope", "national")
        metadata = {"policy_scope": policy_scope}
        # 透传给 industry_knowledge adapter，skill_id 已由 Orchestrator 决定
        result = await self.adapter.invoke(query, context)
        result.skill_name = self.name
        result.metadata = {**result.metadata, **metadata}
        return result
