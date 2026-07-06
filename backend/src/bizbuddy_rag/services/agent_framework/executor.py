"""Agent 执行引擎."""

import asyncio
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
from bizbuddy_rag.services.agent_framework.prompts import render
from bizbuddy_rag.services.agent_framework.skill_registry import SkillRegistry
from bizbuddy_rag.services.bge_embedding import BgeM3EmbeddingService
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

    async def _precompute_query_vector(self, query: str) -> list[float] | None:
        """在 asyncio 线程池中预计算 bge-m3 query 向量，供所有 Worker 复用。

        失败时返回 None，Worker 会自行再 embed 一次，逻辑不受影响。
        """
        try:
            svc = BgeM3EmbeddingService()
            return await asyncio.to_thread(svc.embed_query, query)
        except Exception:
            return None


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

        # 提前预计算 query 向量：多 Worker 共享，省 bge-m3 推理。
        query_vector = await self._precompute_query_vector(user_query)

        context: dict[str, Any] = {
            "db": self.db,
            "vector_db": self.vector_db,
            "top_k": top_k,
            "_query_vector": query_vector,
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
                if step.role == "reviewer":
                    continue
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
            final_prompt = render(
                "final_answer.jinja2",
                composite_name=composite.name,
                user_query=user_query,
                draft_context=draft_context,
            )
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
            revision, references, delta, answer_html, done, error
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

        query_vector = await self._precompute_query_vector(user_query)

        context: dict[str, Any] = {
            "db": self.db,
            "vector_db": self.vector_db,
            "top_k": top_k,
            "_query_vector": query_vector,
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

        execution_id = self.execution_id
        if execution_id is None:
            execution_id = self.exec_repo.create_execution(
                agent_id=composite_agent_id,
                user_query=user_query,
            )

        # 最终答案累积用于 formatter；每轮 revision 会覆盖，只保留最后一次。
        final_answer = ""

        # ── 意图预判（Router-first 短路）─────────────────────────────
        # 规则级识别：显然的整句寒暄/致谢/自我介绍 → 直接跳过 Orchestrator，
        # 让下面的循环用一个"空计划 + intent=chitchat"的方式走 chitchat 分支。
        # 命中率不高但省 3-5s Orchestrator LLM；未命中时继续走 LLM 判定（B）。
        from bizbuddy_rag.services.agent_framework.agents import rule_based_intent
        pre_intent = rule_based_intent(user_query)
        if pre_intent == "chitchat":
            yield "phase", {
                "phase": "intent",
                "revision": 0,
                "message": "识别为寒暄/元问题，直接回答…",
            }
            plan = AgentPlan(
                steps=[],
                expected_output="",
                reasoning="规则命中：显然是寒暄/元问题，跳过检索工具直接回答",
                intent="chitchat",
            )
            yield "plan", {
                "reasoning": plan.reasoning,
                "expected_output": plan.expected_output,
                "steps": [],
                "revision": 0,
                "intent": "chitchat",
            }
            # 进入 chitchat 直答分支（复用主循环中的"起草回答"阶段，但不做 worker/reviewer）。
            # 为了减少代码重复，直接在这里把 chitchat 分支跑完然后返回。
            yield "references", []
            yield "phase", {"phase": "drafting", "revision": 0, "message": "生成回答…"}
            chitchat_prompt = (
                f"用户说：{user_query}\n\n"
                "请以你的身份用简洁、友好的自然语言回应。"
                "如果是打招呼，直接问好并简短说明你能帮什么；"
                "如果是自我介绍问询，简要介绍你的定位和主要能力；"
                "如果是致谢或告别，礼貌回应即可；"
                "不要罗列长清单，控制在 3 句以内。"
            )
            final_answer_parts: list[str] = []
            async for delta in self.llm.chat_stream(
                chitchat_prompt, "", composite.system_prompt
            ):
                final_answer_parts.append(delta)
                yield "delta", {"delta": delta, "revision": 0}
            final_answer = "".join(final_answer_parts)

            # 可选 HTML 美化，同主流程逻辑。
            formatted_html: str | None = None
            if self.formatter is not None and final_answer:
                yield "phase", {"phase": "finalizing", "revision": 0, "message": "生成最终排版…"}
                try:
                    formatted_html = await self.formatter.format(final_answer)
                    yield "answer_html", {"html": formatted_html}
                except Exception:
                    formatted_html = None

            self.exec_repo.complete_execution(
                execution_id=execution_id,
                status="success",
                final_answer=formatted_html or final_answer,
                revision_count=0,
                plan_json=plan.to_dict(),
            )
            yield "done", {
                "execution_id": str(execution_id),
                "revision_count": 0,
                "reviews": 0,
                "intent": "chitchat",
            }
            return

        # 主循环：每一轮 = 生成 Plan → 执行 Worker → 生成回答 → 评审。
        # 只有在还允许触发修订时（revision_count < max_revisions）才做评审，
        # 否则本轮回答即最终答案。这保证用户看到的 REVISE 数量 == 触发的修订数量，
        # 不会出现"最后一次评审判 revise 但没修订"的悬空反馈。
        while True:
            # ── 阶段 1：规划 ────────────────────────────────────────────
            yield "phase", {
                "phase": "planning",
                "revision": revision_count,
                "message": (
                    f"第 {revision_count + 1} 轮：根据评审意见重新规划中…"
                    if revision_count > 0
                    else "分析问题并制定执行计划…"
                ),
            }
            previous_feedback = reviews[-1].feedback if reviews else None
            if self.use_function_calling and tools:
                plan_task = asyncio.create_task(
                    orchestrator.create_plan_with_tools(
                        user_query=user_query,
                        workers=workers_info,
                        tools=tools,
                        reviewer=reviewer_info,
                        previous_feedback=previous_feedback,
                        previous_plan=plan,
                    )
                )
            else:
                plan_task = asyncio.create_task(
                    orchestrator.create_plan(
                        user_query=user_query,
                        workers=workers_info,
                        reviewer=reviewer_info,
                        previous_feedback=previous_feedback,
                        previous_plan=plan,
                    )
                )
            # 每 10s 保活，避免中间层空闲超时。
            while not plan_task.done():
                try:
                    await asyncio.wait_for(asyncio.shield(plan_task), timeout=10.0)
                except asyncio.TimeoutError:
                    yield "heartbeat", {"phase": "planning", "ts": time.time()}
            plan = plan_task.result()
            yield "plan", {
                "reasoning": plan.reasoning,
                "expected_output": plan.expected_output,
                "steps": [
                    {**step.to_dict(), "revision": revision_count}
                    for step in plan.steps
                ],
                "revision": revision_count,
                "intent": plan.intent,
            }

            # ── LLM 判为 chitchat：跳过 Worker/Reviewer，直接生成答案 ──
            # 场景：规则短路没命中，但 Orchestrator LLM 判断"不需要工具"（如"你是谁"）。
            if plan.intent == "chitchat":
                yield "references", []
                yield "phase", {
                    "phase": "drafting",
                    "revision": revision_count,
                    "message": "识别为寒暄/元问题，直接回答…",
                }
                chitchat_prompt = (
                    f"用户说：{user_query}\n\n"
                    "请以你的身份用简洁、友好的自然语言回应。"
                    "如果是打招呼，直接问好并简短说明你能帮什么；"
                    "如果是自我介绍问询，简要介绍你的定位和主要能力；"
                    "如果是致谢或告别，礼貌回应即可；"
                    "不要罗列长清单，控制在 3 句以内。"
                )
                final_answer_parts: list[str] = []
                async for delta in self.llm.chat_stream(
                    chitchat_prompt, "", composite.system_prompt
                ):
                    final_answer_parts.append(delta)
                    yield "delta", {"delta": delta, "revision": revision_count}
                final_answer = "".join(final_answer_parts)

                formatted_html: str | None = None
                if self.formatter is not None and final_answer:
                    yield "phase", {
                        "phase": "finalizing",
                        "revision": revision_count,
                        "message": "生成最终排版…",
                    }
                    try:
                        formatted_html = await self.formatter.format(final_answer)
                        yield "answer_html", {"html": formatted_html}
                    except Exception:
                        formatted_html = None

                self.exec_repo.complete_execution(
                    execution_id=execution_id,
                    status="success",
                    final_answer=formatted_html or final_answer,
                    revision_count=revision_count,
                    plan_json=plan.to_dict(),
                )
                yield "done", {
                    "execution_id": str(execution_id),
                    "revision_count": revision_count,
                    "reviews": len(reviews),
                    "intent": "chitchat",
                }
                return

            # ── 阶段 2：Worker 执行 ────────────────────────────────────
            yield "phase", {
                "phase": "executing",
                "revision": revision_count,
                "message": "调用检索技能收集证据…",
            }
            worker_outputs: list[SkillResult] = []
            all_references = []
            step_db_ids: dict[int, UUID] = {}
            for step in plan.steps:
                if step.role == "reviewer":
                    continue

                worker_info = next(
                    (w for w in workers_info if w["id"] == step.member_agent_id), {}
                )
                template = worker_info.get("step_template") or {}
                step.input = {**template, **step.input}

                step.started_at = time.time()
                worker = workers.get(step.member_agent_id)
                worker_name = worker.name if worker else "unknown"

                step_db_id = self.exec_repo.create_step(
                    execution_id=execution_id,
                    step_number=step.step_number,
                    role=step.role,
                    member_agent_id=step.member_agent_id,
                    action=step.action,
                    input_json=step.input,
                    status="running",
                )
                step_db_ids[step.step_number] = step_db_id

                yield "step_start", {
                    "step_number": step.step_number,
                    "revision": revision_count,
                    "role": step.role,
                    "worker": worker_name,
                    "action": step.action,
                    "reason": step.reason,
                    "input": step.input,
                    "started_at": step.started_at,
                }

                if worker is None:
                    step.result = SkillResult(
                        skill_name=step.action,
                        success=False,
                        error=f"未找到 member_agent_id={step.member_agent_id} 的 worker",
                    )
                    step.status = "failed"
                else:
                    await worker.execute_step(user_query, step, context)

                step.completed_at = time.time()
                step.elapsed_ms = int((step.completed_at - step.started_at) * 1000)
                worker_outputs.append(step.result)
                if step.result:
                    all_references.extend(step.result.references)

                self.exec_repo.update_step(
                    step_id=step_db_id,
                    output_json=step.result.to_dict() if step.result else None,
                    status=step.status,
                )

                yield "step_complete", {
                    "step_number": step.step_number,
                    "revision": revision_count,
                    "status": step.status,
                    "summary": step.result.content[:500] if step.result else "",
                    "error": step.result.error if step.result else None,
                    "started_at": step.started_at,
                    "completed_at": step.completed_at,
                    "elapsed_ms": step.elapsed_ms,
                }

            # ── 阶段 3：起草回答 ────────────────────────────────────────
            draft_context = "\n\n".join(
                f"[{i + 1}] {out.content[:1500]}"
                for i, out in enumerate(worker_outputs)
                if out and out.success
            )
            final_prompt = render(
                "final_answer.jinja2",
                composite_name=composite.name,
                user_query=user_query,
                draft_context=draft_context,
            )

            yield "references", all_references

            # 新一轮开始前先让前端清空上一轮的 delta 累积，避免答案被拼接。
            if revision_count > 0:
                yield "answer_reset", {"revision": revision_count}

            yield "phase", {
                "phase": "drafting",
                "revision": revision_count,
                "message": "根据证据生成回答…",
            }

            final_answer_parts: list[str] = []
            async for delta in self.llm.chat_stream(
                final_prompt, "", composite.system_prompt
            ):
                final_answer_parts.append(delta)
                yield "delta", {"delta": delta, "revision": revision_count}
            final_answer = "".join(final_answer_parts)

            # ── 阶段 4：判断是否需要评审 ────────────────────────────────
            # 没有 reviewer，或已经用完修订次数 → 本轮就是最终答案，直接跳出。
            if reviewer is None or revision_count >= self.max_revisions:
                break

            # ── 阶段 5：评审 ────────────────────────────────────────────
            review_step = next(
                (s for s in plan.steps if s.role == "reviewer"), None
            )
            if review_step is None:
                # 兜底：Orchestrator 没生成 reviewer step，也直接结束。
                break

            yield "phase", {
                "phase": "reviewing",
                "revision": revision_count,
                "message": "评审当前回答的完整性与引用可靠性…",
            }

            review_step.started_at = time.time()
            review_db_id = self.exec_repo.create_step(
                execution_id=execution_id,
                step_number=review_step.step_number,
                role=review_step.role,
                member_agent_id=review_step.member_agent_id,
                action=review_step.action,
                input_json=review_step.input,
                status="running",
            )
            yield "step_start", {
                "step_number": review_step.step_number,
                "revision": revision_count,
                "role": review_step.role,
                "worker": reviewer.name,
                "action": review_step.action,
                "reason": review_step.reason,
                "input": review_step.input,
                "started_at": review_step.started_at,
            }

            # Reviewer LLM 通常 25-50s，其间不发字节容易触发 nginx 空闲超时。
            # 每 10s 吐一个 heartbeat 保活。
            review_task = asyncio.create_task(
                reviewer.review(
                    user_query=user_query,
                    plan=plan,
                    worker_outputs=worker_outputs,
                    draft_answer=final_answer,
                )
            )
            while not review_task.done():
                try:
                    await asyncio.wait_for(asyncio.shield(review_task), timeout=10.0)
                except asyncio.TimeoutError:
                    yield "heartbeat", {"phase": "reviewing", "ts": time.time()}
            review_result = review_task.result()
            reviews.append(review_result)
            review_step.status = "completed"
            review_step.completed_at = time.time()
            review_step.elapsed_ms = int(
                (review_step.completed_at - review_step.started_at) * 1000
            )

            self.exec_repo.update_step(
                step_id=review_db_id,
                output_json=review_result.to_dict(),
                status=review_step.status,
                review_feedback=review_result.feedback,
            )
            self.exec_repo.create_review(
                execution_id=execution_id,
                reviewer_agent_id=reviewer.agent_id,
                verdict=review_result.verdict,
                feedback=review_result.feedback,
                defects=review_result.defects,
            )

            yield "review", {**review_result.to_dict(), "revision": revision_count}
            yield "step_complete", {
                "step_number": review_step.step_number,
                "revision": revision_count,
                "status": review_step.status,
                "summary": review_result.feedback[:300],
                "error": None,
                "started_at": review_step.started_at,
                "completed_at": review_step.completed_at,
                "elapsed_ms": review_step.elapsed_ms,
            }

            # 评审通过：本轮即最终答案。
            if not review_result.requires_revision:
                break

            # 评审要求修订：进入下一轮。
            revision_count += 1
            yield "revision", {
                "revision": revision_count,
                "feedback": review_result.feedback,
            }

        # ── 阶段 6：最终 HTML 美化 ─────────────────────────────────────
        formatted_html: str | None = None
        if self.formatter is not None and final_answer:
            yield "phase", {
                "phase": "finalizing",
                "revision": revision_count,
                "message": "生成最终排版…",
            }
            try:
                formatted_html = await self.formatter.format(final_answer)
                yield "answer_html", {"html": formatted_html}
            except Exception:
                formatted_html = None

        # revision_count 语义为"实际发生的修订次数"，一定 ≤ max_revisions。
        status = "success"
        self.exec_repo.complete_execution(
            execution_id=execution_id,
            status=status,
            final_answer=formatted_html or final_answer,
            revision_count=revision_count,
            plan_json=plan.to_dict() if plan else {},
        )

        yield "done", {
            "execution_id": str(execution_id),
            "revision_count": revision_count,
            "reviews": len(reviews),
        }
