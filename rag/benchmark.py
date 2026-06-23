"""综合测试：FastAPI 启动检查 + 聚类路由加速对比 + 系统评估"""
import json
import time
import sys

def check_imports():
    print("=== 1. 依赖检查 ===")
    for mod in ["fastapi", "uvicorn", "sklearn", "psycopg2", "sentence_transformers", "numpy"]:
        try:
            m = __import__(mod)
            print(f"  OK  {mod} {getattr(m, '__version__', '')}")
        except ImportError:
            print(f"  ERR {mod} not found")
    sys.stdout.flush()


def benchmark_cluster_routing():
    print("\n=== 2. 聚类路由加速对比 ===")
    from rag import RetrieverConfig, GufeiVecRetriever, SemanticClusterer

    cfg = RetrieverConfig()
    retriever = GufeiVecRetriever(cfg)
    cl = SemanticClusterer(cfg)
    cl.load("arxiv_markdown")
    print(f"  簇心加载: shape={cl.centroids.shape}")

    queries = [
        ("dioxin emission waste incineration", "arxiv_markdown"),
        ("lithium battery recycling cobalt recovery", "arxiv_markdown"),
        ("heavy metal adsorption biochar", "arxiv_markdown"),
    ]

    print(f"\n  {'Query':<50} {'probes=20':>10} {'probes=10':>10} {'probes=5':>10} {'probes=1':>10}")
    print(f"  {'-'*50} {'-'*10} {'-'*10} {'-'*10} {'-'*10}")

    for q_text, subdir in queries:
        times = {}
        for probes in [20, 10, 5, 1]:
            t0 = time.time()
            results = retriever.retrieve(q_text, k=5, scope=subdir, probes=probes)
            dt = time.time() - t0
            times[probes] = (round(dt, 2), results[0].cosine_sim if results else 0)
        
        row = f"  {q_text[:50]:<50}"
        for p in [20, 10, 5, 1]:
            row += f" {times[p][0]:>7.2f}s/sim{times[p][1]:.3f}"
        print(row)
    sys.stdout.flush()

    print("\n  聚类路由测试:")
    for q_text, subdir in queries:
        qvec = retriever.encode(q_text)
        route = cl.route(qvec, top_n=3)
        route_str = ", ".join(f"c{cid}({sim:.3f})" for cid, sim in route)
        print(f"    {q_text[:40]:<40} -> {route_str}")
    sys.stdout.flush()

    retriever.close()


def run_eval():
    print("\n=== 3. 系统评估 (10 queries) ===")
    from rag import RetrieverConfig, RAGPipeline
    from rag.eval_queries import INDUSTRIAL_EVAL_QUERIES

    cfg = RetrieverConfig()
    pipe = RAGPipeline(cfg, use_reranker=True)

    all_results = []
    for q in INDUSTRIAL_EVAL_QUERIES:
        result = pipe.search(
            query=q["query"],
            k=30,
            scope=q["scope"],
            final_k=5,
            probes=10,
        )
        top_sim = result.final_results[0].cosine_sim if result.final_results else 0
        avg_sim = (
            sum(r.cosine_sim for r in result.final_results) / len(result.final_results)
            if result.final_results else 0
        )
        all_results.append({
            "id": q["id"],
            "query": q["query"],
            "lang": q["lang"],
            "intent": q["intent"],
            "top1_sim": round(top_sim, 4),
            "avg_sim": round(avg_sim, 4),
            "total_s": result.timings.get("total_s", 0),
            "retrieval_s": result.timings.get("retrieval_s", 0),
        })
        print(f"  [{q['id']}] {q['lang']} sim={top_sim:.3f}/{avg_sim:.3f} time={result.timings.get('total_s', 0)}s  {q['query'][:40]}")
    sys.stdout.flush()

    pipe.close()

    avg_top1 = sum(r["top1_sim"] for r in all_results) / len(all_results)
    avg_time = sum(r["total_s"] for r in all_results) / len(all_results)
    print(f"\n  整体平均: top1_sim={avg_top1:.4f}  avg_time={avg_time:.2f}s")

    print("\n=== 4. JSON 汇总 ===")
    print(json.dumps({
        "evaluation": all_results,
        "summary": {
            "n_queries": len(all_results),
            "avg_top1_sim": round(avg_top1, 4),
            "avg_total_s": round(avg_time, 2),
        }
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    check_imports()
    benchmark_cluster_routing()
    run_eval()
