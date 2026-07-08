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


# gufei_vec 向量库（独立库，端口 5440）的只读连接。
# 该库由外部维护，本服务只做向量检索，不创建扩展、不写入，因此不挂 pgvector 初始化事件。
# 未配置 gufei_vec_url 时保持 None，向量检索路径会给出明确错误。
gufei_vec_engine = None
GufeiVecSessionLocal = None
if settings.gufei_vec_url:
    gufei_vec_engine = create_engine(
        settings.gufei_vec_url,
        pool_pre_ping=True,
        echo=False,
    )
    GufeiVecSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=gufei_vec_engine
    )


# 用户库（buildingai）连接：与 rswaste-platform 共用同一个 public.user 表。
# 未配置时保持 None，认证接口会给出明确错误。
auth_engine = None
AuthSessionLocal = None
if settings.auth_database_url:
    auth_engine = create_engine(
        settings.auth_database_url,
        pool_pre_ping=True,
        echo=False,
    )
    AuthSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=auth_engine
    )


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
