"""把内部 Skill 子类包装为统一的 GenericSkill 接口."""

from typing import Any

from bizbuddy_rag.services.agent_framework.models import SkillResult
from bizbuddy_rag.services.agent_framework.skills import Skill


class NativeSkillAdapter(Skill):
    """包装内部原生 Skill 类.

    使得 SkillRegistry 可以统一通过 name 获取 Skill 实例，
    无论该 Skill 来自 Python 类定义还是数据库配置。
    """

    name = "native_adapter"

    def __init__(self, skill_class: type[Skill]) -> None:
        """初始化.

        Args:
            skill_class: 内部 Skill 类，如 BasicRAGSkill。
        """
        self._skill_class = skill_class
        self._instance: Skill | None = None
        self.name = skill_class.name

    async def invoke(self, query: str, context: dict[str, Any]) -> SkillResult:
        """调用内部 Skill。"""
        if self._instance is None:
            self._instance = self._skill_class()
        return await self._instance.invoke(query, context)

    def __repr__(self) -> str:
        return f"NativeSkillAdapter({self._skill_class.__name__})"
