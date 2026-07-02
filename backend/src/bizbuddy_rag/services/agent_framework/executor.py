"""Agent 执行引擎."""

from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from bizbuddy_rag.db.execution_repository import ExecutionRepository
from bizbuddy_rag.db.repository import AgentRepository
from bizbuddy_rag.services.agent_framework.agents import (
    OrchestratorAgent,
    ReviewerAgent,
    WorkerAgent,
)
from bizbuddy_rag.services.agent_framework.models import (
    AgentPlan,
    ExecutionResult,
    ReviewResult,
    SkillResult,
)
from bizbuddy_rag.services.llm import LLMService
from bizbuddy_rag.utils.exceptions import RAGException

MAX_REVISIONS = 2


class AgentExecutor:
    """复合 Agent 执行引擎.

    编排 Orchestrator -> Workers -> Reviewer -> Revision 循环。
    """

    def __init__(
        self,
        db: Session,
        vector_db: Session | None,
        agent_repo: AgentRepository,
        execution_id: UUID | None = None,
    ) -> None:
        self.db = db
        self.vector_db = vector_db
        self.agent_repo = agent_repo
        self.execution_id = execution_id
        self.exec_repo = ExecutionRepository(db)
        self.llm = LLMService()

    async def run(
        self,
        composite_agent_id: int,
        user_query: str,
        top_k: int = 5,
        stream: bool = False,
    ) -> ExecutionResult:
        """执行复合 Agent.

        Args:
            composite_agent_id: 复合 Agent ID.
            user_query: 用户问题.
            top_k: 默认检索数量.
            stream: 是否流式（非流式直接返回结果）.

        Returns:
            ExecutionResult.
        """
        composite = self.agent_repo.get_by_id(composite_agent_id)
        if composite is None:
            raise RAGException("复合 Agent 不存在")
        if composite.agent_type != "composite":
            raise RAGException("该 Agent 不是复合 Agent")

        team = self.agent_repo.list_team_members(composite_agent_id)
        orchestrator_member = next(
            (m for m in team if m["role"] == "orchestrator"), None
        )
        worker_members = [m for m in team if m["role"] == "worker"]
        reviewer_member = next(
            (m for m in team if m["role"] == "reviewer"), None
        )

        if orchestrator_member is None:
            raise RAGException("复合 Agent 未配置 Orchestrator")

        orchestrator = OrchestratorAgent(
            agent_id=orchestrator_member["member_agent_id"],
            name=orchestrator_member["member_name"],
            system_prompt=orchestrator_member["system_prompt"],
        )

        workers = {
            m["member_agent_id"]: WorkerAgent(
                agent_id=m["member_agent_id"],
                name=m["member_name"],
                system_prompt=m["system_prompt"],
            )
            for m in worker_members
        }

        reviewer = None
        if reviewer_member is not None:
            reviewer = ReviewerAgent(
                agent_id=reviewer_member["member_agent_id"],
                name=reviewer_member["member_name"],
                system_prompt=reviewer_member["system_prompt"],
            )

        context: dict[str, Any] = {
            "db": self.db,
            "vector_db": self.vector_db,
            "top_k": top_k,
        }

        workers_info = [
            {
                "id": m["member_agent_id"],
                "name": m["member_name"],
                "skills": m.get("skills", []),
                "step_template": m.get("step_template", {}),
            }
            for m in worker_members
        ]
        reviewer_info = (
            {
                "id": reviewer_member["member_agent_id"],
                "name": reviewer_member["member_name"],
            }
            if reviewer_member
            else None
        )

        plan: AgentPlan | None = None
        reviews: list[ReviewResult] = []
        revision_count = 0
        final_answer = ""
        all_references: list[dict[str, Any]] = []

        execution_id = self.execution_id
        if execution_id is None:
            execution_id = self.exec_repo.create_execution(
                agent_id=composite_agent_id,
                user_query=user_query,
            )

        while revision_count <= MAX_REVISIONS:
            previous_feedback = reviews[-1].feedback if reviews else None
            plan = await orchestrator.create_plan(
                user_query=user_query,
                workers=workers_info,
                reviewer=reviewer_info,
                previous_feedback=previous_feedback,
                previous_plan=plan,
            )

            self.exec_repo.complete_execution(
                execution_id=execution_id,
                status="running",
                final_answer="",
                revision_count=revision_count,
            )

            worker_outputs: list[SkillResult] = []
            all_references = []
            for step in plan.steps:
                worker = workers.get(step.member_agent_id)
                if worker is None:
                    step.result = SkillResult(
                        skill_name=step.action,
                        success=False,
                        error=f"未找到 member_agent_id={step.member_agent_id} 的 worker",
                    )
                    step.status = "failed"
                    worker_outputs.append(step.result)
                    continue

                # 合并 worker 的 step_template 到 step.input
                worker_info = next(
                    (w for w in workers_info if w["id"] == step.member_agent_id), {}
                )
                template = worker_info.get("step_template") or {}
                merged_input = {**template, **step.input}
                step.input = merged_input

                result = await worker.execute_step(user_query, step, context)
                worker_outputs.append(result)
                all_references.extend(result.references)

            draft_context = "\n\n".join(
                f"[{i + 1}] {out.content[:1500]}"
                for i, out in enumerate(worker_outputs)
                if out.success
            )
            final_prompt = f"""你是 {composite.name}。请基于以下 Worker 收集的证据，回答用户问题。

用户问题：{user_query}

证据：
{draft_context}

要求：
1. 给出结构化、带引用的回答。
2. 如果证据不足，请明确说明。
3. 引用格式为 [1], [2] 等，对应证据编号。"""
            final_answer = await self.llm.chat(
                final_prompt, "", composite.system_prompt
            )

            if reviewer is None:
                break

            review_result = await reviewer.review(
                user_query=user_query,
                plan=plan,
                worker_outputs=worker_outputs,
                draft_answer=final_answer,
            )
            reviews.append(review_result)

            if not review_result.requires_revision:
                break

            revision_count += 1

        status = "success" if revision_count <= MAX_REVISIONS else "max_revisions_reached"

        self.exec_repo.complete_execution(
            execution_id=execution_id,
            status=status,
            final_answer=final_answer,
            revision_count=revision_count,
            plan_json=plan.to_dict() if plan else {},
        )

        for review in reviews:
            self.exec_repo.create_review(
                execution_id=execution_id,
                reviewer_agent_id=reviewer.member_agent_id if reviewer else None,
                verdict=review.verdict,
                feedback=review.feedback,
                defects=review.defects,
            )

        return ExecutionResult(
            execution_id=execution_id,
            agent_id=composite_agent_id,
            user_query=user_query,
            status=status,
            final_answer=final_answer,
            plan=plan,
            reviews=reviews,
            revision_count=revision_count,
            references=all_references,
        )

    async def execute_stream(
        self,
        composite_agent_id: int,
        user_query: str,
        top_k: int = 5,
    ) -> AsyncGenerator[tuple[str, Any]]:
        """流式执行复合 Agent.

        Yields:
            (event_type, payload) tuples.
            event_type 包括: plan, step_start, step_complete, review,
            revision, references, delta, done, error
        """
        composite = self.agent_repo.get_by_id(composite_agent_id)
        if composite is None:
            yield "error", {"error": "复合 Agent 不存在"}
            return
        if composite.agent_type != "composite":
            yield "error", {"error": "该 Agent 不是复合 Agent"}
            return

        team = self.agent_repo.list_team_members(composite_agent_id)
        orchestrator_member = next(
            (m for m in team if m["role"] == "orchestrator"), None
        )
        worker_members = [m for m in team if m["role"] == "worker"]
        reviewer_member = next(
            (m for m in team if m["role"] == "reviewer"), None
        )

        if orchestrator_member is None:
            yield "error", {"error": "复合 Agent 未配置 Orchestrator"}
            return

        orchestrator = OrchestratorAgent(
            agent_id=orchestrator_member["member_agent_id"],
            name=orchestrator_member["member_name"],
            system_prompt=orchestrator_member["system_prompt"],
        )
        workers = {
            m["member_agent_id"]: WorkerAgent(
                agent_id=m["member_agent_id"],
                name=m["member_name"],
                system_prompt=m["system_prompt"],
            )
            for m in worker_members
        }
        reviewer = None
        if reviewer_member is not None:
            reviewer = ReviewerAgent(
                agent_id=reviewer_member["member_agent_id"],
                name=reviewer_member["member_name"],
                system_prompt=reviewer_member["system_prompt"],
            )

        context: dict[str, Any] = {
            "db": self.db,
            "vector_db": self.vector_db,
            "top_k": top_k,
        }
        workers_info = [
            {
                "id": m["member_agent_id"],
                "name": m["member_name"],
                "skills": m.get("skills", []),
                "step_template": m.get("step_template", {}),
            }
            for m in worker_members
        ]
        reviewer_info = (
            {
                "id": reviewer_member["member_agent_id"],
                "name": reviewer_member["member_name"],
            }
            if reviewer_member
            else None
        )

        plan: AgentPlan | None = None
        reviews: list[ReviewResult] = []
        revision_count = 0
        all_references: list[dict[str, Any]] = []

        while revision_count <= MAX_REVISIONS:
            previous_feedback = reviews[-1].feedback if reviews else None
            plan = await orchestrator.create_plan(
                user_query=user_query,
                workers=workers_info,
                reviewer=reviewer_info,
                previous_feedback=previous_feedback,
                previous_plan=plan,
            )
            yield "plan", {
                "reasoning": plan.reasoning,
                "expected_output": plan.expected_output,
                "steps": [step.to_dict() for step in plan.steps],
                "revision": revision_count,
            }

            worker_outputs: list[SkillResult] = []
            all_references = []
            for step in plan.steps:
                yield "step_start", {
                    "step_number": step.step_number,
                    "worker": workers.get(step.member_agent_id, WorkerAgent(-1, "unknown")).name,
                    "action": step.action,
                    "reason": step.reason,
                }
                worker = workers.get(step.member_agent_id)
                if worker is None:
                    step.result = SkillResult(
                        skill_name=step.action,
                        success=False,
                        error=f"未找到 member_agent_id={step.member_agent_id} 的 worker",
                    )
                    step.status = "failed"
                else:
                    worker_info = next(
                        (w for w in workers_info if w["id"] == step.member_agent_id), {}
                    )
                    template = worker_info.get("step_template") or {}
                    step.input = {**template, **step.input}
                    await worker.execute_step(user_query, step, context)
                worker_outputs.append(step.result)
                if step.result:
                    all_references.extend(step.result.references)
                yield "step_complete", {
                    "step_number": step.step_number,
                    "status": step.status,
                    "summary": step.result.content[:500] if step.result else "",
                    "error": step.result.error if step.result else None,
                }

            draft_context = "\n\n".join(
                f"[{i + 1}] {out.content[:1500]}"
                for i, out in enumerate(worker_outputs)
                if out and out.success
            )
            final_prompt = f"""你是 {composite.name}。请基于以下 Worker 收集的证据，回答用户问题。

用户问题：{user_query}

证据：
{draft_context}

要求：
1. 给出结构化、带引用的回答。
2. 如果证据不足，请明确说明。
3. 引用格式为 [1], [2] 等，对应证据编号。"""

            yield "references", all_references

            async for delta in self.llm.chat_stream(
                final_prompt, "", composite.system_prompt
            ):
                yield "delta", {"delta": delta}

            if reviewer is None:
                break

            review_result = await reviewer.review(
                user_query=user_query,
                plan=plan,
                worker_outputs=worker_outputs,
                draft_answer="",  # 流式场景暂不传完整 answer
            )
            reviews.append(review_result)
            yield "review", review_result.to_dict()

            if not review_result.requires_revision:
                break

            revision_count += 1
            yield "revision", {"revision": revision_count, "feedback": review_result.feedback}

        yield "done", {}
