# RAG 算法设计文档

> 作者：徐简  
> 更新：2026-06-22  
> 状态：Phase 1 已实现，Phase 2 进行中

---

## 1. 概述

本模块为 WuYu 工业智能体提供基于向量检索的 RAG（Retrieval-Augmented Generation）能力。目标是让智能体在回答用户问题前，先从海量工业文献库中检索相关知识，再结合检索结果生成回答。

### 1.1 设计目标

| 目标 | 指标 |
|---|---|
| 检索相关性 | top-5 结果与查询语义高度匹配 |
| 检索延迟 | P95 < 2s（聚类路由优化后） |
| 可扩展性 | 支持新增数据源、新增 embedding 模型 |
| 可接入性 | 提供 HTTP API，后端零侵入调用 |

### 1.2 数据规模

| 数据源 | chunk 数 | 内容 |
|---|---:|---|
| html_md | 26,301,183 | 法律政策网页转 Markdown |
| pt_md | 26,168,009 | 固废技术资料 |
| arxiv_markdown | 11,446,457 | arXiv 论文 |
| MDS_md | 3,558,872 | 材料科学数据 |
| chemrxiv_md | 1,329,481 | ChemRxiv 化学论文 |
| **合计** | **68,804,002** | |

---

## 2. 系统架构

```
用户提问
   │
   ▼
┌──────────────┐
│  Query 编码   │  BGE-M3 (1024d)
└──────┬───────┘
       │
       ▼
┌──────────────┐     可选（聚类路由开启时）
│  簇心路由     │────→ 选择 top-N 个簇，缩小搜索范围
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  向量检索     │  pgvector + ivfflat (cosine)
│  (recall)    │  召回 candidate_k 条 (默认 30)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  重排         │  MMR (多样性) / Cross-encoder (精度)
│  (rerank)    │  精排到 top_k 条 (默认 5)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  上下文组装   │  格式化为 LLM prompt 片段
└──────┬───────┘
       │
       ▼
   传入 LLM 生成回答
```

---

## 3. 核心模块

### 3.1 向量检索器（retriever.py）

**职责**：将用户查询编码为向量，在 pgvector 中做 ANN 检索。

**Embedding 模型**：BGE-M3（锁定，不替换）
- 维度：1024
- 多语言：中英文
- 归一化：是（使用 cosine 相似度）
- 模型路径：`/data/models/bge-m3_20250912_235519m`

**向量数据库**：
- 引擎：PostgreSQL 16 + pgvector
- 容器：`pg-gufei-vec`（端口 5440）
- 索引：ivfflat, lists=2048, halfvec(1024), cosine_ops
- 索引大小：175 GB

**检索 SQL**：
```sql
SET ivfflat.probes = 5;
SELECT id, subdir, source, chunk_idx, n_chunks,
       1 - (embedding::halfvec(1024) <=> $1::halfvec(1024)) AS cosine_sim,
       txt
FROM chunks
WHERE subdir = ANY($2)            -- 可选：按数据源过滤
ORDER BY (embedding::halfvec(1024)) <=> $1::halfvec(1024)
LIMIT $3;
```

**数据源过滤（scope）**：
| scope | 包含的 subdir | 用途 |
|---|---|---|
| `industrial` | arxiv_markdown, MDS_md, chemrxiv_md | 工业技术文献 |
| `policy` | html_md, pt_md | 法律政策 |
| `all` | 全部 | 全量搜索 |
| 自定义 | 任意组合 | 按需指定 |

### 3.2 重排器（reranker.py）

**职责**：从召回的 candidate_k 条结果中，精选 top_k 条。

**方案 A：MMR（已实现）**
- 公式：`score = λ·sim(q,d) - (1-λ)·max_{s∈selected} sim(d,s)`
- 参数：λ=0.7
- 优势：无需额外模型，直接复用已有 embedding
- 作用：多样性去重，避免返回同一篇文档的多个相似 chunk

**方案 B：Cross-encoder（接口已预留）**
- 模型：bge-reranker-v2-m3（待部署）
- 作用：真正的语义精排，精度显著优于 MMR
- 使用：在 config 中设置 `rerank_model_path` 即可自动切换

### 3.3 聚类模块（clusterer.py）—— 核心

**职责**：对海量 chunk 做语义聚类，用于检索加速和数据治理。

**算法**：MiniBatchKMeans
- 选择理由：相比标准 KMeans，支持增量更新，适合流式数据；相比 HDBSCAN，聚类速度可控，产出簇心可用于路由
- 参数：n_clusters=50（每个 subdir），batch_size=4096

**双重用途**：

1. **检索加速（query routing）**
   - 离线：对每个 subdir 采样 → KMeans → 保存簇心
   - 在线：query 向量 → 与簇心计算相似度 → 选 top-3 簇 → 只在对应簇内搜索
   - 预期效果：搜索范围缩小 10-20 倍，延迟从 7-20s 降到 1-2s

2. **数据治理（cluster labeling）**
   - 每个簇的簇心代表一个语义主题
   - 可用于：自动分类新数据、数据质量异常检测、面向用户的数据浏览

**聚类路由实现路径（规划）**：
```
Phase A (已完成): 采样聚类 → 保存簇心文件
Phase B (规划):   给 chunks 表加 cluster_id 列 → 批量赋值
Phase C (规划):   检索时 WHERE cluster_id IN (路由结果) → 缩小扫描范围
```

### 3.4 端到端管线（pipeline.py）

串联以上模块，提供统一接口：
```python
pipe = RAGPipeline()
result = pipe.search("固废焚烧二噁英控制", scope="industrial")
# result.final_results → top-5 结果
# result.timings → 各环节耗时
# pipe.format_context(result) → LLM 可用的上下文字符串
```

### 3.5 HTTP 服务（api_service.py）

FastAPI 封装，供后端通过 HTTP 调用：
```
POST /search     → 检索 + 重排
GET  /health     → 健康检查
GET  /subdirs    → 数据源列表
```

---

## 4. Chunking 策略

当前策略（前序团队设定，沿用）：
```
RecursiveCharacterTextSplitter
  chunk_size = 800
  chunk_overlap = 100
  separators = ["\n\n", "\n", "。", "！", "？", ". ", " ", ""]
```

**优化方向（后续）**：
- 学术论文：按章节（Abstract/Introduction/Methods/Results）分块
- 政策法规：按条款分块
- 表格数据：保留完整表格，不切断

---

## 5. 性能基准

### 5.1 probes 参数调优（关键发现）

在 arxiv_markdown（1145 万 chunks）上的实测对比：

| Query | probes=20 | probes=10 | probes=5 | probes=1 |
|---|---|---|---|---|
| dioxin emission | 2.87s / sim=0.654 | 0.29s / sim=0.654 | **0.44s / sim=0.635** | 0.21s / sim=0.549 |
| lithium battery | 9.79s / sim=0.732 | 3.98s / sim=0.732 | **0.21s / sim=0.732** | 0.13s / sim=0.726 |
| heavy metal | 12.28s / sim=0.779 | 7.37s / sim=0.779 | **0.23s / sim=0.779** | 0.11s / sim=0.740 |

**结论：probes=5 是最佳参数**。相比 probes=20 延迟降低 30-50 倍，相似度几乎无损失。probes=1 虽然更快但质量下降明显。

→ 已将默认 probes 从 20 改为 5。

### 5.2 系统评估（10 条工业 query，probes=10）

| 指标 | 中文 query | 英文 query | 整体 |
|---|---|---|---|
| 平均 top1 相似度 | 0.495 | 0.679 | 0.586 |
| 平均延迟 | 6.9s | 2.3s | 4.65s |

**发现**：
- 英文检索效果优于中文（arxiv 论文以英文为主，符合预期）
- 中文 query 延迟更高（可能因为中文 BGE-M3 编码后的向量分布更分散）
- 相似度在 0.4-0.75 区间，对于 cosine 相似度属于"相关"到"高度相关"

### 5.3 优化目标

| 优化手段 | 预期延迟 | 状态 |
|---|---|---|
| probes 20→5 | **0.2-0.4s** | ✅ 已验证，已应用 |
| + 聚类路由 | ~0.1-0.2s | 簇心已生成，待接入 |
| + HNSW 索引 | ~0.05s | 待评估（175GB 索引重建成本高） |

---

## 6. 模块文件

```
rag/
├── __init__.py          # 包入口
├── config.py            # 配置（DSN、模型路径、参数）
├── retriever.py         # 向量检索器
├── reranker.py          # MMR + Cross-encoder
├── clusterer.py         # KMeans 聚类
├── pipeline.py          # 端到端管线
├── api_service.py       # FastAPI 服务
├── eval_queries.py      # 评估查询集
├── demo.py              # 检索演示
├── demo_cluster.py      # 聚类演示
├── run_full_cluster.py  # 全量聚类脚本
├── benchmark.py         # 性能基准测试
└── requirements.txt     # 依赖
```

---

## 7. 部署信息

| 项 | 值 |
|---|---|
| Python 环境 | `/root/miniconda3/envs/gufei_vec/` (Python 3.12) |
| 代码路径 | `/data/gufei_vec/rag/` |
| 模型路径 | `/data/models/bge-m3_20250912_235519m` |
| 向量库 | `pg-gufei-vec` 容器, 端口 5440 |
| 簇心文件 | `/data/gufei_vec/centroids_*.npy` |

---

## 8. 后续规划

| 优先级 | 任务 | 预计 |
|---|---|---|
| P0 | 聚类路由落地（加 cluster_id 列 + 检索过滤） | 本周 |
| P0 | 接入 wuyu-backend（HTTP 调用 RAG 服务） | 本周 |
| P1 | 部署 bge-reranker 精排模型 | 下周 |
| P1 | 混合检索（向量 ANN + BM25 全文） | 下周 |
| P2 | 自适应 chunking（按文档类型） | 后续 |
| P2 | 检索质量评估系统（Recall@K + 人工标注） | 后续 |
