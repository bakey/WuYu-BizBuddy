"""数据库连接和初始化."""

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from bizbuddy_rag.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=settings.app_env == "development",
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _ensure_pgvector_extension(dbapi_conn, _connection_record):
    """确保 pgvector 扩展已启用."""
    with dbapi_conn.cursor() as cursor:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        dbapi_conn.commit()


event.listens_for(engine, "connect")(_ensure_pgvector_extension)


def init_db() -> None:
    """初始化数据库表结构."""
    from bizbuddy_rag.db.models import Base

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
    Base.metadata.create_all(bind=engine)
