"""演示脚本 —— 跑 3 个查询，展示检索 + MMR 重排效果。

用法 (在服务器上):
    cd /data/gufei_vec/rag
    /root/miniconda3/envs/gufei_vec/bin/python demo.py
"""
from __future__ import annotations

import json
import sys
import time

from rag import RetrieverConfig, RAGPipeline
from rag.eval_queries import INDUSTRIAL_EVAL_QUERIES


DEMO_QUERIES = INDUSTRIAL_EVAL_QUERIES[:3]


def run_demo():
    print("=" * 70)
    print("RAG Pipeline Demo  ——  检索 + MMR 重排")
    print("=" * 70)

    cfg = RetrieverConfig()
    pipe = RAGPipeline(cfg, use_reranker=True)

    print(f"\n[init] 模型: {cfg.model_path}")
    print(f"[init] DB:   {cfg.pg_dsn.split('@')[1]}")
    print()

    all_timings = []

    for q in DEMO_QUERIES:
        print(f"\n{'─' * 70}")
        print(f"Query [{q['id']}] ({q['lang']}): {q['query']}")
        print(f"Scope: {q['scope']}")
        print(f"{'─' * 70}")

        result = pipe.search(
            query=q["query"],
            k=30,
            scope=q["scope"],
            final_k=5,
            probes=20,
        )

        print(f"\n⏱  耗时: encode={result.timings.get('encode_s')}s  "
              f"retrieve={result.timings.get('retrieval_s')}s  "
              f"rerank={result.timings.get('rerank_s', 0)}s  "
              f"total={result.timings.get('total_s')}s")
        print(f"   重排器: {result.timings.get('reranker', 'none')}")

        print(f"\n📌 Top-5 结果 (重排后):")
        for i, r in enumerate(result.final_results, 1):
            print(f"\n  [{i}] sim={r.cosine_sim:.4f}  [{r.subdir}]")
            src_short = r.source.split("/")[-1][:60]
            print(f"      source: {src_short}")
            print(f"      chunk:  {r.chunk_idx}/{r.n_chunks}")
            preview = r.text[:200].replace("\n", " ")
            print(f"      text:   {preview}...")

        all_timings.append({
            "id": q["id"],
            "query": q["query"],
            **result.timings,
            "n_retrieved": len(result.retrieval_results),
            "n_final": len(result.final_results),
        })

    pipe.close()

    print(f"\n{'=' * 70}")
    print("汇总")
    print(f"{'=' * 70}")
    avg_total = sum(t["total_s"] for t in all_timings) / len(all_timings)
    avg_ret = sum(t["retrieval_s"] for t in all_timings) / len(all_timings)
    print(f"平均检索耗时: {avg_ret:.2f}s")
    print(f"平均总耗时:   {avg_total:.2f}s")
    print(f"\n详细: {json.dumps(all_timings, indent=2, ensure_ascii=False)}")


if __name__ == "__main__":
    run_demo()
