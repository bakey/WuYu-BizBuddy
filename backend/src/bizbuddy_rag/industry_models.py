"""Pydantic models for industry knowledge skill query APIs."""

# 模块作用：定义行业知识库接口使用的请求体和响应体模型。
# 这些模型会被 FastAPI 用来解析请求、校验字段，并生成接口文档。

# 导入 Any，用于 debug、metadata、tags 这类结构灵活的字典字段。
from typing import Any
# 导入 UUID 类型，用于标注 skill、dataset、document、segment、log、feedback 等 ID。
from uuid import UUID

# BaseModel 是 Pydantic 模型基类；Field 用于设置字段校验规则和接口文档描述。
from pydantic import BaseModel, Field


# 模型作用：/industry-knowledge/retrieve 接口的请求体。
# 用于描述一次“只检索知识片段、不调用大模型”的请求。
class IndustryKnowledgeRetrieveRequest(BaseModel):
    """Request body for retrieving industry knowledge segments."""

    # 必填：行业知识技能 ID，后端用它找到对应的 skill 配置和 dataset_id。
    skill_id: UUID = Field(..., description="Industry knowledge skill ID")
    # 必填：用户查询文本；min_length=1 表示不能为空字符串。
    query: str = Field(..., min_length=1, description="User query")
    # 可选：希望返回的 chunk 数量；如果传入，必须在 1 到 20 之间。
    top_k: int | None = Field(default=None, ge=1, le=20, description="Top K chunks")


# 模型作用：检索或问答接口返回的一条证据引用。
# 每个对象对应数据库中命中的一个 chunk。
class IndustryKnowledgeReference(BaseModel):
    """Retrieved evidence chunk returned by skill query APIs."""

    # chunk ID；全文模式对应 public.datasets_segments.id（uuid 字符串），
    # 向量模式对应 gufei_vec.chunks.id（md5 text）。
    segment_id: str
    # 检索相关性分数；全文模式是 ts_rank，向量模式是 cosine 相似度（0~1）。
    score: float
    # chunk 在文档/文件中的分块序号。
    chunk_index: int
    # chunk 正文内容。
    content: str
    # chunk 所属文档 ID；向量库无此概念，可为空。
    document_id: UUID | None = None
    # chunk 所属数据集 ID；向量库无此概念，可为空。
    dataset_id: UUID | None = None
    # chunk 来源（向量库原始文件路径）；全文模式可为空。
    source: str | None = None
    # chunk 所属 subdir（向量库分区）；全文模式可为空。
    subdir: str | None = None
    # chunk 元数据，例如来源、标题、章节等；可为空。
    metadata: dict[str, Any] | None = None


# 模型作用：/industry-knowledge/retrieve 接口的响应体。
# 返回检索到的证据片段，以及用于排查问题的 debug 信息。
class IndustryKnowledgeRetrieveResponse(BaseModel):
    """Response body for retrieval-only requests."""

    # 检索命中的证据片段列表。
    items: list[IndustryKnowledgeReference]
    # 调试信息，例如 skill_id、dataset_id、top_k、retrieved_count 等。
    debug: dict[str, Any]


# 模型作用：/industry-knowledge/query 接口的请求体。
# 它继承 retrieve 请求，所以字段同样是 skill_id、query、top_k。
class IndustryKnowledgeQueryRequest(IndustryKnowledgeRetrieveRequest):
    """Request body for retrieve-and-answer requests."""

    # 继承父类字段，不新增额外字段。
    pass


# 模型作用：/industry-knowledge/query 接口的响应体。
# 返回问答日志 ID、最终答案、引用片段和 debug 信息。
class IndustryKnowledgeQueryResponse(BaseModel):
    """Response body for industry knowledge question answering."""

    # 本次问答日志 ID，提交反馈时用它关联到这次回答。
    query_log_id: UUID
    # 最终回答文本；可能是 LLM 回答，也可能是无上下文兜底回答。
    answer: str
    # 本次回答引用的证据片段列表。
    references: list[IndustryKnowledgeReference]
    # 调试信息，例如检索模式、top_k、命中数量、上下文长度、耗时等。
    debug: dict[str, Any]


# 模型作用：/industry-knowledge/feedback 接口的请求体。
# 用于提交用户对某次问答结果的评分、帮助性判断、评论和标签。
class IndustryKnowledgeFeedbackRequest(BaseModel):
    """Request body for feedback on a skill query answer."""

    # 必填：反馈对应的问答日志 ID。
    query_log_id: UUID
    # 可选：用户评分；如果传入，必须在 1 到 5 之间。
    rating: int | None = Field(default=None, ge=1, le=5)
    # 可选：用户是否认为回答有帮助。
    is_helpful: bool | None = None
    # 可选：用户文字评论。
    comment: str | None = None
    # 可选：结构化反馈标签。
    tags: dict[str, Any] | None = None


# 模型作用：/industry-knowledge/feedback 接口的响应体。
# 表示反馈保存成功，并返回新反馈记录 ID。
class IndustryKnowledgeFeedbackResponse(BaseModel):
    """Response body after feedback is stored."""

    # 新创建的反馈记录 ID。
    feedback_id: UUID
    # 是否保存成功；默认返回 True。
    saved: bool = True
