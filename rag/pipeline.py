from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Sequence

from .config import RetrieverConfig
from .retriever import GufeiVecRetriever, RetrievalResult
from .reranker import MMRReranker, CrossEncoderReranker
from .clusterer import SemanticClusterer


@dataclass
class PipelineResult:
    query: str
    retrieval_results: list[RetrievalResult] = field(default_factory=list)
    reranked_results: list[RetrievalResult] = field(default_factory=list)
    cluster_route: list[tuple[int, float]] = field(default_factory=list)
    timings: dict = field(default_factory=dict)

    @property
    def final_results(self) -> list[RetrievalResult]:
        return self.reranked_results or self.retrieval_results


class RAGPipeline:
    """端到端 RAG 管线：检索 → （聚类路由）→ 重排。

    用法:
        pipe = RAGPipeline()
        result = pipe.search("固废焚烧二噁英控制", scope="industrial")
        for r in result.final_results:
            print(r.cosine_sim, r.preview())
    """

    def __init__(
        self,
        config: RetrieverConfig | None = None,
        use_reranker: bool = True,
        use_cluster_routing: bool = False,
    ):
        self.cfg = config or RetrieverConfig()
        self.retriever = GufeiVecRetriever(self.cfg)
        self.clusterer = SemanticClusterer(self.cfg)

        self.mmr: MMRReranker | None = None
        self.cross_encoder: CrossEncoderReranker | None = None

        if use_reranker:
            self.mmr = MMRReranker(
                lambda_=self.cfg.mmr_lambda,
                encode_fn=self.retriever._model.encode,
            )
            if self.cfg.rerank_model_path:
                try:
                    self.cross_encoder = CrossEncoderReranker(
                        self.cfg.rerank_model_path,
                        device=self.cfg.device,
                    )
                except Exception as e:
                    print(f"[pipeline] cross-encoder load failed, MMR fallback: {e}")

        self._cluster_loaded = False
        if use_cluster_routing:
            self._cluster_loaded = self.clusterer.load()

    def search(
        self,
        query: str,
        k: int = 50,
        scope: str | Sequence[str] | None = None,
        final_k: int | None = None,
        probes: int | None = None,
    ) -> PipelineResult:
        final_k = final_k or self.cfg.rerank_top_k
        result = PipelineResult(query=query)
        t_start = time.time()

        qvec = self.retriever.encode(query)
        t_enc = time.time() - t_start

        if self._cluster_loaded:
            t_c = time.time()
            result.cluster_route = self.clusterer.route(qvec)
            result.timings["cluster_route_s"] = round(time.time() - t_c, 3)

        t_r = time.time()
        result.retrieval_results = self.retriever.retrieve(
            query, k=k, scope=scope, probes=probes,
            return_embeddings=bool(self.mmr),
        )
        result.timings["retrieval_s"] = round(time.time() - t_r, 3)
        result.timings["encode_s"] = round(t_enc, 3)

        if self.cross_encoder:
            t_rr = time.time()
            result.reranked_results = self.cross_encoder.rerank(
                query, result.retrieval_results, top_k=final_k,
            )
            result.timings["rerank_s"] = round(time.time() - t_rr, 3)
            result.timings["reranker"] = "cross-encoder"
        elif self.mmr and len(result.retrieval_results) > final_k:
            t_rr = time.time()
            result.reranked_results = self.mmr.rerank(
                qvec, result.retrieval_results, top_k=final_k,
            )
            result.timings["rerank_s"] = round(time.time() - t_rr, 3)
            result.timings["reranker"] = "MMR"

        result.timings["total_s"] = round(time.time() - t_start, 3)
        return result

    def format_context(self, result: PipelineResult, max_chars: int = 4000) -> str:
        """把检索结果格式化为 LLM 可用的上下文字符串。"""
        results = result.final_results
        parts: list[str] = []
        total = 0
        for i, r in enumerate(results, 1):
            snippet = r.text[:800]
            header = f"[{i}] (sim={r.cosine_sim:.3f}, {r.subdir}) {r.source}\n"
            block = header + snippet + "\n"
            if total + len(block) > max_chars:
                break
            parts.append(block)
            total += len(block)
        return "\n---\n".join(parts)

    def close(self):
        self.retriever.close()
