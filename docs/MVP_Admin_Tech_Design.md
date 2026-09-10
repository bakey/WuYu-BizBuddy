# 无隅 BizBuddy MVP 管理后台技术设计

> 上游文档：`docs/MVP_PRD.md`（6.4/6.5/6.6 节）、`docs/MVP_Client_Tech_Design.md`（私有云总体架构）
> 对应原型：`wuyu_product_mvp_admin.html`
> 负责角色：4 号（D + F）；管理后台前端约 4 周，service/RAG/Collector/内核侧工作量分别计入对应模块
> 部署基线：企业私有云 Web 管理后台；RAG、模型配置、会话轨迹与时序数据均在私有云维护
> 状态：草案 v2

---

## 1. 目标与范围

管理后台是企业 IT 管理员通过内网访问的 Web 控制台，覆盖 MVP PRD 中的五个管理页面：

| 页面 | 对应 PRD | 核心能力 |
|------|----------|----------|
| 文档与索引 | 6.4.1 | 全量文档管理、RAG 索引状态、重建索引、重新解析、删除 |
| DCS 接入 | 6.4.2 | 数据源 CRUD、连接测试、启停、点位配置和批量导入 |
| 接入客户端 | 6.4.3 | Collector 心跳、数据延迟、协议能力和状态，只读展示 |
| 模型配置 | 6.5 | OpenAI 兼容端点 CRUD、默认模型、连接测试、私有云存储状态 |
| 轨迹观测 | 6.6 | 执行记录列表和详情，包括计划、工具调用、引用和 token 使用 |

**不做**：多租户、多厂区隔离、点位图表、Collector 远程启停、费用统计、成功率趋势、失败自动归因、本地 LLM。

---

## 2. 总体架构与部署形态

管理后台部署在企业私有云，管理员通过企业内网 HTTPS 地址访问。桌面端的「管理后台」入口只负责调用默认浏览器打开该地址，不在 Electron 内嵌管理页面。

```
管理员浏览器
  https://bizbuddy-admin.corp.internal
        │ HTTPS + Admin Token
        ▼
┌──────────────── 企业私有云 ────────────────────────────────────────┐
│ Ingress / service（唯一对外入口）                                  │
│ ├─ 托管 admin/dist SPA                                             │
│ ├─ /api/admin/*：管理员鉴权与管理 API                              │
│ ├─ /api/client/*：桌面客户端认证、文档、对话和历史                  │
│ └─ /internal/*：受保护的内部组件与 Collector API                   │
│         │                    │                    │                 │
│         ▼                    ▼                    ▼                 │
│ Agent 内核（dsh）      Python RAG sidecar     Collector 配置/数据面 │
│ 会话与执行轨迹          文档处理与 pgvector     注册/配置/心跳/写入  │
│         │                    │                    ▲                 │
│         └────────────┬───────┘                    │                 │
│                      ▼                            │                 │
│ PostgreSQL + pgvector（独立 StatefulSet/托管实例） │                 │
│ 私有云文档存储（PVC 或企业对象/文件存储）           │                 │
│                      ▲                            │                 │
│            DCS Collector（独立工作负载，可部署于厂区网络）─────────┘ │
└───────────────────────────────────────────────────────────────────┘
```

关键决策：

- **service 是唯一对外入口**：管理后台不直接访问 sidecar、Agent 内核、数据库或 Collector。
- **应用 Pod 无状态化**：service、admin SPA 和 RAG sidecar 可以同 Pod 部署，但 PostgreSQL、原始文档和解析产物必须使用独立持久化存储，Pod 重建不得导致数据丢失。
- **RAG 只在私有云运行**：桌面端上传文件后，私有云完成保存、解析、切片、Embedding、索引和检索。
- **Collector 独立部署**：Collector 部署在能够访问工业设备的受控网络，通过主动连接私有云完成注册、配置拉取、数据写入和心跳上报。
- **模型配置集中管理**：API Key 在服务端加密保存并只注入私有云 Agent 内核，不下发桌面端或浏览器。
- **断网语义分层**：公网不可用但私有云可达时，文档与管理功能仍可用；私有云不可达时管理后台不可用。

---

## 3. 前端设计

### 3.1 工程结构

```
admin/
├── package.json / vite.config.ts / tsconfig.json
├── index.html
└── src/
    ├── main.ts / App.vue
    ├── api/
    │   ├── client.ts           # 同源 baseURL、token 注入、requestId、错误归一化
    │   ├── documents.ts
    │   ├── dcs.ts
    │   ├── models.ts
    │   ├── storage.ts
    │   └── traces.ts
    ├── types.ts
    ├── router.ts               # 五个管理页面 + 登录页
    └── views/
        ├── LoginView.vue
        ├── DocsIndexView.vue
        ├── DcsSourcesView.vue
        ├── ClientsView.vue
        ├── ModelsView.vue
        └── TracesView.vue
```

布局与交互以 `wuyu_product_mvp_admin.html` 为视觉基准：顶部通栏、左侧分组导航、右侧内容区。SPA 与 API 同源部署，不开放跨域访问。

### 3.2 关键交互

| 交互 | 设计 |
|------|------|
| 数据源连接测试 | service 将测试路由到具备协议能力且能访问目标网络的在线 Collector；成功后返回与配置摘要绑定、短期有效的 `testToken` |
| 数据源保存 | 前端测试通过前禁用保存；后端创建或修改连接参数时也必须校验 `testToken`，禁止绕过 UI |
| 模型连接测试 | 使用未保存草稿测试；API Key 只随 HTTPS 请求进入 service，不写前端日志或状态持久化 |
| 点位批量导入 | 支持粘贴或上传 CSV；前端解析预览，服务端再次校验字段、重复 tag 和数量限制 |
| 重建索引 / 重新解析 | 接口返回 `operationId`；前端轮询统一任务状态，展示阶段、进度和失败原因 |
| 接入客户端 | 5 秒轮询；状态由服务端根据心跳阈值推导，同时展示配置版本和最近错误 |
| 轨迹详情 | 抽屉展示计划、工具调用摘要、引用、耗时、token 使用和关联请求 ID；敏感入参脱敏 |
| 协议能力 | MVP 只启用 OPC UA；Modbus/MQTT 隐藏或显示为不可用，不允许提交 |
| 异常与空态 | 所有页面提供空态、加载失败重试、权限失效跳转登录和私有云连接异常提示 |

---

## 4. API 设计

### 4.1 通用约定

- 对外管理 API 统一前缀 `/api/admin`，除登录外均要求 `Authorization: Bearer <admin-token>`。
- JSON 错误统一为 `{ "error": { "code": "...", "message": "...", "requestId": "...", "details": {} } }`。
- 列表使用 `?q=&page=&size=`，响应返回 `{ items, page, size, total }`，不提供“有时分页、有时全量”的双重语义。
- 写操作接受 `Idempotency-Key`；异步操作返回 `202 { operationId }`。
- 所有时间使用 UTC ISO 8601；对外 ID 使用 UUID，不暴露数据库自增序号。
- service 完成鉴权、授权、审计、限流和字段脱敏后，才调用内部组件。

### 4.2 管理员认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/admin/login` | `{ password }` 换取短期 access token；失败登录受速率限制 |
| POST | `/api/admin/logout` | 吊销当前 token |
| POST | `/api/admin/password` | 已登录管理员修改密码，并吊销其他 token |

初始密码在私有云首次部署时通过 Secret 或交互式 CLI 设置，不写入镜像、日志或默认配置。token 最长 24 小时过期，服务端保存可吊销的会话摘要。

### 4.3 文档与索引

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/rag/status` | `{ total, indexed, parsing, failed, queued }` |
| GET | `/api/admin/documents` | 全量文档分页列表，含上传人、来源客户端、文件状态和索引进度 |
| GET | `/api/admin/documents/{id}` | 文档详情和脱敏后的切片预览 |
| POST | `/api/admin/documents/{id}/reindex` | 使用现有切片重建向量，返回 `operationId` |
| POST | `/api/admin/documents/{id}/reparse` | 从持久化原始文件重新解析，返回 `operationId` |
| DELETE | `/api/admin/documents/{id}` | 异步删除原始文件、解析产物、切片和向量，返回 `operationId` |
| GET | `/api/admin/operations/{id}` | 查询异步任务状态、阶段、进度和失败原因 |

文档列表项至少包含：

```jsonc
{
  "id": "uuid",
  "name": "有限空间作业管理制度.pdf",
  "uploaderId": "user-or-device-id",
  "uploaderName": "张三",
  "sourceClientId": "desktop-client-id",
  "sizeBytes": 1048576,
  "mimeType": "application/pdf",
  "parseStatus": "queued", // queued / parsing / done / failed
  "failReason": null,
  "chunkCount": 128,
  "vectorCount": 128,
  "uploadedAt": "2026-09-10T08:00:00Z",
  "updatedAt": "2026-09-10T08:01:00Z"
}
```

`uploaderId` 和 `sourceClientId` 必须来自已认证客户端上下文，不接受客户端提交自由文本冒充身份。

### 4.4 DCS 数据源

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/ts-capabilities` | 返回实际启用协议及可执行测试的在线 Collector 能力 |
| GET | `/api/admin/ts-sources` | 数据源分页列表，含配置版本、连接状态、最近成功时间和最近错误 |
| POST | `/api/admin/ts-sources/test` | 测试表单草稿；由 service 路由到 Collector，成功返回 `testToken` |
| POST | `/api/admin/ts-sources` | 创建数据源；必须携带与当前配置绑定的有效 `testToken` |
| GET | `/api/admin/ts-sources/{id}` | 返回详情；密码等敏感字段仅返回是否已配置 |
| PUT | `/api/admin/ts-sources/{id}` | 修改；连接或点位配置变化时必须重新测试 |
| DELETE | `/api/admin/ts-sources/{id}` | 软删除并停用配置；历史时序数据按 7 天保留策略自然过期后再清理配置 |
| POST | `/api/admin/ts-sources/{id}/toggle` | 启用或停用，生成新配置版本 |

测试成功响应示例：

```jsonc
{
  "ok": true,
  "latencyMs": 35,
  "collectorId": "uuid",
  "testToken": "opaque-short-lived-token",
  "expiresAt": "2026-09-10T08:05:00Z"
}
```

`testToken` 必须绑定标准化后的协议、连接配置和点位配置摘要；表单发生变化后不可继续使用。MVP 只接受 `opcua`，其他协议返回明确的 `PROTOCOL_NOT_ENABLED`。

### 4.5 Collector 管理与内部协议

管理员只读接口：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/clients` | Collector 列表，含能力、心跳、延迟、配置版本、状态和最近错误 |

Collector 内部接口不使用管理员 token，并与 `/api/admin` 隔离：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/internal/collectors/register` | 使用部署凭证或 mTLS 身份注册，返回 collector ID 与短期凭证 |
| POST | `/internal/collectors/{id}/heartbeat` | 上报时间、延迟、协议能力、当前配置版本和健康状态 |
| GET | `/internal/collectors/{id}/config` | 使用 `afterVersion` 长轮询获取适用的新配置，不建立静态数据源绑定 |
| POST | `/internal/collector-tests/{jobId}/result` | 上报连接测试结果；service 据此签发 `testToken` |
| POST | `/internal/timeseries/samples` | 批量写入点位值、采集时间、质量码和来源 Collector |

Collector 状态由服务端计算：最近心跳不超过 30 秒为在线，超过 30 秒为离线。Collector 只主动连接私有云，私有云不反向打开厂区网络端口。

### 4.6 模型配置

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/models` | 模型端点列表；只返回 `hasApiKey` 和脱敏提示，不返回可复用的 Key 片段 |
| POST | `/api/admin/models` | 新增端点 |
| PUT | `/api/admin/models/{id}` | 更新端点；未提交 `apiKey` 表示保留原 Key，提交新值表示替换 |
| DELETE | `/api/admin/models/{id}` | 删除非默认端点；默认端点不可删除 |
| POST | `/api/admin/models/{id}/default` | 在事务中原子切换唯一默认模型 |
| POST | `/api/admin/models/test` | 使用未保存草稿测试连接，不记录完整请求体 |

数据库必须保证同一企业部署最多一个默认模型，例如使用部分唯一索引。切换默认模型成功后，Agent 内核通过配置版本刷新，无需重启桌面客户端。

### 4.7 私有云存储

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/settings/storage` | 返回数据库、文档存储、时序存储的逻辑位置、容量、已用空间和健康状态 |
| PUT | `/api/admin/settings/storage` | 仅允许切换到部署时预先批准的存储后端；返回迁移 `operationId` |

API 不接受任意宿主机路径。存在数据时修改存储必须执行校验、复制、校验和比对、原子切换和可回滚迁移；迁移期间上传和删除进入维护状态。若部署环境不支持在线迁移，MVP UI 只读展示并引导管理员使用部署 CLI 修改。

### 4.8 轨迹观测

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/traces` | 分页列表：时间、问题摘要、状态、引用数、耗时、requestId |
| GET | `/api/admin/traces/{id}` | 详情：计划、工具调用摘要、引用、token 使用和回答 |

Agent 内核把会话和执行轨迹写入 PostgreSQL 持久化存储；管理 API 查询持久化投影，不依赖 Pod 临时日志。工具参数和结果必须按字段策略脱敏，不向前端返回模型 API Key、DCS 凭证或完整文档正文。

---

## 5. 数据模型

以下为管理后台依赖的关键字段；完整迁移由各模块维护。

```sql
-- 文档：原始文件位于私有云持久化文件存储
ALTER TABLE documents ADD COLUMN uploader_id UUID;
ALTER TABLE documents ADD COLUMN source_client_id UUID;
ALTER TABLE documents ADD COLUMN storage_uri TEXT;
ALTER TABLE documents ADD COLUMN content_hash TEXT;
ALTER TABLE documents ADD COLUMN mime_type TEXT;
ALTER TABLE documents ADD COLUMN parse_status TEXT DEFAULT 'queued';
ALTER TABLE documents ADD COLUMN fail_reason TEXT;
ALTER TABLE documents ADD COLUMN chunk_count INTEGER DEFAULT 0;
ALTER TABLE documents ADD COLUMN vector_count INTEGER DEFAULT 0;
ALTER TABLE documents ADD COLUMN updated_at timestamptz DEFAULT now();

CREATE INDEX documents_uploader_idx ON documents (uploader_id, uploaded_at DESC);
CREATE INDEX documents_content_hash_idx ON documents (content_hash);

CREATE TABLE time_series_sources (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    protocol VARCHAR(50) NOT NULL CHECK (protocol IN ('opcua', 'modbus', 'mqtt')),
    connection_config_enc BYTEA NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    config_version BIGINT NOT NULL DEFAULT 1,
    connection_status VARCHAR(32) NOT NULL DEFAULT 'unknown',
    last_success_at timestamptz,
    last_error_code VARCHAR(100),
    last_error_message TEXT,
    deleted_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE time_series_tags (
    id UUID PRIMARY KEY,
    source_id UUID NOT NULL REFERENCES time_series_sources(id),
    tag_name VARCHAR(255) NOT NULL,
    display_name VARCHAR(255),
    unit VARCHAR(50),
    description TEXT,
    UNIQUE (source_id, tag_name)
);

CREATE TABLE collector_clients (
    id UUID PRIMARY KEY,
    instance_id VARCHAR(255) NOT NULL UNIQUE,
    display_name VARCHAR(255) NOT NULL,
    auth_subject VARCHAR(255) NOT NULL UNIQUE,
    capabilities JSONB NOT NULL,
    last_heartbeat_at timestamptz,
    latency_ms INTEGER,
    config_version BIGINT NOT NULL DEFAULT 0,
    last_error_code VARCHAR(100),
    last_error_message TEXT,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE time_series_samples (
    tag_id UUID NOT NULL REFERENCES time_series_tags(id),
    collector_id UUID NOT NULL REFERENCES collector_clients(id),
    sampled_at timestamptz NOT NULL,
    value_double DOUBLE PRECISION,
    value_text TEXT,
    quality VARCHAR(32),
    PRIMARY KEY (tag_id, sampled_at)
) PARTITION BY RANGE (sampled_at);

CREATE TABLE model_endpoints (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    model_id VARCHAR(255) NOT NULL,
    base_url VARCHAR(512) NOT NULL,
    api_key_enc BYTEA NOT NULL,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    config_version BIGINT NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX model_endpoints_one_default
    ON model_endpoints (is_default) WHERE is_default;

CREATE TABLE admin_auth (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    password_hash TEXT NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE admin_sessions (
    id UUID PRIMARY KEY,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE async_operations (
    id UUID PRIMARY KEY,
    operation_type VARCHAR(64) NOT NULL,
    resource_type VARCHAR(64) NOT NULL,
    resource_id UUID,
    status VARCHAR(32) NOT NULL,
    progress INTEGER NOT NULL DEFAULT 0,
    stage VARCHAR(100),
    error_code VARCHAR(100),
    error_message TEXT,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
```

时序分区由定时任务滚动创建，并删除早于 7 天的分区。已软删除数据源的样本过期后，再清理其 tag 和数据源记录。Agent 会话和轨迹表由内核模块维护，但必须位于持久化 PostgreSQL 或等价持久化存储中。

---

## 6. 持久化、备份与删除

- PostgreSQL 使用企业托管实例或 StatefulSet + PVC，启用定期备份和恢复演练，不与无状态应用容器共享临时磁盘。
- 原始文档和解析产物保存到加密 PVC 或企业对象/文件存储；数据库只保存不可由用户控制的内部 `storage_uri`。
- 文档重建索引和重新解析必须从持久化原始文件读取，Pod 重启或滚动升级后仍可执行。
- 删除文档通过异步任务级联清除原始文件、解析产物、切片、向量和相关缓存；失败步骤可重试，并保留管理员审计记录。
- DCS 数据严格保留 7 天；文档、会话和执行轨迹长期保留，直到管理员主动删除或企业部署策略调整。
- 数据库、文档存储和备份全部静态加密；加密密钥来自 Secret/KMS，不写数据库、镜像或日志。

---

## 7. 权限与安全

- **管理员认证**：MVP 单管理员，密码使用 bcrypt 或 Argon2id；登录 token 可吊销且最长 24 小时过期。
- **客户端与管理员隔离**：桌面客户端凭证不能调用 `/api/admin/*`；管理员 token 不能作为 Collector 凭证。
- **Collector 身份**：优先使用 mTLS；若使用部署凭证，只允许首次注册并立即兑换短期、可轮换的实例凭证。
- **传输安全**：客户端、管理后台、Collector 和外部模型调用全部使用 HTTPS；生产环境禁止跳过证书校验。
- **进程边界**：RAG sidecar 若与 service 同 Pod，绑定 loopback 并使用 `X-Sidecar-Token`；若拆为独立 Pod，则使用 ClusterIP、NetworkPolicy 和服务身份。NetworkPolicy 只用于 Pod 间隔离，不宣称隔离同一 Pod 内容器。
- **敏感字段**：API Key、DCS 密码和 token 加密保存；管理 API 不返回可复用密钥片段，日志和轨迹按字段脱敏。
- **业务数据**：文档、向量、对话、轨迹、时序数据及备份静态加密，并限制为当前企业部署访问。
- **上传安全**：校验文件类型、大小和内容；解析任务在受限容器中运行，设置 CPU、内存、时间和并发限制。
- **审计**：登录、模型配置、数据源配置、文档删除、索引重建、存储迁移和密码修改均记录管理员审计事件。

---

## 8. 与其他模块的接口契约

| 接口 | 提供方 | 管理后台消费点 | 冻结时间 |
|------|--------|----------------|----------|
| 客户端上传与身份字段 | service / 桌面客户端 | 文档列表中的上传人和来源客户端 | W1 |
| 文档/索引管理 API | RAG sidecar，经 service 转发 | 文档与索引页 | W2 |
| Collector 注册、配置、测试、写入与心跳 | DCS 模块，经 service 转发 | DCS 接入、接入客户端页 | W2 |
| 模型配置与热刷新 | service / Agent 内核 | 模型配置页 | W2 |
| 持久化轨迹查询 | Agent 内核 / service | 轨迹观测页 | W3 |
| 存储状态与迁移 | service / 运维层 | 私有云存储配置 | W3 |

前端先按冻结后的 OpenAPI 契约生成类型和 mock adapter，真实 API 就绪后只切换 transport，不在页面中维护另一套手写字段定义。

---

## 9. 排期

| 周 | 内容 | 产出 |
|----|------|------|
| W2 | 工程初始化、布局、登录鉴权、OpenAPI 类型和 mock | 五个页面可导航，登录与失效跳转可用 |
| W3 | 文档/索引页、异步任务组件、持久化存储联调 | 上传文档可查看、重建、重解析和删除 |
| W4-W5 | DCS 数据源、Collector 列表、测试凭证和配置版本 | OPC UA 接入闭环可用 |
| W5-W6 | 模型配置、存储状态、轨迹观测 | 默认模型热刷新、轨迹持久化可验证 |
| W7-W8 | 权限、安全、异常态、备份恢复、私有云联调 | 完成验收与部署文档 |

---

## 10. 验收标准

1. 管理员添加 OPC UA 数据源，测试由在线 Collector 执行；未测试、测试过期或测试后改动配置均无法保存。
2. 数据源保存后生成配置版本，Collector 拉取并热加载，开始上报数据与心跳；管理后台展示在线状态、延迟和当前版本。
3. 文档与索引页显示全部用户上传文档的稳定上传人和来源客户端；重新解析、重建索引和删除均有异步任务进度。
4. 应用 Pod 重建后，原始文档、索引、模型配置、会话和轨迹不丢失，仍能重新解析文档和查询历史轨迹。
5. 新增模型端点并测试通过，原子设为唯一默认后，新对话无需重启桌面客户端即可使用；API Key 不出现在浏览器、桌面端或日志中。
6. 桌面端完成一次问答后 5 秒内出现轨迹，详情包含计划、工具调用摘要、引用和 token 使用；重启服务后仍可查询。
7. 公网断开但企业私有云可达时，管理员仍可登录、上传/管理文档和查看 DCS；模型测试与对话明确提示外部模型不可达。
8. 未登录访问 `/api/admin/*` 返回 401；客户端凭证访问管理 API 返回 403；sidecar、数据库和 Collector 内部接口不能从企业普通网络直接访问。
9. 文档、向量、会话、轨迹、时序数据及备份均启用静态加密；执行一次备份恢复演练并验证数据完整性。

---

## 11. 风险

| 风险 | 应对 |
|------|------|
| 厂区 DCS 网络无法由私有云直接访问 | Collector 独立部署并主动连接私有云；连接测试也通过 Collector 执行 |
| 原始文档或数据库随 Pod 重建丢失 | 无状态应用与持久化数据分离；使用 PVC/托管服务并纳入恢复验收 |
| 大文件上传或解析造成资源峰值 | 流式上传、文件大小限制、受限解析容器、任务队列与并发控制 |
| 轨迹查询依赖临时 dsh 日志 | 内核写入持久化会话/轨迹存储，管理后台只查询持久化投影 |
| 管理后台与桌面端字段漂移 | 共同使用 OpenAPI 生成类型，以契约测试阻止不兼容发布 |
| 内网 HTTPS 证书申请周期长 | W1 启动申请；联调证书也必须由测试客户端显式信任，不允许关闭校验 |
| 管理员忘记密码 | 提供仅私有云主机可执行的 `service --reset-admin`，重置后吊销全部会话 |
