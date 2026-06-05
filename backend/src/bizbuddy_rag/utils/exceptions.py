"""自定义异常."""


class RAGException(Exception):
    """RAG 服务基础异常."""

    pass


class EmbeddingError(RAGException):
    """嵌入服务异常."""

    pass


class LLMError(RAGException):
    """大模型服务异常."""

    pass


class DatabaseError(RAGException):
    """数据库异常."""

    pass
