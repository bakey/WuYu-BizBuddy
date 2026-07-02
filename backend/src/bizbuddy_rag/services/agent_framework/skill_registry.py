"""Skill 注册表."""

from typing import Any

from sqlalchemy.orm import Session

from bizbuddy_rag.db.repository import SkillRepository

from .adapters import NativeSkillAdapter, OpenAIFunctionSkillAdapter
from .skills import BasicRAGSkill, IndustryKnowledgeSkillAdapter, PolicySearchSkill, Skill


class SkillRegistry:
    """Skill 注册表，根据 action 名称解析并创建 Skill 实例。

    支持两种来源：
    1. 原生 Python Skill 类（硬编码）。
    2. 数据库 skills 表中定义的外部 Skill（如 OpenAI function）。
    """

    _skills: dict[str, type[Skill]] = {
        "basic_rag": BasicRAGSkill,
        "industry_knowledge": IndustryKnowledgeSkillAdapter,
        "policy_search": PolicySearchSkill,
    }

    # 缓存已实例化的 adapter（用于数据库动态加载）
    _adapters: dict[str, Skill] = {}

    @classmethod
    def register(cls, name: str, skill_class: type[Skill]) -> None:
        """注册新的原生 Skill 类。"""
        cls._skills[name] = skill_class

    @classmethod
    def register_adapter(cls, name: str, skill: Skill) -> None:
        """注册 Skill 实例（通常来自数据库配置）。"""
        cls._adapters[name] = skill

    @classmethod
    def get(cls, name: str) -> Skill | None:
        """根据名称获取 Skill 实例。

        查找顺序：
        1. 已缓存的 adapter（数据库动态加载）。
        2. 原生 Skill 类。
        """
        if name in cls._adapters:
            return cls._adapters[name]
        skill_class = cls._skills.get(name)
        if skill_class is None:
            return None
        return NativeSkillAdapter(skill_class)

    @classmethod
    def list_skills(cls) -> list[str]:
        """列出所有已注册 Skill 名称。"""
        return list(dict.fromkeys(list(cls._skills.keys()) + list(cls._adapters.keys())))

    @classmethod
    def as_openai_tools(cls) -> list[dict[str, Any]]:
        """把所有已注册 Skill 转换为 OpenAI tools 格式。

        原生 Skill 会生成默认的 function schema；
        OpenAIFunctionSkillAdapter 会直接使用自身 schema。
        """
        tools: list[dict[str, Any]] = []
        for name in cls.list_skills():
            skill = cls.get(name)
            if skill is None:
                continue
            if isinstance(skill, OpenAIFunctionSkillAdapter):
                tools.append(skill.as_openai_tool())
            elif name == "policy_search":
                # policy_search 支持按范围多次调用，schema 需暴露 policy_scope
                tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": name,
                            "description": getattr(
                                skill, "description", "按政策范围检索相关法规、标准或案例"
                            ),
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "query": {
                                        "type": "string",
                                        "description": "用户的原始问题或提取的检索关键词",
                                    },
                                    "policy_scope": {
                                        "type": "string",
                                        "enum": ["national", "local", "standard", "case"],
                                        "description": "检索范围：national 国家级、local 地方级、standard 标准规范、case 案例",
                                    },
                                },
                                "required": ["query", "policy_scope"],
                            },
                        },
                    }
                )
            else:
                tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": name,
                            "description": getattr(
                                skill, "description", f"调用 {name} skill"
                            ),
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "query": {
                                        "type": "string",
                                        "description": "用户的原始问题",
                                    }
                                },
                            },
                        },
                    }
                )
        return tools

    @classmethod
    def load_from_db(cls, db: Session) -> None:
        """从数据库加载 Skill 定义并注册到注册表。"""
        repo = SkillRepository(db)
        skills = repo.list_skills(only_enabled=True)
        for skill_def in skills:
            if skill_def.format == "openai_function":
                adapter = OpenAIFunctionSkillAdapter(
                    name=skill_def.name,
                    description=skill_def.description,
                    parameters_schema=skill_def.parameters_schema,
                    config=skill_def.config,
                )
                cls.register_adapter(skill_def.name, adapter)
            elif skill_def.format == "native" and skill_def.handler_module:
                # 支持通过模块路径动态加载内部 Skill
                native = cls._load_native(skill_def.handler_module)
                if native is not None:
                    cls.register_adapter(skill_def.name, native)

    @classmethod
    def clear_adapters(cls) -> None:
        """清空动态加载的 adapter，便于重新加载。"""
        cls._adapters.clear()

    @classmethod
    def _load_native(cls, handler_module: str) -> Skill | None:
        """根据模块路径加载原生 Skill。"""
        try:
            import importlib

            module_path, class_name = handler_module.rsplit(".", 1)
            module = importlib.import_module(module_path)
            skill_class = getattr(module, class_name)
            return NativeSkillAdapter(skill_class)
        except Exception:
            return None
