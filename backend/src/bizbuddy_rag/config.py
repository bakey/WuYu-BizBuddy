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

    rag_top_k: int = 5
    rag_similarity_threshold: float = 0.7

    industry_default_top_k: int = 5
    industry_max_top_k: int = 20
    industry_fulltext_config: str = "chinese_zh"
    industry_default_max_context_chars: int = 6000


settings = Settings()
