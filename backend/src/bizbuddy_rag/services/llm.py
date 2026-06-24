"""大模型服务."""

from collections.abc import AsyncGenerator

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from bizbuddy_rag.config import settings
from bizbuddy_rag.utils.exceptions import LLMError


class LLMService:
    """基于 OpenAI 协议的大模型服务."""

    SYSTEM_PROMPT = (
        "你是一个有帮助的助手。请严格根据以下参考资料回答用户问题，"
        "如果参考资料不足以回答问题，请明确告知。"
    )

    def __init__(self) -> None:
        """初始化异步 OpenAI 客户端."""
        if not settings.openai_api_key:
            raise LLMError("OPENAI_API_KEY 未配置")
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
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=self._build_messages(prompt, context, system_prompt),
                temperature=0.3,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            raise LLMError(f"LLM 调用失败: {exc}") from exc

    async def chat_stream(
        self, prompt: str, context: str
    ) -> AsyncGenerator[str]:
        """流式对话.

        Args:
            prompt: 用户问题.
            context: 参考资料.

        Yields:
            回答文本片段.

        Raises:
            LLMError: 调用失败.
        """
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=self._build_messages(prompt, context),
                temperature=0.3,
                stream=True,
            )
            async for chunk in stream:
                # 部分 OpenAI 兼容网关会发空 choices 的 chunk（如末尾 usage 块），需跳过
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as exc:
            raise LLMError(f"LLM 流式调用失败: {exc}") from exc
