"""Pydantic 请求/响应模型."""

from pydantic import BaseModel, ConfigDict, Field


class DocumentCreate(BaseModel):
    """创建文档请求."""

    content: str = Field(..., min_length=1, description="文档内容")
    source: str | None = Field(default=None, description="文档来源")
    metadata: dict[str, object] | None = Field(default=None, description="附加元数据")


class DocumentOut(BaseModel):
    """文档响应."""

    id: int
    content: str
    source: str | None
    metadata: dict[str, object] | None

    model_config = ConfigDict(from_attributes=True)


class QueryRequest(BaseModel):
    """RAG 查询请求."""

    prompt: str = Field(..., min_length=1, description="用户问题")
    top_k: int = Field(default=5, ge=1, le=20, description="检索top_k文档")
    stream: bool = Field(default=False, description="是否流式返回")


class RetrieveRequest(BaseModel):
    """纯检索请求."""

    query: str = Field(..., min_length=1, description="检索query")
    top_k: int = Field(default=5, ge=1, le=20, description="检索top_k文档")


class RetrievedChunk(BaseModel):
    """检索到的文档片段."""

    content: str
    source: str | None
    score: float
    metadata: dict[str, object] | None


class RAGResponse(BaseModel):
    """RAG 回答响应."""

    answer: str
    references: list[RetrievedChunk]


class HealthResponse(BaseModel):
    """健康检查响应."""

    status: str
    version: str


class ChatTaskCreate(BaseModel):
    """创建聊天任务请求."""

    title: str = Field(..., min_length=1, max_length=512, description="任务标题")
    meta: str | None = Field(default=None, max_length=255, description="任务副标题")
    pin: str | None = Field(default="", max_length=50, description="置顶标识样式")
    pinned: bool = Field(default=False, description="是否置顶")
    agent_name: str | None = Field(default=None, max_length=255, description="Agent 名称")
    agent_icon: str | None = Field(default=None, max_length=50, description="Agent 图标")
    agent_id: int | None = Field(default=None, description="Agent ID")


class ChatTaskUpdate(BaseModel):
    """更新聊天任务请求."""

    title: str | None = Field(default=None, min_length=1, max_length=512)
    meta: str | None = Field(default=None, max_length=255)
    pin: str | None = Field(default=None, max_length=50)
    pinned: bool | None = None
    active: bool | None = None
    agent_id: int | None = Field(default=None, description="Agent ID")


class ChatTaskOut(BaseModel):
    """聊天任务响应."""

    id: int
    title: str
    meta: str | None
    pin: str
    pinned: bool
    active: bool
    agent_name: str | None
    agent_icon: str | None
    agent_id: int | None
    created_at: str | None
    updated_at: str | None

    model_config = ConfigDict(from_attributes=True)


class AgentTag(BaseModel):
    """Agent 标签."""

    label: str
    cls: str


class AgentCreate(BaseModel):
    """创建 Agent 请求."""

    name: str = Field(..., min_length=1, max_length=255)
    agent_type: str = Field(default="simple", max_length=20)
    icon: str = Field(..., max_length=50)
    bg: str = Field(..., max_length=100)
    color: str = Field(..., max_length=100)
    desc: str = Field(..., min_length=1)
    skills: list[str] = Field(default_factory=list)
    users: str = Field(default="0", max_length=50)
    rating: float = Field(default=0.0, ge=0.0, le=5.0)
    featured: bool = Field(default=False)
    category: str = Field(..., max_length=100)
    tag: AgentTag | None = None
    source: str = Field(default="官方 Agent", max_length=50)
    enabled: bool = Field(default=True)
    system_prompt: str | None = Field(default=None)
    default_top_k: int = Field(default=5, ge=1, le=20)
    retrieval_mode: str = Field(default="basic_rag")
    industry_skill_id: str | None = Field(default=None)
    config: dict[str, object] | None = Field(default=None)


class AgentUpdate(BaseModel):
    """更新 Agent 请求."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    agent_type: str | None = Field(default=None, max_length=20)
    icon: str | None = Field(default=None, max_length=50)
    bg: str | None = Field(default=None, max_length=100)
    color: str | None = Field(default=None, max_length=100)
    desc: str | None = Field(default=None, min_length=1)
    skills: list[str] | None = None
    users: str | None = Field(default=None, max_length=50)
    rating: float | None = Field(default=None, ge=0.0, le=5.0)
    featured: bool | None = None
    category: str | None = Field(default=None, max_length=100)
    tag: AgentTag | None = None
    source: str | None = Field(default=None, max_length=50)
    enabled: bool | None = None
    system_prompt: str | None = Field(default=None)
    default_top_k: int | None = Field(default=None, ge=1, le=20)
    retrieval_mode: str | None = Field(default=None)
    industry_skill_id: str | None = Field(default=None)
    config: dict[str, object] | None = Field(default=None)


class AgentOut(BaseModel):
    """Agent 响应."""

    id: int
    name: str
    agent_type: str
    icon: str
    bg: str
    color: str
    desc: str
    skills: list[str]
    users: str
    rating: float
    featured: bool
    category: str
    tag: AgentTag | None
    source: str
    enabled: bool
    system_prompt: str | None
    default_top_k: int
    retrieval_mode: str
    industry_skill_id: str | None
    config: dict[str, object] | None

    model_config = ConfigDict(from_attributes=True)


class AgentTeamMemberCreate(BaseModel):
    """添加团队成员请求."""

    member_agent_id: int = Field(..., description="成员 Agent ID")
    role: str = Field(..., pattern="^(orchestrator|worker|reviewer)$")
    step_template: dict[str, object] | None = Field(default=None)
    order_index: int = Field(default=0)


class AgentTeamMemberOut(BaseModel):
    """团队成员响应."""

    id: int
    agent_id: int
    member_agent_id: int
    member_name: str
    member_icon: str
    role: str
    step_template: dict[str, object] | None
    order_index: int

    model_config = ConfigDict(from_attributes=True)


class AgentCategoryStat(BaseModel):
    """Agent 分类统计."""

    label: str
    count: int


class AgentExecutionCreate(BaseModel):
    """创建 Agent 执行请求."""

    prompt: str = Field(..., min_length=1, description="用户问题")
    top_k: int = Field(default=5, ge=1, le=20, description="检索top_k文档")


class AgentExecutionOut(BaseModel):
    """Agent 执行记录响应."""

    id: str
    agent_id: int
    agent_name: str
    user_query: str
    status: str
    revision_count: int
    created_at: str | None
    updated_at: str | None

    model_config = ConfigDict(from_attributes=True)


class AgentExecutionDetailOut(BaseModel):
    """Agent 执行详情响应."""

    id: str
    agent_id: int
    agent_name: str
    user_query: str
    status: str
    final_answer: str | None
    plan_json: dict[str, object] | None
    revision_count: int
    steps: list[dict[str, object]]
    reviews: list[dict[str, object]]
    created_at: str | None
    updated_at: str | None
