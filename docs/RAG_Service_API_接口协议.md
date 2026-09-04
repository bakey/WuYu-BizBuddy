**文档 / RAG Service
接口协议与实现约定**

API Specification v1.0

适用于：service 进程在同 pod 内通过 localhost 调用 RAG Service

| **项目** | **内容** |
| --- | --- |
| 文档版本 | v1.0 |
| 协议状态 | Draft / 可进入联调 |
| 通信方式 | HTTP/1.1 JSON + multipart/form-data |
| 监听范围 | 仅同 pod localhost：127.0.0.1 / ::1 |
| 持久化 | PostgreSQL（元数据 + 向量，pgvector） |
| 核心能力 | 文档解析、切片、BGE Embedding、rerank、检索、索引管理 |

# 1. 文档目的与范围

本协议定义 service 进程与 RAG Service（同 pod 部署）之间的接口、数据模型、状态机、错误码、索引生命周期、部署约束和验收标准。目标是让 RAG Service 可以独立开发、独立启动，并由 service 统一通过同 pod 内 localhost HTTP API 消费；多用户鉴权与用户体系上移到 service 层，RAG Service 不感知用户账号。

本次裁剪后的边界：多用户鉴权与远程业务逻辑上移到 service 层，不进入 RAG Service；数据存储统一使用 PostgreSQL（元数据 + 向量，向量用 pgvector）；文档解析覆盖 PDF、Word、Excel 和常见图片；向量化使用 BGE Embedding；检索结果进入 rerank；同时提供上传、状态、查询、删除、重建和统计等索引管理接口。

# 2. 术语与角色

| **术语** | **定义** |
| --- | --- |
| RAG Service | 与 service 同 pod 部署的 Python RAG 进程/容器，负责文档/RAG 能力。 |
| Client | 调用 RAG Service API 的进程，即同 pod 内的 service 进程。 |
| Document | 用户上传并纳入知识库管理的原始文件。 |
| Chunk | 文档切分后的最小检索单元，包含正文、来源页码/Sheet 等定位信息。 |
| Embedding | 由 BGE 模型产生的向量表示。 |
| Rerank | 对初步向量召回结果进行二次相关性排序。 |
| Job | 上传解析、索引重建等异步任务。 |
| Citation | 可回溯到原始文档、页码/工作表/块位置的引用信息。 |

# 3. 总体架构与职责边界

```
K8s Pod（私有云）
  ├─ service 容器
  │     ├─ 接收客户端请求（Backend / Electron / Frontend）
  │     ├─ 认证 / 业务路由 / 知识库路由
  │     │     │ localhost（同 pod）
  │     │     ▼
  │     └─ 调用 RAG Service
  ├─ RAG Service 容器
  │     ├─ API Layer
  │     ├─ Document Parser (PDF / Word / Excel / Image)
  │     ├─ Chunker
  │     ├─ BGE Embedding
  │     ├─ Reranker
  │     └─ 访问 PostgreSQL
  └─ PostgreSQL 容器
        ├─ Metadata Store
        └─ Vector Store (pgvector)
```

- RAG Service MUST 只监听同 pod 内 localhost（127.0.0.1 / ::1），不暴露到局域网或公网。

- RAG Service MUST 自主管理 PostgreSQL 的初始化、schema 版本迁移与连接健康检测。

- Client（service）SHOULD 将 RAG Service 视为独立服务，不直接读写其 PostgreSQL 数据库。

- 上传/重建属于异步任务；查询/状态/健康检查属于同步请求。

- RAG Service 不负责最终大模型回答；它负责返回高质量上下文与可核验引用。若后续需要，也可在 /query 结果上层接入 LLM。

# 4. 通信与通用协议约定

| **项** | **约定** |
| --- | --- |
| Base URL | http://127.0.0.1:{port}/api/v1 |
| 编码 | UTF-8 |
| 数据格式 | 除文件上传外均为 application/json |
| 上传格式 | multipart/form-data |
| 时间 | ISO 8601，UTC，例如 2026-08-28T12:00:00Z |
| ID | UUID v4 字符串 |
| 布尔值 | true / false |
| 分页 | page、page_size，默认 1 / 20，page_size 最大 100 |
| 请求追踪 | Client SHOULD 发送 X-Request-ID；RAG Service MUST 在响应头回传或生成一个新的。 |
| 协议版本 | URL 路径版本 /api/v1；破坏性变更升级为 /api/v2。 |

HTTP 状态码遵循语义化使用：2xx 表示成功，4xx 表示调用方参数或资源状态问题，5xx 表示 RAG Service 内部错误。业务错误细节统一放在 error 对象中。

```
{
  "ok": false,
  "error": {
    "code": "FAILED_PRECONDITION",
    "message": "Document is still indexing",
    "details": {"document_id": "...", "status": "EMBEDDING"},
    "request_id": "req-..."
  }
}
```

# 5. 安全与进程边界

- MUST 绑定 127.0.0.1，禁止 0.0.0.0。IPv6 可选绑定 ::1。

- MUST 拒绝非 loopback Host/来源的请求；CORS 默认关闭，仅在明确需要浏览器直连时配置白名单。

- 由 service 进程统一代理调用；桌面端 / Electron / Frontend 不直连 RAG Service。

- 可选：service 启动 RAG Service 时生成一次性随机 X-RAG-Service-Token，RAG Service 对所有非 health 接口校验该 Header。此机制无需 RAG Service 内置用户账号体系（认证在 service 层）。

- 文件名必须进行路径净化，禁止 ../、绝对路径、符号链接穿越和任意写盘。

- 解析器应设置超时、最大页数/Sheet 数/像素数等资源限制，避免恶意或异常文件拖垮进程。

# 6. 文档与任务状态机

```
RECEIVED
   ↓
PARSING → CHUNKING → EMBEDDING → INDEXING → READY
   └────────────── any stage error ──────────────→ FAILED

READY / FAILED
   └─ DELETE requested → DELETING → DELETED

READY
   └─ REINDEX requested → PARSING/CHUNKING/... → READY | FAILED
```

| **状态** | **含义** | **是否可检索** |
| --- | --- | --- |
| RECEIVED | 文件已保存，任务已创建 | 否 |
| PARSING | 提取文本、表格、图片文字/结构 | 否 |
| CHUNKING | 切片并生成定位元数据 | 否 |
| EMBEDDING | 计算 BGE 向量 | 否 |
| INDEXING | 写入 PostgreSQL 向量与索引元数据 | 否 |
| READY | 已完成并可参与查询 | 是 |
| FAILED | 处理失败，可查看错误并重试 | 否 |
| DELETING | 正在删除索引/元数据/文件 | 否 |
| DELETED | 已删除；正常列表默认不返回 | 否 |

# 7. 核心数据模型

## 7.1 Document

```
{
  "id": "9e2c...",
  "name": "设计说明.docx",
  "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "size_bytes": 183244,
  "sha256": "...",
  "status": "READY",
  "created_at": "2026-08-28T12:00:00Z",
  "updated_at": "2026-08-28T12:00:08Z",
  "chunk_count": 146,
  "vector_count": 146,
  "uploader": "u_...",
  "metadata": {
    "source": "user_upload",
    "tags": ["项目A", "需求"]
  },
  "last_error": null
}
```

## 7.2 Chunk / Citation

```
{
  "chunk_id": "chk_...",
  "document_id": "9e2c...",
  "text": "……命中的正文……",
  "score": 0.8421,
  "rerank_score": 0.7312,
  "citation": {
    "document_name": "设计说明.docx",
    "page": 12,
    "sheet": null,
    "section": "3.2 索引流程",
    "cell_range": null,
    "chunk_index": 37
  }
}
```

## 7.3 Job

```
{
  "id": "job_...",
  "type": "DOCUMENT_INGEST",
  "status": "RUNNING",
  "progress": 62,
  "stage": "EMBEDDING",
  "created_at": "...",
  "started_at": "...",
  "finished_at": null,
  "result": {"document_id": "9e2c..."},
  "error": null
}
```

# 8. API 接口定义

## 8.1 健康检查与版本

**GET /health**

进程存活检查。应尽量轻量，不触发模型加载。

**响应示例**

```
HTTP/1.1 200 OK
{
  "ok": true,
  "data": {"status": "alive", "uptime_sec": 3812}
}
```

**GET /ready**

就绪检查。用于判断数据库、Embedding/Rerank 组件是否可接受业务请求。

**响应示例**

```
{
  "ok": true,
  "data": {
    "ready": true,
    "database": "ok",
    "embedding": "loaded",
    "reranker": "loaded"
  }
}
```

**GET /version**

返回 RAG Service、API 与数据库 schema 版本。具体模型名称不在此返回（模型会随升级变动），可通过 /capabilities 或配置查看当前生效模型。

**响应示例**

```
{
  "ok": true,
  "data": {
    "rag_service_version": "1.0.0",
    "api_version": "v1",
    "schema_version": 3
  }
}
```

## 8.2 文档上传与管理

**POST /documents**

上传单个文档并创建异步入库任务。

**参数**

| **名称** | **位置/类型** | **必填** | **说明** |
| --- | --- | --- | --- |
| file | multipart file | 是 | PDF / DOCX / XLSX / XLS / PNG / JPG / JPEG 等允许类型 |
| metadata | JSON string | 否 | 业务元数据，例如 tags、source、project_id |
| deduplicate | boolean | 否 | 默认 true；按 sha256 去重 |

**请求示例**

```
Content-Type: multipart/form-data

file=@设计说明.docx
metadata={"tags":["项目A"],"source":"user_upload"}
deduplicate=true
```

**响应示例**

```
HTTP/1.1 202 Accepted
{
  "ok": true,
  "data": {
    "document_id": "9e2c...",
    "job_id": "job_31d...",
    "status": "RECEIVED",
    "deduplicated": false
  }
}
```

- 若 sha256 已存在且 deduplicate=true，建议返回 200，并指向既有 document_id，而不是重复入库。

- 上传成功仅代表文件接收成功，不代表已可检索；Client 必须根据 job 或 document status 判断 READY。

**GET /documents**

分页获取文档列表。

**参数**

| **名称** | **位置/类型** | **必填** | **说明** |
| --- | --- | --- | --- |
| page | query/int | 否 | 默认 1 |
| page_size | query/int | 否 | 默认 20，最大 100 |
| status | query/string | 否 | 按状态筛选 |
| q | query/string | 否 | 按文件名模糊搜索 |
| tag | query/string | 否 | 按 tag 筛选 |

**响应示例**

```
{
  "ok": true,
  "data": {
    "items": [{"id":"...","name":"设计说明.docx","status":"READY","chunk_count":146}],
    "page": 1,
    "page_size": 20,
    "total": 37
  }
}
```

**GET /documents/{document_id}**

获取单个文档详情、当前状态和最近失败原因。

**响应示例**

```
{
  "ok": true,
  "data": {
    "id":"9e2c...",
    "name":"设计说明.docx",
    "status":"READY",
    "chunk_count":146,
    "last_job_id":"job_31d...",
    "last_error":null
  }
}
```

**DELETE /documents/{document_id}**

删除文档。删除必须同时覆盖原文件、PostgreSQL 元数据、Chunk 记录与 pgvector 向量。

**参数**

| **名称** | **位置/类型** | **必填** | **说明** |
| --- | --- | --- | --- |
| purge_file | query/boolean | 否 | 默认 true；是否删除 RAG Service 托管的原始文件 |

**响应示例**

```
HTTP/1.1 202 Accepted
{
  "ok": true,
  "data": {"document_id":"9e2c...","job_id":"job_del...","status":"DELETING"}
}
```

- 验收要求：删除任务完成后，/query 不得再返回该 document_id 的任何 chunk。

- 重复 DELETE 建议幂等；已删除资源可返回 204 或带 deleted=true 的 200。

**POST /documents/{document_id}/reindex**

对已有文档重新解析、切片、向量化并替换旧索引。适用于切片参数、模型版本或解析器升级。

**请求示例**

```
{
  "reason": "embedding_model_changed",
  "force": true
}
```

**响应示例**

```
HTTP/1.1 202 Accepted
{
  "ok": true,
  "data": {"job_id":"job_reindex...","document_id":"9e2c..."}
}
```

**POST /documents/{document_id}/reparse**

对解析失败（FAILED）的文档重跑 PARSING → CHUNKING → EMBEDDING → INDEXING 流程。与 reindex 的区别：reparse 面向“解析阶段失败、尚未产生可用索引”的文档重试；reindex 面向“已就绪文档因模型/切片参数变化”的全量重建。

**响应示例**

```
HTTP/1.1 202 Accepted
{
  "ok": true,
  "data": {"job_id":"job_reparse...","document_id":"9e2c..."}
}
```

## 8.3 异步任务

**GET /jobs/{job_id}**

查询异步任务进度。Client 推荐轮询 500 ms～2 s，并在任务完成后停止。

**响应示例**

```
{
  "ok": true,
  "data": {
    "id":"job_31d...",
    "type":"DOCUMENT_INGEST",
    "status":"RUNNING",
    "progress":62,
    "stage":"EMBEDDING",
    "message":"Embedding 91 / 146 chunks"
  }
}
```

**GET /jobs**（v1.1+，MVP 不实现）

查询最近任务列表，用于“任务中心”页面。MVP 阶段只需 `GET /jobs/{job_id}` 单任务轮询即可覆盖上传/删除/重建的进度跟踪。

**参数**

| **名称** | **位置/类型** | **必填** | **说明** |
| --- | --- | --- | --- |
| status | query/string | 否 | PENDING/RUNNING/SUCCEEDED/FAILED/CANCELLED |
| limit | query/int | 否 | 默认 50，最大 200 |

**响应示例**

```
{
  "ok": true,
  "data": {"items": [], "total": 0}
}
```

## 8.4 RAG 检索

**POST /query**

执行向量召回 + rerank，返回最终上下文及引用。该接口是 service 获取 RAG 上下文的主入口。

**参数**

| **名称** | **位置/类型** | **必填** | **说明** |
| --- | --- | --- | --- |
| query | body/string | 是 | 用户问题或检索文本，去首尾空格后长度 > 0 |
| top_k | body/int | 否 | 向量初召回数量，建议默认 20 |
| rerank_top_k | body/int | 否 | 重排后返回数量，建议默认 6 |
| tags | body/string[] | 否 | 限定 metadata.tags |
| min_score | body/number | 否 | 最低召回阈值，可为空 |
| include_text | body/boolean | 否 | 默认 true |

**请求示例**

```
{
  "query": "索引重建接口在什么情况下使用？",
  "top_k": 20,
  "rerank_top_k": 6,
  "tags": ["项目A"],
  "include_text": true
}
```

**响应示例**

```
{
  "ok": true,
  "data": {
    "query": "索引重建接口在什么情况下使用？",
    "took_ms": 84,
    "results": [
      {
        "chunk_id":"chk_...",
        "document_id":"9e2c...",
        "document_name":"设计说明.docx",
        "text":"……当 embedding 模型或切片参数变化时，应重新构建索引……",
        "vector_score":0.8421,
        "rerank_score":0.7312,
        "citation": {"page":12,"section":"3.2 索引流程","chunk_index":37}
      }
    ]
  }
}
```

- 只允许 READY 文档参与检索。

- 最终排序 SHOULD 以 rerank_score 为主；若 reranker 关闭，可退化为 vector_score。

- citation MUST 足够让 UI 展示“来自哪个文档/页/Sheet/段落”。

- 当没有达到阈值的结果时返回 200 + results: []，不要伪造命中。

- 按文档集合过滤检索（document_ids）不在 MVP 范围，若需保留请标注 v1.1+。

- 返回字段命名（text / vector_score / rerank_score）需与 Agent 内核 doc_search 工具出参契约（目前为 snippet / score）在接口冻结时统一，避免适配层做无意义映射。

**POST /query/context**（v1.1+，MVP 不实现）

生成适合直接拼接到 LLM Prompt 的上下文块，但不调用大模型。MVP 阶段上下文拼接由 Agent 内核完成，RAG Service 只返回 chunks + citations，避免双份拼装逻辑漂移。

**请求示例**

```
{
  "query":"如何删除文档？",
  "rerank_top_k":4,
  "max_context_chars":12000
}
```

**响应示例**

```
{
  "ok": true,
  "data": {
    "context":"[1] 设计说明.docx p.12\n...",
    "citations":[{"index":1,"document_id":"...","page":12,"chunk_id":"..."}],
    "truncated":false
  }
}
```

## 8.5 索引管理

**POST /indexes/rebuild**

全量重建知识库索引。一般用于数据库结构迁移、Embedding 模型升级或 pgvector 索引损坏恢复。

**请求示例**

```
{
  "scope": "all",
  "force": false
}
```

**响应示例**

```
HTTP/1.1 202 Accepted
{
  "ok": true,
  "data": {"job_id":"job_rebuild...","status":"PENDING"}
}
```

**GET /indexes/status**

返回索引概况与一致性信息。

**响应示例**

```
{
  "ok": true,
  "data": {
    "documents_ready": 36,
    "chunks": 8241,
    "vectors": 8241,
    "orphan_vectors": 0,
    "embedding_model":"BAAI/bge-m3",
    "last_rebuild_at":"2026-08-27T08:20:00Z"
  }
}
```

**POST /indexes/compact**（v1.1+，MVP 不实现）

可选维护接口：压缩/优化 PostgreSQL/pgvector 数据文件。

**响应示例**

```
HTTP/1.1 202 Accepted
{
  "ok": true,
  "data": {"job_id":"job_compact..."}
}
```

## 8.6 统计与运行信息

**GET /stats**

用于管理后台“文档与索引”概览页与诊断页展示知识库规模、磁盘占用和任务数量。

**响应示例**

```
{
  "ok": true,
  "data": {
    "documents_total": 37,
    "documents_ready": 36,
    "documents_parsing": 1,
    "documents_failed": 0,
    "chunks_total": 8241,
    "storage_bytes": 338420112,
    "jobs_running": 0
  }
}
```

# 9. 错误码规范

| **HTTP** | **error.code** | **场景** |
| --- | --- | --- |
| 400 | INVALID_ARGUMENT | 缺少必填字段、字段类型错误、query 为空、不支持的文件类型、文件超过上限 |
| 400 | FAILED_PRECONDITION | 对未 READY 文档执行需就绪的操作；同一文档已有互斥任务运行；文件可接收但解析失败、解析后无可索引文本 |
| 400 | OUT_OF_RANGE | 分页/参数超出允许范围（page、page_size、top_k 等） |
| 401 | UNAUTHENTICATED | 缺少或校验失败 X-RAG-Service-Token |
| 403 | PERMISSION_DENIED | 客户端无权限访问该资源/接口 |
| 404 | NOT_FOUND | document_id / job_id 不存在 |
| 409 | ALREADY_EXISTS | 关闭自动去重时，重复文档被显式报告 |
| 429 | RESOURCE_EXHAUSTED | 请求配额/速率超限；文件体量超过配置上限 |
| 500 | INTERNAL | 未分类内部异常 |
| 500 | DATA_LOSS | 数据损坏或不可恢复（如元数据与向量不一致） |
| 501 | UNIMPLEMENTED | 功能未实现（如 OCR/图片能力，若未内置模型） |
| 503 | UNAVAILABLE | PostgreSQL 不可用；Embedding/Reranker 未加载 |
| 504 | DEADLINE_EXCEEDED | 解析/索引处理超时 |

错误码采用 Google API 标准错误模型（业界普遍一致使用的约定）：`error.code` 为稳定、机器可读的枚举值，并对应标准的 HTTP 状态码（400/401/403/404/409/429/500/501/503/504）。message 面向开发者，应该稳定、清晰；details 可包含阶段、原始异常类型、文档 ID 等诊断信息，但不应泄露本机绝对路径、隐私数据或完整堆栈。完整 traceback 写本地日志。

# 10. 文档解析与切片约定

| **类型** | **最小解析要求** | **Citation 定位** |
| --- | --- | --- |
| PDF | 提取分页文本；扫描 PDF 可走 OCR（若组件启用） | page |
| DOCX | 段落、标题、表格文本；尽量保留标题层级 | section / paragraph |
| XLSX/XLS | 按 Sheet、行列读取；表头与数据行一并组织 | sheet / cell_range |
| PNG/JPG/JPEG | OCR 或视觉文字提取；无可读文字时归入 FAILED_PRECONDITION（无索引文本） | image/page=1 |

建议默认切片策略（属于可配置默认值，不属于协议硬编码）：切片**不是一刀切**，而是按文件类型与数据量自适应。通用约束：标题、页码、Sheet、表头等结构元数据必须随 Chunk 保存；表格按“表头 + 若干连续数据行”组织，避免拆散表头。

- **按文件类型差异化**：
  - PDF / Word：优先按标题、章节、段落等结构边界切分，尽量保留标题层级，下一页/节用 citation 定位。
  - XLSX / XLS：按 Sheet + 表头 + 连续数据行切片，单行或行组为一个 chunk，表头随每个块保留。
  - 图片 / OCR：按页切分，每页作为一个 chunk，页码作为定位。
- **按数据量自适应**：
  - 小文件（如摘要、短文）：可整体作为少量 chunk 或按段落切，避免过度碎片化。
  - 中大文件（长报告、多页 PDF、大表格）：自动降低单 chunk 目标字符数、增加层级与块数，控制信息密度与总量。
  - 超长表格：按“表头 + 若干连续数据行”分块，避免单个 chunk 过大或拆掉表头。
- **基线参数**：单 chunk 目标字符数（如 700～1000 中文字符）与 overlap（如 80～150 字符）仅作为默认基线，实际按类型与规模动态调整，不写死；切片粒度上限应由配置约束（如 max_chunks 或单 chunk 最大字符数）。

- 每个 Chunk MUST 有稳定 chunk_id，且同一版本文档内 chunk_index 递增。

- 重建索引时使用“新索引完成后再切换”的 replace 策略，避免查询过程中出现半旧半新数据。

- 解析后的纯文本可选择落 PostgreSQL/独立缓存文件；但 API 不依赖其具体存储方式。

- 图片/OCR 功能如果未内置模型，应在 /version 或 capabilities 中明确报告 disabled，而不是静默失败。

# 11. Embedding、向量库与 Rerank 约定

Embedding 与 rerank 模型名称允许通过配置文件切换。接口层只暴露模型标识和版本，不把向量维度等底层细节泄露给调用方。推荐的处理链为：Query normalize → BGE query embedding → pgvector top-k 召回 → 元数据过滤 → rerank → 阈值裁剪 → 返回 Citation。

```
query
  → normalize
  → embedding(query)
  → pgvector vector search (top_k=20)
  → metadata/document filters
  → rerank(query, candidate_chunks)
  → top 6
  → response + citations
```

- 同一知识库中的向量必须由同一 embedding model/version 生成；模型变化必须触发重建。

- PostgreSQL 中建议记录 embedding_model、embedding_dim、chunker_version、parser_version、index_generation。

- Reranker 失败时可配置 fail-open：退化到向量得分，同时在响应 meta 中返回 rerank_degraded=true；是否允许退化由产品决定。

# 12. PostgreSQL 元数据建议 Schema

| **表** | **关键字段** | **用途** |
| --- | --- | --- |
| documents | id, name, mime_type, sha256, status, uploader, chunk_count, vector_count, metadata_json, created_at, updated_at, last_error | 文档主表 |
| chunks | id, document_id, chunk_index, text, locator_json, content_hash | Chunk 文本和引用定位 |
| jobs | id, type, status, progress, stage, payload_json, result_json, error_json, timestamps | 异步任务 |
| settings | key, value_json, updated_at | 本地配置与 schema/model 版本 |
| index_generations | id, embedding_model, chunker_version, created_at, active | 索引代次，用于原子切换 |

pgvector 中每条记录至少需要：chunk_id、document_id、vector、必要过滤字段（例如 tags 或 project_id）和 index_generation。正文可与向量同表存储，也可单独存储；若分开存储，查询时需避免 N+1 读。

# 13. 配置文件约定

建议 RAG Service 接受一个启动参数 --config <path>，配置采用 TOML 或 YAML。以下为建议项：

```
[server]
host = "127.0.0.1"
port = 17861
request_timeout_sec = 60

[storage]
data_dir = "<app-data>/rag-service"
database_url = "postgresql://rag:rag@127.0.0.1:5432/rag"
# pgvector 扩展在启动迁移时自动创建

[upload]
max_file_mb = 200
allowed_extensions = ["pdf", "docx", "xlsx", "xls", "png", "jpg", "jpeg"]

[chunking]
# 默认基线；实际按文件类型与数据量动态调整
target_chars = 850
overlap_chars = 120
max_chunks = 5000

[embedding]
model = "BAAI/bge-m3"
batch_size = 32

[rerank]
enabled = true
model = "BAAI/bge-reranker-v2-m3"

[search]
top_k = 20
rerank_top_k = 6
```

模型路径可在镜像构建时改为本地相对路径，避免运行期联网下载。所有配置应可被 /version 或 /capabilities 以“非敏感摘要”形式查看，便于联调。

# 14. 容器化交付与同 pod 启动约定

RAG Service 以容器镜像交付，与 service、PostgreSQL 部署在同一个 K8s pod 内。镜像内预置 Python 运行时、模型权重与依赖，运行期不依赖企业外网。

1. 镜像构建：基础镜像 + 应用代码 + 模型权重；模型可打进镜像，也可通过只读卷/InitContainer 挂载，二者皆可。

2. 同 pod 启动顺序：RAG Service 启动期间完成数据库迁移、pgvector 初始化（扩展/索引）和模型加载；这些耗时操作不得阻塞 /health。service 只有在 RAG Service 的 /ready.ready=true 之后才开放知识库路由，可直接对接 K8s readiness 探针。

3. 端口与通信：RAG Service 在容器内使用固定端口（同 pod localhost 通信），不暴露到 Service 网络。

4. 部署约束一：PostgreSQL 数据目录挂载 PVC，保证 pod 重建后元数据与向量不丢失。

5. 部署约束二：RAG Service 容器配置独立的 resource limits，避免 embedding 等 CPU/内存密集型任务拖垮同 pod 的 PostgreSQL。

6. 退出：RAG Service 收到终止信号后，必须安全关闭 PostgreSQL 连接池与 pgvector 连接。

# 15. 日志、诊断与可观测性

| **项** | **要求** |
| --- | --- |
| 日志输出 | 输出到 stdout/stderr，由 K8s/平台日志层统一采集；不自行落地文件 |
| 日志格式 | 建议 JSON Lines；至少包含 timestamp、level、event、request_id、job_id/document_id |
| 日志级别 | DEBUG / INFO / WARNING / ERROR |
| 敏感信息 | 禁止写入完整文档正文、token、绝对用户隐私路径；必要时只写 basename/hash |
| 性能字段 | query_took_ms、embedding_ms、rerank_ms、candidates、results |
| 诊断包 | 可选：导出版本、配置摘要、最近日志和 DB schema 版本，不导出用户文档正文 |

# 16. 并发、幂等与一致性

- 上传和查询可并发；同一 document_id 的 delete/reindex 应互斥。

- PostgreSQL 采用连接池与合适的事务隔离，设置 statement_timeout / lock_timeout，避免查询与状态更新互相阻塞。

- 异步任务必须持久化 Job 状态；RAG Service 异常退出后，启动时将 RUNNING 任务恢复为 FAILED/INTERRUPTED 或按策略继续。

- DELETE 操作必须对 PostgreSQL（元数据与向量）采用可恢复流程；若部分删除失败，状态保持 DELETING/FAILED 并允许重试。

- 重建索引采用 generation 或临时表机制，完成后原子切换 active generation；切换前旧索引继续服务。

- 对上传可支持 Idempotency-Key（v1.1+）；相同 key + 相同 body 在有效期内返回同一结果。

# 17. 验收标准

| **编号** | **验收场景** | **通过条件** |
| --- | --- | --- |
| A01 | RAG Service 启动 | pod 启动后 /health=200；PG 与模型就绪后 /ready.ready=true（“无需账号服务”可保留：认证在 service 层） |
| A02 | 上传 PDF/Word/Excel/图片 | POST /documents 返回 202；状态按流程进入 READY 或给出明确 FAILED |
| A03 | 状态流转 | UI 可通过 /jobs 或 /documents/{id} 看到“解析中→已入知识库” |
| A04 | 检索命中 | 对文档内已知问题，/query 返回相关 Chunk 且 citation 可定位原文 |
| A05 | 删除文档 | 删除任务完成后，文档不在默认列表中，且 /query 无法检索到该 document_id |
| A06 | 重建索引 | /indexes/rebuild 可完成；重建期间查询不出现半索引状态 |
| A07 | 重复上传 | 相同文件在 deduplicate=true 时不生成重复向量 |
| A08 | 断电/强杀恢复 | 再次启动数据库可打开；残留 RUNNING 任务被正确处理 |
| A09 | 本地安全 | 服务仅监听 127.0.0.1/::1，局域网地址不可访问 |
| A10 | 容器化交付 | pod 部署后，经 service 完成上传 → 检索 → 删除闭环 |

# 18. 推荐联调流程

```
1) Start RAG Service
2) GET /health
3) GET /ready
4) POST /documents                    → document_id + job_id
5) GET /jobs/{job_id}                 → RUNNING ... SUCCEEDED
6) GET /documents/{document_id}       → READY
7) POST /query                        → chunks + citations
8) DELETE /documents/{document_id}    → delete job
9) GET /jobs/{delete_job_id}          → SUCCEEDED
10) POST /query                       → no result from deleted document
```

# 19. 向后兼容与版本演进

- v1 内新增可选字段属于兼容性变更；Client 必须忽略未知字段。

- 删除字段、修改字段类型、改变状态语义等属于破坏性变更，应升级 /api/v2。

- 数据库 schema_version 与 API version 分离；内部迁移不应迫使 Client 升级。

- 模型升级如果会改变既有向量语义，必须记录新的 index_generation 并触发重建。

# 20. OpenAPI 交付建议

正式开发时建议 RAG Service 使用 FastAPI/Pydantic 直接生成 OpenAPI 3.1，并提供 /docs（仅开发模式）与 /openapi.json。前后端 SDK 可基于 openapi.json 自动生成，减少字段漂移。生产环境可以关闭 Swagger UI，但保留版本化的 openapi.json 文件随源码交付。

```
openapi: 3.1.0
info:
  title: RAG Service API
  version: 1.0.0
servers:
  - url: http://127.0.0.1:{port}/api/v1
paths:
  /health: ...
  /ready: ...
  /documents: ...
  /documents/{document_id}: ...
  /jobs/{job_id}: ...
  /query: ...
  /indexes/rebuild: ...
```

# 21. 开发前需要团队冻结的 10 个参数

| **#** | **决策项** | **建议初值** |
| --- | --- | --- |
| 1 | 端口 | 容器内固定端口（同 pod localhost 通信）；可预留 17861 |
| 2 | 是否启用 X-RAG-Service-Token | 建议启用 |
| 3 | 单文件最大体积 | 200 MB |
| 4 | 是否支持扫描 PDF / 图片 OCR | 支持但可作为 capability 开关 |
| 5 | BGE Embedding 型号 | bge-m3（或项目已有模型） |
| 6 | Reranker 型号 | bge-reranker-v2-m3（或项目已有模型） |
| 7 | Chunk 大小/Overlap | 850 / 120 中文字符 |
| 8 | 召回 top_k / rerank_top_k | 20 / 6 |
| 9 | 重复文件策略 | SHA-256 去重 |
| 10 | 镜像交付方式 | 基础镜像选型；模型打进镜像还是挂载只读卷 |

> 另需冻结：/query 返回字段命名与 Agent 内核 doc_search 出参（snippet / score）的统一映射。

# 附录 A：统一成功响应建议

```
{
  "ok": true,
  "data": {},
  "meta": {
    "request_id": "req_...",
    "api_version": "v1"
  }
}
```

# 附录 B：统一失败响应建议

```
{
  "ok": false,
  "error": {
    "code": "INVALID_ARGUMENT",
    "message": "query must not be empty",
    "details": {"field": "query"},
    "request_id": "req_..."
  }
}
```

# 附录 C：建议目录结构

```
rag-service/
├─ app/
│  ├─ api/
│  ├─ parsers/
│  ├─ chunking/
│  ├─ embedding/
│  ├─ rerank/
│  ├─ storage/
│  ├─ jobs/
│  └─ models/
├─ migrations/
├─ tests/
├─ config.example.toml
├─ pyproject.toml
└─ build.spec
```
