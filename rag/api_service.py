"""RAG 检索服务 —— FastAPI 封装，供 wuyu-backend 通过 HTTP 调用。

启动:
    cd /data/gufei_vec
    PYTHONPATH=/data/gufei_vec /root/miniconda3/envs/gufei_vec/bin/python \
        -m uvicorn rag.api_service:app --host 0.0.0.0 --port 8010

调用示例:
    curl -X POST http://localhost:8010/search \
      -H "Content-Type: application/json" \
      -d '{"query": "固废焚烧二噁英控制", "scope": "industrial", "top_k": 5}'
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Sequence

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .config import RetrieverConfig
from .pipeline import RAGPipeline


pipeline: RAGPipeline | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pipeline
    cfg = RetrieverConfig()
    pipeline = RAGPipeline(cfg, use_reranker=True)
    yield
    if pipeline:
        pipeline.close()


app = FastAPI(
    title="WuYu RAG Service",
    description="向量检索 + MMR 重排服务，供工业智能体后端调用",
    version="0.1.0",
    lifespan=lifespan,
)


class SearchRequest(BaseModel):
    query: str
    scope: str | Sequence[str] | None = "industrial"
    top_k: int = Field(default=5, ge=1, le=50)
    candidate_k: int = Field(default=30, ge=5, le=100)
    probes: int = Field(default=10, ge=1, le=100)
    return_context: bool = Field(default=True, description="返回格式化的 LLM 上下文")
    context_max_chars: int = Field(default=4000, ge=500, le=20000)


class SearchResult(BaseModel):
    chunk_id: str
    subdir: str
    source: str
    chunk_idx: int
    n_chunks: int
    cosine_sim: float
    preview: str


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    context: str | None = None
    timings: dict
    total_results: int


@app.post("/search", response_model=SearchResponse)
def search(req: SearchRequest):
    t0 = time.time()
    result = pipeline.search(
        query=req.query,
        k=req.candidate_k,
        scope=req.scope,
        final_k=req.top_k,
        probes=req.probes,
    )

    results = [
        SearchResult(
            chunk_id=r.chunk_id,
            subdir=r.subdir,
            source=r.source,
            chunk_idx=r.chunk_idx,
            n_chunks=r.n_chunks,
            cosine_sim=r.cosine_sim,
            preview=r.preview(500),
        )
        for r in result.final_results
    ]

    context = None
    if req.return_context:
        context = pipeline.format_context(result, max_chars=req.context_max_chars)

    return SearchResponse(
        query=req.query,
        results=results,
        context=context,
        timings=result.timings,
        total_results=len(results),
    )


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": pipeline is not None}


@app.get("/subdirs")
def list_subdirs():
    cfg = RetrieverConfig()
    return {
        "subdirs": list(cfg.valid_subdirs),
        "aliases": cfg.subdir_aliases,
    }
