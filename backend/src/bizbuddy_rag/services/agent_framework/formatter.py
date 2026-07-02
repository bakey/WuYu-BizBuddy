"""报告格式美化：把 Markdown/纯文本转换成格式化的 HTML."""

from bizbuddy_rag.services.llm import LLMService


class ReportFormatter:
    """报告美化器，使用 LLM 把回答文本转换为美观的 HTML。"""

    SYSTEM_PROMPT = (
        "你是报告格式美化专家。请把用户提供的 Markdown/纯文本内容转换成"
        "格式美观、结构清晰的 HTML。\n\n"
        "要求：\n"
        "1. 只输出 HTML 片段（放在 <div class=\"formatted-report\"> 中），"
        "不要输出任何额外说明。\n"
        "2. 保留原文的所有核心信息，不要增删内容。\n"
        "3. 使用语义化标签：标题用 <h3>/<h4>，列表用 <ul>/<ol>，"
        "重点用 <strong>，引用用 <blockquote>。\n"
        "4. 每个段落之间保留合适间距，适当使用卡片式布局或分隔线让结构更清晰。\n"
        "5. 如果原文包含 [1], [2] 这类引用标记，保留原样。\n"
        "6. 不要使用 <html>, <head>, <body> 等文档级标签。"
    )

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
        prompt = f"请把以下内容转换为格式美观的 HTML：\n\n{text}"
        result = await self.llm.chat(prompt, "", self.SYSTEM_PROMPT)
        # 简单清理：去掉可能的 markdown 代码块包裹
        result = result.strip()
        if result.startswith("```html"):
            result = result[7:]
        if result.startswith("```"):
            result = result[3:]
        if result.endswith("```"):
            result = result[:-3]
        return result.strip()
