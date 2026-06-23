"""聚类演示 —— 对 arxiv_markdown 子集做 KMeans 聚类，展示簇心和路由。

用法:
    cd /data/gufei_vec
    PYTHONPATH=/data/gufei_vec /root/miniconda3/envs/gufei_vec/bin/python rag/demo_cluster.py
"""
from __future__ import annotations

import json
import time

import numpy as np

from rag import RetrieverConfig, SemanticClusterer, GufeiVecRetriever


def run_cluster_demo():
    print("=" * 70)
    print("聚类 Demo  ——  MiniBatchKMeans on arxiv_markdown")
    print("=" * 70)

    cfg = RetrieverConfig()
    cl = SemanticClusterer(cfg)

    print("\n[1/3] 采样 + 聚类 (n_clusters=30, sample=30000)...")
    stats = cl.fit(
        n_clusters=30,
        sample_size=30000,
        subdir="arxiv_markdown",
        save=True,
    )
    print(f"  采样耗时: {stats['fetch_time_s']}s")
    print(f"  聚类耗时: {stats['fit_time_s']}s")
    print(f"  簇数: {stats['n_clusters']}")
    print(f"  样本量: {stats['sample_size']}")

    dist = stats["cluster_distribution"]
    print(f"\n  簇大小分布 (top-10):")
    for cid, cnt in sorted(dist.items(), key=lambda x: -x[1])[:10]:
        bar = "#" * min(cnt // 50, 40)
        print(f"    cluster {cid:2d}: {cnt:5d}  {bar}")

    print(f"\n[2/3] 簇心路由测试...")
    retriever = GufeiVecRetriever(cfg)

    test_queries = [
        "dioxin emission from waste incineration",
        "lithium battery cathode material recycling",
        "heavy metal adsorption wastewater treatment",
    ]

    for q in test_queries:
        qvec = retriever.encode(q)
        route = cl.route(qvec, top_n=3)
        print(f"\n  query: {q}")
        for cid, sim in route:
            print(f"    -> cluster {cid}  sim={sim:.4f}")

    print(f"\n[3/3] 路由加速效果模拟...")
    print("  (展示: 用簇心路由 + 限定 probes 检索 vs 全量检索)")
    q = "dioxin emission from waste incineration"
    qvec = retriever.encode(q)

    t0 = time.time()
    full = retriever.retrieve(q, k=5, scope="arxiv_markdown", probes=20)
    t_full = time.time() - t0
    print(f"\n  全量检索 (probes=20): {t_full:.2f}s, top1 sim={full[0].cosine_sim:.4f}")

    t0 = time.time()
    fast = retriever.retrieve(q, k=5, scope="arxiv_markdown", probes=5)
    t_fast = time.time() - t0
    print(f"  低 probes (probes=5):  {t_fast:.2f}s, top1 sim={fast[0].cosine_sim:.4f}")

    t0 = time.time()
    faster = retriever.retrieve(q, k=5, scope="arxiv_markdown", probes=1)
    t_faster = time.time() - t0
    print(f"  极低probes (probes=1): {t_faster:.2f}s, top1 sim={faster[0].cosine_sim:.4f}")

    speedup = t_full / max(t_faster, 0.001)
    print(f"\n  理论加速比: {speedup:.1f}x (probes 20->1)")
    print("  注: 聚类路由可在此基础上进一步缩小搜索范围")

    retriever.close()


if __name__ == "__main__":
    run_cluster_demo()
