# BizBuddy RAG Service — API 文档

> Base URL: `http://localhost:8000/api/v1`  
> Content-Type: `application/json`

---

## 目录

- [1. 健康检查](#1-健康检查)
- [2. 文档管理](#2-文档管理)
  - [2.1 上传文档](#21-上传文档)
  - [2.2 列出文档](#22-列出文档)
  - [2.3 删除文档](#23-删除文档)
- [3. 检索与问答](#3-检索与问答)
  - [3.1 向量检索](#31-向量检索)
  - [3.2 RAG 问答](#32-rag-问答)
  - [3.3 流式 RAG 问答 (SSE)](#33-流式-rag-问答-sse)

---

## 通用模型

### RetrievedChunk

检索到的文档片段。

| 字段 | 类型 | 说明 |
|------|------|------|
| `content` | `string` | 文档内容 |
| `source` | `string \| null` | 文档来源 |
| `score` | `number` | 余弦相似度得分 (0 ~ 1) |
| `metadata` | `object \| null` | 附加元数据 |

---

## 1. 健康检查

### GET `/health`

检查服务运行状态。

**响应示例 (200)**

```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

---

## 2. 文档管理

### 2.1 上传文档

### POST `/documents`

上传文档内容，服务会自动调用 Embedding 模型生成向量，并写入 PostgreSQL。

**请求体**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `content` | `string` | ✅ | 文档内容，至少 1 个字符 |
| `source` | `string` | — | 文档来源标识 |
| `metadata` | `object` | — | 自定义附加元数据 |

**请求示例**

```bash
curl -X POST http://localhost:8000/api/v1/documents \
  -H "Content-Type: application/json" \
  -d '{
    "content": "BizBuddy 是一款面向中小企业的智能业务助手，支持客户管理、订单跟踪和数据分析。",
    "source": "product-intro",
    "metadata": { "category": "product", "lang": "zh" }
  }'
```

**响应示例 (200)**

```json
{
  "id": 1,
  "content": "BizBuddy 是一款面向中小企业的智能业务助手...",
  "source": "product-intro",
  "metadata": { "category": "product", "lang": "zh" }
}
```

**错误码**

| 状态码 | 说明 |
|--------|------|
| 422 | 请求参数校验失败（如 content 为空） |
| 500 | Embedding 服务调用失败 |

---

### 2.2 列出文档

### GET `/documents`

分页列出已上传的文档列表（不包含向量字段）。

**查询参数**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `limit` | `integer` | 100 | 返回数量上限 |
| `offset` | `integer` | 0 | 偏移量 |

**请求示例**

```bash
curl "http://localhost:8000/api/v1/documents?limit=10&offset=0"
```

**响应示例 (200)**

```json
[
  {
    "id": 2,
    "content": "第二篇文档内容...",
    "source": null,
    "metadata": null
  },
  {
    "id": 1,
    "content": "BizBuddy 是一款面向中小企业的智能业务助手...",
    "source": "product-intro",
    "metadata": { "category": "product", "lang": "zh" }
  }
]
```

---

### 2.3 删除文档

### DELETE `/documents/{doc_id}`

根据 ID 删除文档及其向量记录。

**路径参数**

| 参数 | 类型 | 说明 |
|------|------|------|
| `doc_id` | `integer` | 文档 ID |

**请求示例**

```bash
curl -X DELETE http://localhost:8000/api/v1/documents/1
```

**响应示例 (200)**

```json
{ "deleted": true }
```

**错误码**

| 状态码 | 说明 |
|--------|------|
| 404 | 文档不存在 |

---

## 3. 检索与问答

### 3.1 向量检索

### POST `/retrieve`

仅执行向量相似度检索，不调用大模型生成回答。适用于需要自行处理检索结果的场景。

**请求体**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `query` | `string` | ✅ | — | 检索语句 |
| `top_k` | `integer` | — | 5 | 返回最相似的 top_k 条，范围 1~20 |

**请求示例**

```bash
curl -X POST http://localhost:8000/api/v1/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "query": "BizBuddy 有什么功能？",
    "top_k": 3
  }'
```

**响应示例 (200)**

```json
[
  {
    "content": "BizBuddy 是一款面向中小企业的智能业务助手，支持客户管理、订单跟踪和数据分析。",
    "source": "product-intro",
    "score": 0.9123,
    "metadata": { "category": "product", "lang": "zh" }
  }
]
```

> 实际返回条数受 `rag_similarity_threshold` 配置影响，低于阈值的文档会被过滤。

**错误码**

| 状态码 | 说明 |
|--------|------|
| 422 | 请求参数校验失败 |
| 500 | Embedding 或数据库查询失败 |

---

### 3.2 RAG 问答

### POST `/query`

完整 RAG 流程：向量检索 → 构造上下文 → 调用大模型生成回答。

**请求体**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `prompt` | `string` | ✅ | — | 用户问题 |
| `top_k` | `integer` | — | 5 | 检索 top_k 条文档作为上下文 |
| `stream` | `boolean` | — | false | 是否流式返回（本接口固定为非流式） |

**请求示例**

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "BizBuddy 是什么？",
    "top_k": 5
  }'
```

**响应示例 (200)**

```json
{
  "answer": "BizBuddy 是一款面向中小企业的智能业务助手，支持客户管理、订单跟踪和数据分析。",
  "references": [
    {
      "content": "BizBuddy 是一款面向中小企业的智能业务助手，支持客户管理、订单跟踪和数据分析。",
      "source": "product-intro",
      "score": 0.9123,
      "metadata": { "category": "product", "lang": "zh" }
    }
  ]
}
```

**错误码**

| 状态码 | 说明 |
|--------|------|
| 422 | 请求参数校验失败 |
| 500 | Embedding、检索或 LLM 调用失败 |

---

### 3.3 流式 RAG 问答 (SSE)

### POST `/query/stream`

与 `/query` 功能相同，但以 **Server-Sent Events (SSE)** 格式流式返回结果。

适用场景：前端需要逐步展示回答文本、减少首字等待时间。

**请求体**

与 `/query` 完全一致。

**请求示例**

```bash
curl -X POST http://localhost:8000/api/v1/query/stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "prompt": "BizBuddy 是什么？",
    "top_k": 5
  }'
```

**SSE 事件说明**

| event | data 类型 | 说明 |
|-------|-----------|------|
| `references` | `RetrievedChunk[]` | 首先推送检索到的参考资料 |
| `delta` | `{"delta": "文本片段"}` | 逐字/逐句推送大模型生成的内容 |
| `done` | `[DONE]` | 流结束标记 |
| `error` | `{"error": "错误信息"}` | 流程中出现异常 |

**响应示例 (SSE)**

```text
event: references
data: [{"content":"...","source":"product-intro","score":0.9123,"metadata":{}}]

event: delta
data: {"delta": "BizBuddy"}

event: delta
data: {"delta": " 是一款"}

event: delta
data: {"delta": " 面向中小企业的智能业务助手。"}

event: done
data: [DONE]
```

**前端连接示例 (JavaScript)**

```javascript
const eventSource = new EventSource('/api/v1/query/stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ prompt: 'BizBuddy 是什么？', top_k: 5 }),
});

eventSource.addEventListener('references', (e) => {
  const refs = JSON.parse(e.data);
  console.log('参考资料:', refs);
});

eventSource.addEventListener('delta', (e) => {
  const { delta } = JSON.parse(e.data);
  document.getElementById('answer').textContent += delta;
});

eventSource.addEventListener('done', () => {
  eventSource.close();
});

eventSource.addEventListener('error', (e) => {
  console.error('SSE 错误:', JSON.parse(e.data));
  eventSource.close();
});
```

---

## 状态码汇总

| 状态码 | 含义 |
|--------|------|
| 200 | 请求成功 |
| 404 | 资源不存在（如删除不存在的文档） |
| 422 | 请求参数校验失败 |
| 500 | 服务端内部错误（Embedding / LLM / 数据库） |
