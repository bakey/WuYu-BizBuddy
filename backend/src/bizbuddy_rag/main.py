"""FastAPI 应用入口."""

from fastapi import Depends, FastAPI

from bizbuddy_rag.api.agent_routes import router as agent_router
from bizbuddy_rag.api.auth_routes import router as auth_router
from bizbuddy_rag.api.chat_routes import router as chat_router
from bizbuddy_rag.api.industry_knowledge_routes import (
    router as industry_knowledge_router,
)
from bizbuddy_rag.api.routes import lifespan, public_router, router
from bizbuddy_rag.auth.deps import get_current_active_user


def create_app() -> FastAPI:
    """创建 FastAPI 应用."""
    app = FastAPI(
        title="BizBuddy RAG Service",
        description="基于 FastAPI + PostgreSQL(pgvector) 的 RAG 后台服务",
        version="0.1.0",
        lifespan=lifespan,
        redirect_slashes=False,
    )

    # 认证接口自身不能挂鉴权（否则登录死循环）。
    app.include_router(auth_router, prefix="/api/v1")
    # 健康检查免鉴权，供容器 healthcheck 使用。
    app.include_router(public_router, prefix="/api/v1")

    # 所有业务接口强制登录。未登录 401；用户禁用 403。
    auth_dep = [Depends(get_current_active_user)]
    app.include_router(router, prefix="/api/v1", dependencies=auth_dep)
    app.include_router(chat_router, prefix="/api/v1", dependencies=auth_dep)
    app.include_router(agent_router, prefix="/api/v1", dependencies=auth_dep)
    app.include_router(
        industry_knowledge_router, prefix="/api/v1", dependencies=auth_dep
    )
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("bizbuddy_rag.main:app", host="0.0.0.0", port=8000, reload=True)
