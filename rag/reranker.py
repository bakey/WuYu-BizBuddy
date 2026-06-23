from __future__ import annotations

import numpy as np
from typing import Sequence

from .retriever import RetrievalResult


class MMRReranker:
    """Maximal Marginal Relevance —— 多样性重排，无需额外模型。

    MMR 公式: argmax  λ·sim(q,d) - (1-λ)·max_{s∈S} sim(d,s)
    通过惩罚已选文档的相似度来避免结果重复。
    """

    def __init__(self, lambda_: float = 0.7, encode_fn=None):
        self.lambda_ = lambda_
        self.encode_fn = encode_fn

    def rerank(
        self,
        query_embedding: np.ndarray,
        results: Sequence[RetrievalResult],
        top_k: int = 5,
    ) -> list[RetrievalResult]:
        if len(results) <= top_k:
            return list(results)

        doc_embs = self._get_doc_embs(results)

        query_sim = doc_embs @ query_embedding
        sim_matrix = doc_embs @ doc_embs.T

        selected: list[int] = []
        remaining = set(range(len(results)))

        first = int(np.argmax(query_sim))
        selected.append(first)
        remaining.discard(first)

        while len(selected) < top_k and remaining:
            best_score = -1.0
            best_idx = -1
            for idx in remaining:
                relevance = query_sim[idx]
                redundancy = max(sim_matrix[idx, s] for s in selected)
                score = self.lambda_ * relevance - (1 - self.lambda_) * redundancy
                if score > best_score:
                    best_score = score
                    best_idx = idx
            if best_idx < 0:
                break
            selected.append(best_idx)
            remaining.discard(best_idx)

        return [results[i] for i in selected]

    @staticmethod
    def _get_doc_emb(r: RetrievalResult) -> np.ndarray:
        cached = getattr(r, "_embedding", None)
        if cached is not None:
            return cached
        raise RuntimeError("doc embeddings required")

    def _get_doc_embs(self, results: Sequence[RetrievalResult]) -> np.ndarray:
        cached = [getattr(r, "_embedding", None) for r in results]
        if all(c is not None for c in cached):
            return np.stack(cached)
        if self.encode_fn is None:
            raise RuntimeError("MMR needs embeddings: pass encode_fn or set result._embedding")
        texts = [r.text[:2000] for r in results]
        embs = self.encode_fn(texts)
        for r, e in zip(results, embs):
            r._embedding = e
        return embs


class CrossEncoderReranker:
    """Cross-encoder 精排（需要 bge-reranker 模型）。"""

    def __init__(self, model_path: str, device: str = "cpu", max_length: int = 512):
        from sentence_transformers import CrossEncoder
        self.model = CrossEncoder(
            model_path,
            device=device,
            max_length=max_length,
        )

    def rerank(
        self,
        query: str,
        results: Sequence[RetrievalResult],
        top_k: int = 5,
    ) -> list[RetrievalResult]:
        if len(results) <= top_k:
            return list(results)
        pairs = [(query, r.text[:2000]) for r in results]
        scores = self.model.predict(pairs)
        order = np.argsort(scores)[::-1][:top_k]
        return [results[i] for i in order]
