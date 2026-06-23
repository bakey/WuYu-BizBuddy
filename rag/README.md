# WuYu RAG Module

工业智能体的向量检索（RAG）模块。

## 快速开始

### 环境要求
- Python 3.10+
- PostgreSQL 16 + pgvector
- 依赖: `pip install -r rag/requirements.txt`

### 基础用法

```python
from rag import RAGPipeline

pipe = RAGPipeline()
result = pipe.search("固废焚烧二噁英控制", scope="industrial", final_k=5)

for r in result.final_results:
    print(f"[{r.cosine_sim:.3f}] {r.subdir} | {r.preview(100)}")

# 生成 LLM 上下文
context = pipe.format_context(result)
```

### 启动 HTTP 服务

```bash
PYTHONPATH=/data/gufei_vec /root/miniconda3/envs/gufei_vec/bin/python \
    -m uvicorn rag.api_service:app --host 0.0.0.0 --port 8010
```

调用:
```bash
curl -X POST http://localhost:8010/search \
  -H "Content-Type: application/json" \
  -d '{"query": "锂离子电池回收", "scope": "industrial", "top_k": 5}'
```

## 数据源

| scope | 包含数据 | chunk 数 |
|---|---|---|
| `industrial` | arxiv + MDS + chemrxiv | 16.3M |
| `policy` | html_md + pt_md | 52.5M |
| `all` | 全部 | 68.8M |

## 参数调优

关键参数 `probes`（ivfflat 索引扫描簇数）：

| probes | 延迟 | 质量 | 建议 |
|---|---|---|---|
| 20 | 3-12s | 最高 | 仅用于评估 |
| **5** | **0.2-0.4s** | **几乎无损** | **生产推荐** |
| 1 | 0.1-0.2s | 有下降 | 极速场景 |

## 文件说明

| 文件 | 说明 |
|---|---|
| `config.py` | 配置（数据库、模型、参数） |
| `retriever.py` | 向量检索器（pgvector ANN） |
| `reranker.py` | MMR 重排 + Cross-encoder 接口 |
| `clusterer.py` | KMeans 语义聚类（检索路由 + 数据治理） |
| `pipeline.py` | 端到端管线 |
| `api_service.py` | FastAPI HTTP 服务 |
| `eval_queries.py` | 评估查询集（10 条工业 query） |
| `benchmark.py` | 性能基准测试 |
| `demo.py` | 检索演示 |
| `demo_cluster.py` | 聚类演示 |

详见 [docs/RAG_Design.md](../docs/RAG_Design.md)。
