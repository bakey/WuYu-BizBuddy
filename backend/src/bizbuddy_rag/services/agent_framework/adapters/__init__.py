"""Skill 适配器：把外部 Skill 格式转换为内部 Skill 接口."""

from .native_skill import NativeSkillAdapter
from .openai_function import OpenAIFunctionSkillAdapter
from .prompt_skill import PromptSkill

__all__ = ["NativeSkillAdapter", "OpenAIFunctionSkillAdapter", "PromptSkill"]
