"""Agent 执行引擎."""

import time
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from bizbuddy_rag.config import settings
from bizbuddy_rag.db.execution_repository import ExecutionRepository
from bizbuddy_rag.db.repository import AgentRepository
from bizbuddy_rag.services.agent_framework.agents import (
    OrchestratorAgent,
    ReviewerAgent,
    WorkerAgent,
)
from bizbuddy_rag.services.agent_framework.formatter import ReportFormatter
from bizbuddy_rag.services.agent_framework.models import (
    AgentPlan,
    ExecutionResult,
    PlanStep,
    ReviewResult,
    SkillResult,
)
from bizbuddy_rag.services.agent_framework.skill_registry import SkillRegistry
from bizbuddy_rag.services.llm import LLMService
from bizbuddy_rag.utils.exceptions import RAGException


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
        use_function_calling: bool = True,
    ) -> None:
        self.db = db
        self.vector_db = vector_db
        self.agent_repo = agent_repo
        self.execution_id = execution_id
        self.exec_repo = ExecutionRepository(db)
        self.llm = LLMService()
        self.use_function_calling = use_function_calling
        self.max_revisions = max(0, settings.agent_max_revisions)
        self.format_output = settings.agent_format_output
        self.formatter = ReportFormatter() if self.format_output else None
        # 加载数据库中定义的动态 Skill（OpenAI function 等）
        SkillRegistry.load_from_db(db)

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

        tools = SkillRegistry.as_openai_tools()

        while revision_count <= self.max_revisions:
            previous_feedback = reviews[-1].feedback if reviews else None
            if self.use_function_calling and tools:
                plan = await orchestrator.create_plan_with_tools(
                    user_query=user_query,
                    workers=workers_info,
                    tools=tools,
                    reviewer=reviewer_info,
                    previous_feedback=previous_feedback,
                    previous_plan=plan,
                )
            else:
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
                step.started_at = time.time()
                worker = workers.get(step.member_agent_id)
                if worker is None:
                    step.result = SkillResult(
                        skill_name=step.action,
                        success=False,
                        error=f"未找到 member_agent_id={step.member_agent_id} 的 worker",
                    )
                    step.status = "failed"
                    worker_outputs.append(step.result)
                    step.completed_at = time.time()
                    step.elapsed_ms = 0
                    continue

                # 合并 worker 的 step_template 到 step.input
                worker_info = next(
                    (w for w in workers_info if w["id"] == step.member_agent_id), {}
                )
                template = worker_info.get("step_template") or {}
                merged_input = {**template, **step.input}
                step.input = merged_input

                result = await worker.execute_step(user_query, step, context)
                step.completed_at = time.time()
                step.elapsed_ms = int((step.completed_at - step.started_at) * 1000)
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

        # 对最终输出进行 HTML 美化
        if self.formatter is not None and final_answer:
            final_answer = await self.formatter.format(final_answer)

        status = "success" if revision_count <= self.max_revisions else "max_revisions_reached"

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
                reviewer_agent_id=reviewer.agent_id if reviewer else None,
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

        tools = SkillRegistry.as_openai_tools()

        while revision_count <= self.max_revisions:
            previous_feedback = reviews[-1].feedback if reviews else None
            if self.use_function_calling and tools:
                plan = await orchestrator.create_plan_with_tools(
                    user_query=user_query,
                    workers=workers_info,
                    tools=tools,
                    reviewer=reviewer_info,
                    previous_feedback=previous_feedback,
                    previous_plan=plan,
                )
            else:
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
                # reviewer 步骤在 worker 全部执行完、生成回答后再执行
                if step.role == "reviewer":
                    continue
                step.started_at = time.time()
                yield "step_start", {
                    "step_number": step.step_number,
                    "role": step.role,
                    "worker": workers.get(step.member_agent_id, WorkerAgent(-1, "unknown")).name,
                    "action": step.action,
                    "reason": step.reason,
                    "input": step.input,
                    "started_at": step.started_at,
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
                step.completed_at = time.time()
                step.elapsed_ms = int((step.completed_at - step.started_at) * 1000)
                worker_outputs.append(step.result)
                if step.result:
                    all_references.extend(step.result.references)
                yield "step_complete", {
                    "step_number": step.step_number,
                    "status": step.status,
                    "summary": step.result.content[:500] if step.result else "",
                    "error": step.result.error if step.result else None,
                    "started_at": step.started_at,
                    "completed_at": step.completed_at,
                    "elapsed_ms": step.elapsed_ms,
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

            # 先收集完整最终回答
            final_answer_parts: list[str] = []
            async for delta in self.llm.chat_stream(
                final_prompt, "", composite.system_prompt
            ):
                final_answer_parts.append(delta)
            final_answer = "".join(final_answer_parts)

            # 对最终输出进行 HTML 美化，然后分段流式输出
            if self.formatter is not None and final_answer:
                final_answer = await self.formatter.format(final_answer)

            # 模拟流式输出格式化后的内容
            chunk_size = 12
            for i in range(0, len(final_answer), chunk_size):
                yield "delta", {"delta": final_answer[i : i + chunk_size]}

            if reviewer is None:
                break

            # 执行 plan 中已声明的 reviewer 步骤，让其作为执行轨迹的一部分展示
            review_requires_revision = False
            for step in plan.steps:
                if step.role != "reviewer":
                    continue
                step.started_at = time.time()
                yield "step_start", {
                    "step_number": step.step_number,
                    "role": step.role,
                    "worker": reviewer.name,
                    "action": step.action,
                    "reason": step.reason,
                    "input": step.input,
                    "started_at": step.started_at,
                }
                review_result = await reviewer.review(
                    user_query=user_query,
                    plan=plan,
                    worker_outputs=worker_outputs,
                    draft_answer=final_answer,
                )
                reviews.append(review_result)
                step.status = "completed"
                step.completed_at = time.time()
                step.elapsed_ms = int((step.completed_at - step.started_at) * 1000)
                yield "review", review_result.to_dict()
                yield "step_complete", {
                    "step_number": step.step_number,
                    "status": step.status,
                    "summary": review_result.feedback[:300],
                    "error": None,
                    "started_at": step.started_at,
                    "completed_at": step.completed_at,
                    "elapsed_ms": step.elapsed_ms,
                }
                review_requires_revision = review_result.requires_revision

                if review_requires_revision:
                    # 动态追加 revise 步骤并展示
                    revise_step = PlanStep(
                        step_number=len(plan.steps) + 1,
                        role="orchestrator",
                        member_agent_id=orchestrator_member["member_agent_id"],
                        action="revise",
                        input={"feedback": review_result.feedback},
                        reason="根据评审意见重新规划",
                    )
                    plan.steps.append(revise_step)
                    revise_step.started_at = time.time()
                    yield "step_start", {
                        "step_number": revise_step.step_number,
                        "role": revise_step.role,
                        "worker": orchestrator.name,
                        "action": revise_step.action,
                        "reason": revise_step.reason,
                        "input": revise_step.input,
                        "started_at": revise_step.started_at,
                    }
                    revise_step.status = "completed"
                    revise_step.completed_at = time.time()
                    revise_step.elapsed_ms = int(
                        (revise_step.completed_at - revise_step.started_at) * 1000
                    )
                    yield "step_complete", {
                        "step_number": revise_step.step_number,
                        "status": revise_step.status,
                        "summary": "",
                        "error": None,
                        "started_at": revise_step.started_at,
                        "completed_at": revise_step.completed_at,
                        "elapsed_ms": revise_step.elapsed_ms,
                    }

            if not review_requires_revision:
                break

            revision_count += 1
            yield "revision", {"revision": revision_count, "feedback": review_result.feedback}

        yield "done", {}
