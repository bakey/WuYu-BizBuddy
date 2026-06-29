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


class ChatTaskUpdate(BaseModel):
    """更新聊天任务请求."""

    title: str | None = Field(default=None, min_length=1, max_length=512)
    meta: str | None = Field(default=None, max_length=255)
    pin: str | None = Field(default=None, max_length=50)
    pinned: bool | None = None
    active: bool | None = None


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


class AgentUpdate(BaseModel):
    """更新 Agent 请求."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
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


class AgentOut(BaseModel):
    """Agent 响应."""

    id: int
    name: str
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

    model_config = ConfigDict(from_attributes=True)


class AgentCategoryStat(BaseModel):
    """Agent 分类统计."""

    label: str
    count: int
