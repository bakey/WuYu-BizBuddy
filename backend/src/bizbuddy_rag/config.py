"""应用配置."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置模型."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    log_level: str = "info"

    database_url: str = "postgresql://postgres:postgres@localhost:5432/bizbuddy_rag"

    openai_api_key: str = ""
    openai_base_url: str | None = None
    openai_embedding_model: str = "text-embedding-3-small"
    openai_chat_model: str = "gpt-4o-mini"

    # 本地调试开关：开启后使用 mock embedding / mock llm，无需 OpenAI API Key
    mock_ai: bool = False

    rag_top_k: int = 5
    rag_similarity_threshold: float = 0.7

    industry_default_top_k: int = 5
    industry_max_top_k: int = 20
    industry_fulltext_config: str = "chinese_zh"
    industry_default_max_context_chars: int = 6000

    # 向量检索（gufei_vec）相关配置。
    # gufei_vec 向量库连接串；为空时表示未配置，向量检索会报错。
    # Linux 部署示例：postgresql://postgres:****@127.0.0.1:5440/gufei_vec
    gufei_vec_url: str = ""
    # 本地 bge-m3 模型路径（必须与入库时的模型一致，1024 维）。
    bge_m3_model_path: str = "/data/models/bge-m3_20250912_235519m"
    # bge-m3 运行设备，cpu 或 cuda。
    bge_m3_device: str = "cpu"
    # IVFFlat 默认 probes：5≈20s/85%，10≈47s/90%，20≈77s/95%（强烈建议配合 subdir 过滤）。
    industry_vector_probes: int = 5
    # 向量召回的 cosine 相似度阈值，低于该值的片段会被过滤；0 表示不过滤。
    industry_vector_score_threshold: float = 0.0
    # 召回片段的最小正文字符数：过滤掉"只有标题/极短碎片"的 chunk；0 表示不过滤。
    industry_vector_min_chunk_chars: int = 50
    # 同一来源文档最多保留的片段数：避免一篇文档的多个碎片占满 top_k；0 表示不限。
    industry_vector_max_per_source: int = 3
    # 内容近重去重：正文规范化前缀相同则视为重复，只保留一条；0 表示不做内容去重。
    # 用于消除"同一篇文章被爬到多个不同 URL"这类跨来源重复。
    industry_vector_dedupe_content_prefix: int = 80

    # 重排（rerank）相关配置：先向量多召回，再用 cross-encoder 重排取 top_k。
    # bge-reranker 模型路径；建议指向 Linux 本地路径（如 /data/models/bge-reranker-v2-m3）。
    bge_reranker_model_path: str = "BAAI/bge-reranker-v2-m3"
    # reranker 运行设备，cpu 或 cuda。
    bge_reranker_device: str = "cpu"
    # 是否默认启用重排；可被 skill 级配置覆盖。默认关闭，配好模型后再开。
    industry_rerank_enabled: bool = False
    # 重排前向量多召回的候选数量（over-fetch），最终再截断到 top_k。
    industry_rerank_over_fetch_k: int = 30


settings = Settings()
