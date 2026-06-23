"""全量聚类 —— 对工业类数据做聚类并保存簇心"""
import json
import time

from rag import RetrieverConfig, SemanticClusterer

cfg = RetrieverConfig()
results = {}

for sub in ["arxiv_markdown", "MDS_md", "chemrxiv_md"]:
    print(f"\n--- clustering {sub} (n=50, sample=40000) ---", flush=True)
    t0 = time.time()
    cl = SemanticClusterer(cfg)
    stats = cl.fit(n_clusters=50, sample_size=40000, subdir=sub, save=True)
    elapsed = time.time() - t0
    results[sub] = {
        "n_clusters": stats["n_clusters"],
        "sample_size": stats["sample_size"],
        "fetch_time_s": stats["fetch_time_s"],
        "fit_time_s": stats["fit_time_s"],
        "total_elapsed_s": round(elapsed, 2),
    }
    print(f"  fetch={stats['fetch_time_s']}s  fit={stats['fit_time_s']}s  total={elapsed:.1f}s", flush=True)

    dist = stats["cluster_distribution"]
    top5 = sorted(dist.items(), key=lambda x: -x[1])[:5]
    print(f"  top-5 clusters: {top5}", flush=True)

print("\n=== SUMMARY ===")
print(json.dumps(results, indent=2, ensure_ascii=False))
