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
