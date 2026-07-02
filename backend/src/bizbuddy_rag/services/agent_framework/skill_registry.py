"""Skill 注册表."""


from bizbuddy_rag.services.agent_framework.skills import (
    BasicRAGSkill,
    IndustryKnowledgeSkillAdapter,
    PolicySearchSkill,
    Skill,
)


class SkillRegistry:
    """Skill 注册表，根据 action 名称解析并创建 Skill 实例."""

    _skills: dict[str, type[Skill]] = {
        "basic_rag": BasicRAGSkill,
        "industry_knowledge": IndustryKnowledgeSkillAdapter,
        "policy_search": PolicySearchSkill,
    }

    @classmethod
    def register(cls, name: str, skill_class: type[Skill]) -> None:
        """注册新的 Skill."""
        cls._skills[name] = skill_class

    @classmethod
    def get(cls, name: str) -> Skill | None:
        """根据名称获取 Skill 实例."""
        skill_class = cls._skills.get(name)
        if skill_class is None:
            return None
        return skill_class()

    @classmethod
    def list_skills(cls) -> list[str]:
        """列出所有已注册 Skill 名称."""
        return list(cls._skills.keys())
