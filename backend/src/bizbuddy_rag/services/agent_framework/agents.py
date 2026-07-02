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
        """生成执行计划（普通 JSON 模式）.

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
        if reviewer:
            steps.append(
                PlanStep(
                    step_number=len(steps) + 1,
                    role="reviewer",
                    member_agent_id=reviewer["id"],
                    action="review",
                    input={},
                    reason="评审各 Worker 输出与草稿回答，决定是否需要修订",
                )
            )
        return AgentPlan(
            steps=steps,
            expected_output=data.get("expected_output", ""),
            reasoning=data.get("reasoning", ""),
        )

    async def create_plan_with_tools(
        self,
        user_query: str,
        workers: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        reviewer: dict[str, Any] | None,
        previous_feedback: str | None = None,
        previous_plan: AgentPlan | None = None,
    ) -> AgentPlan:
        """使用 OpenAI function calling 生成执行计划.

        Args:
            user_query: 用户问题.
            workers: 可用 worker 列表.
            tools: OpenAI tools 定义列表.
            reviewer: reviewer 信息.
            previous_feedback: 上一轮 reviewer 反馈（修订模式）.
            previous_plan: 上一轮 plan（修订模式）.

        Returns:
            AgentPlan.
        """
        revision_context = ""
        if previous_feedback and previous_plan:
            revision_context = (
                f"\n上一轮计划执行后，Reviewer 给出的反馈是：{previous_feedback}\n"
                f"上一轮计划为：{json.dumps(previous_plan.to_dict(), ensure_ascii=False)}\n"
                "请根据反馈修订计划，重点修复被指出的缺陷。"
            )

        # 建立 (action, policy_scope) 到 member_agent_id 的映射
        worker_by_scope: dict[tuple[str, str], int] = {}
        for w in workers:
            template = w.get("step_template") or {}
            action = template.get("action")
            scope = template.get("policy_scope", "national")
            if action:
                worker_by_scope[(action, scope)] = w["id"]

        system_prompt = (
            f"你是 {self.name}，负责理解用户意图并制定执行计划。"
            "你会被提供一组 tools，每个 tool 对应一个 Worker。"
            "请根据用户问题，选择一个或多个 tool 调用，生成执行步骤。"
            "如果问题需要多个维度分析（如国家、地方、标准、案例），请为每个维度分别调用一次对应 tool，"
            "并为 policy_search 传入不同的 policy_scope。"
        )

        prompt = f"""用户问题：{user_query}

可用 Worker 与 Skill 映射：
{json.dumps(
    {w['id']: {"name": w['name'], "template": w.get('step_template', {})} for w in workers},
    ensure_ascii=False,
    indent=2,
)}

Reviewer 信息：{reviewer or '无'}

{revision_context}

请直接输出 function calls，每个 function call 代表一个执行步骤。
要求：
1. function name 必须是可用的 tool 名称。
2. arguments 中的 query 字段应提取用户问题中的关键检索词。
3. 如需 skill_id/policy_scope，请在 arguments 中提供。
4. 如果问题涉及多个政策范围（national 国家级、local 地方级、standard 标准规范、case 案例），
   请多次调用 policy_search，每次指定不同的 policy_scope，确保各维度证据都被收集。"""

        message = await self.llm.chat_with_tools(
            prompt=prompt,
            tools=tools,
            system_prompt=system_prompt,
            tool_choice="auto",
        )

        tool_calls = message.get("tool_calls", [])
        if not tool_calls:
            if settings.mock_ai:
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
            # 没有 tool calls 时 fallback 到普通 JSON 模式
            return await self.create_plan(
                user_query, workers, reviewer, previous_feedback, previous_plan
            )

        steps: list[PlanStep] = []
        for i, tc in enumerate(tool_calls, start=1):
            func = tc.get("function", {})
            action = func.get("name", "")
            try:
                arguments = json.loads(func.get("arguments", "{}"))
            except json.JSONDecodeError:
                arguments = {}

            policy_scope = arguments.get("policy_scope", "national")
            member_agent_id = worker_by_scope.get((action, policy_scope))
            if member_agent_id is None:
                # 尝试从 arguments 中查找，或 fallback 到同 action 任意 scope
                member_agent_id = arguments.get("member_agent_id")
                if member_agent_id is None:
                    member_agent_id = worker_by_scope.get((action, "national"))
                if member_agent_id is None:
                    member_agent_id = next(
                        (wid for (a, _), wid in worker_by_scope.items() if a == action), None
                    )
                if member_agent_id is None and workers:
                    member_agent_id = workers[0]["id"]

            # 合并 worker 的 step_template 和 function arguments
            template = {}
            for w in workers:
                st = w.get("step_template") or {}
                if st.get("action") == action and st.get("policy_scope", "national") == policy_scope:
                    template = dict(st)
                    break
            # 若未精确匹配，fallback 到同 action 的第一个 template
            if not template:
                for w in workers:
                    st = w.get("step_template") or {}
                    if st.get("action") == action:
                        template = dict(st)
                        break
            merged_input = {**template, **arguments}
            merged_input.pop("query", None)  # query 单独传入，不重复放在 input 中

            steps.append(
                PlanStep(
                    step_number=i,
                    role="worker",
                    member_agent_id=int(member_agent_id),
                    action=action,
                    input=merged_input,
                    reason=arguments.get("reason", f"调用 {action} 获取相关证据"),
                )
            )

        if reviewer:
            steps.append(
                PlanStep(
                    step_number=len(steps) + 1,
                    role="reviewer",
                    member_agent_id=reviewer["id"],
                    action="review",
                    input={},
                    reason="评审各 Worker 输出与草稿回答，决定是否需要修订",
                )
            )
        return AgentPlan(
            steps=steps,
            expected_output="基于各维度证据的综合政策解读",
            reasoning=f"通过 function calling 生成 {len(steps)} 个执行步骤",
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
