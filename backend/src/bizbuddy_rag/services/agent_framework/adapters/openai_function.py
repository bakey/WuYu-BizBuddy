"""OpenAI function calling 格式 Skill 适配器."""

from typing import Any

from bizbuddy_rag.services.agent_framework.models import SkillResult
from bizbuddy_rag.services.agent_framework.skills import Skill


class OpenAIFunctionSkillAdapter(Skill):
    """把 OpenAI function 定义映射为内部 Skill。

    OpenAI function 本身只是一份 JSON Schema 描述，真正的执行逻辑可能有两种：

    1. **映射到内部已有 Skill**：function 的 name 对应某个内部 Skill 名称，
       适配器把参数合并后调用该内部 Skill。
    2. **外部 HTTP 回调**：function 配置中包含 endpoint，适配器把参数 POST 过去。

    本适配器优先尝试映射到内部 Skill；如果 config 中包含 endpoint，则走 HTTP 调用。
    """

    name = "openai_function_adapter"

    def __init__(
        self,
        name: str,
        description: str,
        parameters_schema: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> None:
        """初始化。

        Args:
            name: function 名称。
            description: function 描述。
            parameters_schema: OpenAI function parameters JSON Schema。
            config: 外部配置，可包含 endpoint、method、headers、target_skill 等。
        """
        self.name = name
        self.description = description
        self.parameters_schema = parameters_schema
        self.config = config or {}

    def as_openai_tool(self) -> dict[str, Any]:
        """转换为 OpenAI tool 格式。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }

    async def invoke(self, query: str, context: dict[str, Any]) -> SkillResult:
        """执行 function。

        执行策略：
        1. 若 config.target_skill 存在，调用对应内部 Skill。
        2. 若 config.endpoint 存在，发起 HTTP 调用。
        3. 否则尝试按 name 直接查找内部 Skill。
        """
        # 延迟导入避免循环依赖
        from bizbuddy_rag.services.agent_framework.skill_registry import SkillRegistry

        target_skill = self.config.get("target_skill") or self.name
        if target_skill:
            skill = SkillRegistry.get(target_skill)
            if skill is not None:
                merged = {**context, "skill_id": context.get("skill_id")}
                return await skill.invoke(query, merged)

        endpoint = self.config.get("endpoint")
        if endpoint:
            return await self._invoke_http(query, context, endpoint)

        return SkillResult(
            skill_name=self.name,
            success=False,
            error=f"OpenAI function '{self.name}' 未配置 target_skill 或 endpoint",
        )

    async def _invoke_http(
        self, query: str, context: dict[str, Any], endpoint: str
    ) -> SkillResult:
        """调用外部 HTTP endpoint。"""
        import httpx

        method = self.config.get("method", "POST").upper()
        headers = self.config.get("headers", {})
        payload = {
            "query": query,
            **context,
            "function_name": self.name,
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                if method == "GET":
                    resp = await client.get(endpoint, params=payload, headers=headers)
                else:
                    resp = await client.post(endpoint, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            return SkillResult(
                skill_name=self.name,
                success=data.get("success", True),
                content=data.get("content", ""),
                references=data.get("references", []),
                metadata=data.get("metadata", {}),
                error=data.get("error"),
            )
        except Exception as exc:
            return SkillResult(
                skill_name=self.name,
                success=False,
                error=f"调用外部 function endpoint 失败: {exc}",
            )
