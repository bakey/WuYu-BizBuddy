"""Prompt 驱动型 Skill 适配器。

SKILL.md format=prompt 时，把整个 Markdown body 作为 system prompt，
把 LLM 当作执行引擎，按说明生成结果。
"""

from __future__ import annotations

from typing import Any

from bizbuddy_rag.services.agent_framework.models import SkillResult
from bizbuddy_rag.services.agent_framework.prompts import render
from bizbuddy_rag.services.agent_framework.skill_package import SkillPackage
from bizbuddy_rag.services.agent_framework.skills import Skill
from bizbuddy_rag.services.llm import LLMService


class PromptSkill(Skill):
    """纯提示型 Skill。

    用 SKILL.md 的 instructions 作为 system prompt，把 query 和参数注入
    prompt_skill.jinja2 后调用 LLM。
    """

    name = "prompt_skill"

    def __init__(self, package: SkillPackage) -> None:
        """初始化。

        Args:
            package: 解析后的 SKILL.md 技能包。
        """
        self.package = package
        self.name = package.name
        self.llm = LLMService()

    async def invoke(self, query: str, context: dict[str, Any]) -> SkillResult:
        """执行 Prompt Skill。"""
        # 把 schema 里的参数从 context 提取出来
        parameters = context.get("parameters", {})
        if not isinstance(parameters, dict):
            parameters = {}

        prompt = render(
            "prompt_skill.jinja2",
            query=query,
            parameters=parameters,
        )
        try:
            content = await self.llm.chat(
                prompt,
                "",
                system_prompt=self.package.instructions,
            )
            return SkillResult(
                skill_name=self.name,
                success=True,
                content=content,
                metadata={"skill_id": self.package.skill_id},
            )
        except Exception as exc:
            return SkillResult(
                skill_name=self.name,
                success=False,
                error=f"prompt_skill '{self.name}' failed: {exc}",
            )
