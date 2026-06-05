"""FastAPI 应用入口."""

from fastapi import FastAPI

from bizbuddy_rag.api.routes import lifespan, router


def create_app() -> FastAPI:
    """创建 FastAPI 应用."""
    app = FastAPI(
        title="BizBuddy RAG Service",
        description="基于 FastAPI + PostgreSQL(pgvector) 的 RAG 后台服务",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(router, prefix="/api/v1")
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("bizbuddy_rag.main:app", host="0.0.0.0", port=8000, reload=True)
