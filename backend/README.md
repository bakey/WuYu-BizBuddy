# BizBuddy RAG Service

基于 FastAPI + PostgreSQL(pgvector) 的 RAG 后台服务。

## 功能

- 文档上传与向量存储
- 基于向量相似度的检索
- 结合大模型生成回答
- 支持流式返回 (SSE)

## 技术栈

- FastAPI
- SQLAlchemy + pgvector
- OpenAI (嵌入 + 大模型)
- uv / pytest / ruff / pyright

## 本地开发环境

详见 [LOCAL_SETUP.md](./LOCAL_SETUP.md)，包含 Postgres Docker、数据库初始化、前后端启动完整步骤。

## 快速开始

### 1. 环境准备

需要 PostgreSQL 并启用 pgvector 扩展：

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### 2. 配置

复制环境变量示例：

```bash
cp .env.example .env
```

编辑 `.env`，填入 `DATABASE_URL` 和 `OPENAI_API_KEY`。

### 3. 启动服务

```bash
uv run -m bizbuddy_rag.main
```

或：

```bash
uv run uvicorn bizbuddy_rag.main:app --reload
```

服务启动后会自动创建数据表。

## API 接口

完整接口文档见 [docs/API.md](./docs/API.md)。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/health` | 健康检查 |
| POST | `/api/v1/documents` | 上传文档 |
| GET | `/api/v1/documents` | 列出文档 |
| DELETE | `/api/v1/documents/{id}` | 删除文档 |
| POST | `/api/v1/retrieve` | 向量检索 |
| POST | `/api/v1/query` | RAG 问答 |
| POST | `/api/v1/query/stream` | 流式 RAG 问答 |

## 示例

上传文档：

```bash
curl -X POST http://localhost:8000/api/v1/documents \
  -H "Content-Type: application/json" \
  -d '{"content": "BizBuddy 是一个智能业务助手。", "source": "intro"}'
```

RAG 问答：

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "BizBuddy 是什么？"}'
```

## 测试

```bash
uv run pytest
```

## 代码检查

```bash
uv run ruff check src
uv run ruff format src
uv run pyright src
```
