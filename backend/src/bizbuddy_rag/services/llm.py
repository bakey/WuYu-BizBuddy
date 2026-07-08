"""大模型服务."""

from collections.abc import AsyncGenerator
from typing import Any

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from bizbuddy_rag.config import settings
from bizbuddy_rag.utils.exceptions import LLMError


class LLMService:
    """基于 OpenAI 协议的大模型服务；mock_ai=true 时返回 mock 回答."""

    SYSTEM_PROMPT = (
        "你是一个有帮助的助手。请严格根据以下参考资料回答用户问题，"
        "如果参考资料不足以回答问题，请明确告知。"
    )

    def __init__(self) -> None:
        """初始化异步 OpenAI 客户端或 mock 模式."""
        self.mock = settings.mock_ai
        if not self.mock and not settings.openai_api_key:
            raise LLMError("OPENAI_API_KEY 未配置")
        self.client = None
        if not self.mock:
            self.client = AsyncOpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url or None,
            )
        self.model = settings.openai_chat_model

    def _build_messages(
        self,
        prompt: str,
        context: str,
        system_prompt: str | None = None,
    ) -> list[ChatCompletionMessageParam]:
        """构造对话消息.

        Args:
            prompt: 用户问题.
            context: 参考资料拼接文本.

        Returns:
            消息列表.
        """
        content = (
            f"参考资料：\n{context}\n\n"
            f"用户问题：{prompt}\n\n"
            "请根据参考资料回答问题。"
        )
        return [
            {"role": "system", "content": system_prompt or self.SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ]

    def _mock_answer(self, prompt: str, context: str) -> str:
        """生成本地调试用的 mock 回答."""
        context_summary = context[:200].replace("\n", " ") if context else "（无上下文）"
        return (
            "【本地 Mock 回答】\n"
            f"用户问题：{prompt}\n"
            f"参考资料摘要：{context_summary}...\n\n"
            "这是 mock 模式返回的固定格式回答，用于无 OpenAI API Key 时的本地调试。"
        )

    async def chat(
        self,
        prompt: str,
        context: str,
        system_prompt: str | None = None,
    ) -> str:
        """非流式对话.

        Args:
            prompt: 用户问题.
            context: 参考资料.

        Returns:
            模型回答.

        Raises:
            LLMError: 调用失败.
        """
        if self.mock:
            return self._mock_answer(prompt, context)
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=self._build_messages(prompt, context, system_prompt),
                temperature=0.3,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            raise LLMError(f"LLM 调用失败: {exc}") from exc

    async def chat_with_tools(
        self,
        prompt: str,
        tools: list[dict[str, Any]],
        system_prompt: str | None = None,
        tool_choice: str = "auto",
    ) -> dict[str, Any]:
        """非流式 function calling 对话.

        Args:
            prompt: 用户问题.
            tools: OpenAI tools 定义列表.
            system_prompt: 系统提示词.
            tool_choice: "auto" / "none" / {"type": "function", "function": {"name": "..."}}

        Returns:
            OpenAI 响应的 message 对象字典（包含 tool_calls 或 content）。

        Raises:
            LLMError: 调用失败.
        """
        if self.mock:
            return {"role": "assistant", "content": self._mock_answer(prompt, "")}
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt or self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                tools=tools,
                tool_choice=tool_choice,
                temperature=0.3,
            )
            message = response.choices[0].message
            return {
                "role": message.role,
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in (message.tool_calls or [])
                ],
            }
        except Exception as exc:
            raise LLMError(f"LLM function calling 调用失败: {exc}") from exc

    async def chat_stream(
        self,
        prompt: str,
        context: str,
        system_prompt: str | None = None,
    ) -> AsyncGenerator[str]:
        """流式对话.

        Args:
            prompt: 用户问题.
            context: 参考资料.
            system_prompt: 自定义系统提示词.

        Yields:
            回答文本片段.

        Raises:
            LLMError: 调用失败.
        """
        if self.mock:
            answer = self._mock_answer(prompt, context)
            # 按词/短句切片，模拟流式输出。
            chunk_size = 8
            for i in range(0, len(answer), chunk_size):
                yield answer[i : i + chunk_size]
            return
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=self._build_messages(prompt, context, system_prompt),
                temperature=0.3,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as exc:
            raise LLMError(f"LLM 流式调用失败: {exc}") from exc
