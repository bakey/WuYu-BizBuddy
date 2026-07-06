"""报告格式美化：把 Markdown/纯文本转换成格式化的 HTML."""

from bizbuddy_rag.services.agent_framework.prompts import render
from bizbuddy_rag.services.llm import LLMService


class ReportFormatter:
    """报告美化器，使用 LLM 把回答文本转换为美观的 HTML。"""

    def __init__(self) -> None:
        self.llm = LLMService()

    async def format(self, text: str) -> str:
        """把文本美化成 HTML.

        Args:
            text: 原始回答文本（Markdown 或纯文本）。

        Returns:
            格式化后的 HTML 字符串。
        """
        if not text or not text.strip():
            return ""
        system_prompt = render("format_report_system.jinja2")
        prompt = render("format_report.jinja2", text=text)
        result = await self.llm.chat(prompt, "", system_prompt)
        # 简单清理：去掉可能的 markdown 代码块包裹
        result = result.strip()
        if result.startswith("```html"):
            result = result[7:]
        if result.startswith("```"):
            result = result[3:]
        if result.endswith("```"):
            result = result[:-3]
        return result.strip()
