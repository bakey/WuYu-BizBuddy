"""Agent 角色实现：Orchestrator、Worker、Reviewer."""

import json
from typing import Any

from bizbuddy_rag.config import settings
from bizbuddy_rag.services.agent_framework.models import (
    AgentPlan,
    PlanStep,
    ReviewResult,
    SkillResult,
)
from bizbuddy_rag.services.agent_framework.skill_registry import SkillRegistry
from bizbuddy_rag.services.llm import LLMService


class BaseAgent:
    """Agent 基类."""

    def __init__(self, agent_id: int, name: str, system_prompt: str | None = None) -> None:
        self.agent_id = agent_id
        self.name = name
        self.system_prompt = system_prompt or ""
        self.llm = LLMService()

    async def _chat(self, prompt: str, context: str, system_prompt: str | None = None) -> str:
        """调用 LLM."""
        sp = system_prompt or self.system_prompt or None
        return await self.llm.chat(prompt, context, system_prompt=sp)


class OrchestratorAgent(BaseAgent):
    """总控 Agent：意图判断 + 计划生成."""

    async def create_plan(
        self,
        user_query: str,
        workers: list[dict[str, Any]],
        reviewer: dict[str, Any] | None,
        previous_feedback: str | None = None,
        previous_plan: AgentPlan | None = None,
    ) -> AgentPlan:
        """生成执行计划.

        Args:
            user_query: 用户问题.
            workers: 可用 worker 列表，每项包含 id/name/skills/step_template.
            reviewer: reviewer 信息.
            previous_feedback: 上一轮 reviewer 反馈（修订模式）.
            previous_plan: 上一轮 plan（修订模式）.

        Returns:
            AgentPlan.
        """
        worker_descriptions = "\n".join(
            f"- Worker ID {w['id']}: {w['name']}, skills={w.get('skills', [])}, "
            f"template={w.get('step_template', {})}"
            for w in workers
        )
        revision_context = ""
        if previous_feedback and previous_plan:
            revision_context = (
                f"\n上一轮计划执行后，Reviewer 给出的反馈是：{previous_feedback}\n"
                f"上一轮计划为：{json.dumps(previous_plan.to_dict(), ensure_ascii=False)}\n"
                "请根据反馈修订计划，重点修复被指出的缺陷。"
            )

        prompt = f"""你是 {self.name}，负责理解用户意图并制定执行计划。

用户问题：{user_query}

可用 Worker：
{worker_descriptions}

Reviewer 信息：{reviewer or '无'}

{revision_context}

请输出一个 JSON 对象，格式如下：
{{
  "reasoning": "对用户意图和计划思路的简短说明",
  "expected_output": "计划完成后应产生的输出描述",
  "steps": [
    {{
      "step_number": 1,
      "member_agent_id": <worker_id>,
      "action": "basic_rag|industry_knowledge|policy_search|...",
      "input": {{"top_k": 5, "skill_id": "...", "policy_scope": "..."}},
      "reason": "为什么需要这一步"
    }}
  ]
}}

要求：
1. steps 中的 action 必须是已注册的 skill 名称。
2. input 中需要 skill_id 的 action（industry_knowledge / policy_search）必须提供 skill_id。
3. 如果问题明确指向某个政策范围，请在 input 中设置 policy_scope（national/local/standard/case）。
4. 只输出 JSON，不要有任何额外说明。"""

        response = await self._chat(prompt, "", self.system_prompt)
        try:
            data = json.loads(self._extract_json(response))
        except json.JSONDecodeError:
            if settings.mock_ai:
                # mock 模式下 LLM 不返回 JSON，回退到默认 plan：调用所有 worker
                return AgentPlan(
                    steps=[
                        PlanStep(
                            step_number=i + 1,
                            role="worker",
                            member_agent_id=w["id"],
                            action=(w.get("step_template") or {}).get("action", "basic_rag"),
                            input=w.get("step_template") or {},
                            reason=f"默认调用 {w['name']}",
                        )
                        for i, w in enumerate(workers)
                    ],
                    expected_output="基于各维度证据的综合政策解读",
                    reasoning="mock 模式下使用默认计划：并行调用所有可用 worker",
                )
            raise

        steps = [
            PlanStep(
                step_number=s["step_number"],
                role="worker",
                member_agent_id=int(s["member_agent_id"]),
                action=s["action"],
                input=s.get("input", {}),
                reason=s.get("reason", ""),
            )
            for s in data.get("steps", [])
        ]
        return AgentPlan(
            steps=steps,
            expected_output=data.get("expected_output", ""),
            reasoning=data.get("reasoning", ""),
        )

    @staticmethod
    def _extract_json(text: str) -> str:
        """从可能包含 markdown 的文本中提取 JSON."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        return text


class WorkerAgent(BaseAgent):
    """Worker Agent：执行 Skill."""

    async def execute_step(
        self, query: str, step: PlanStep, context: dict[str, Any]
    ) -> SkillResult:
        """执行一个 PlanStep.

        Args:
            query: 原始用户问题.
            step: 当前步骤.
            context: 执行上下文（db/vector_db 等）.

        Returns:
            SkillResult.
        """
        skill = SkillRegistry.get(step.action)
        if skill is None:
            return SkillResult(
                skill_name=step.action,
                success=False,
                error=f"未知的 skill: {step.action}",
            )
        step.status = "running"
        merged_context = {**context, **step.input, "worker_name": self.name}
        result = await skill.invoke(query, merged_context)
        step.status = "completed" if result.success else "failed"
        step.result = result
        return result


class ReviewerAgent(BaseAgent):
    """评审 Agent：Review 执行结果."""

    async def review(
        self,
        user_query: str,
        plan: AgentPlan,
        worker_outputs: list[SkillResult],
        draft_answer: str,
    ) -> ReviewResult:
        """评审整体执行结果.

        Args:
            user_query: 用户问题.
            plan: 执行计划.
            worker_outputs: 各 worker 输出.
            draft_answer: 当前草稿回答.

        Returns:
            ReviewResult.
        """
        outputs_summary = "\n\n".join(
            f"Worker: {out.skill_name}\n"
            f"Success: {out.success}\n"
            f"Content summary: {out.content[:800]}..."
            for out in worker_outputs
        )

        prompt = f"""你是 {self.name}，负责评审 Agent 团队对用户问题的回答质量。

用户问题：{user_query}

执行计划：
{json.dumps(plan.to_dict(), ensure_ascii=False, indent=2)}

各 Worker 输出摘要：
{outputs_summary}

当前草稿回答：
{draft_answer}

请输出 JSON：
{{
  "verdict": "pass" 或 "revise",
  "feedback": "评审意见，如果要求修订请明确指出缺陷和如何修改",
  "defects": ["缺陷1", "缺陷2"]
}}

要求：
1. 若回答充分、引用可靠、覆盖用户问题的各个维度，请返回 pass。
2. 若存在遗漏、引用不足、逻辑错误或偏离用户问题，请返回 revise 并给出具体缺陷。
3. 只输出 JSON，不要有任何额外说明。"""

        response = await self._chat(prompt, "", self.system_prompt)
        try:
            data = json.loads(OrchestratorAgent._extract_json(response))
        except json.JSONDecodeError:
            if settings.mock_ai:
                # mock 模式下 LLM 不返回 JSON，默认通过评审
                return ReviewResult(
                    verdict="pass",
                    feedback="mock 模式下默认通过评审",
                    defects=[],
                )
            raise

        return ReviewResult(
            verdict=data.get("verdict", "revise"),
            feedback=data.get("feedback", ""),
            defects=data.get("defects", []),
        )
