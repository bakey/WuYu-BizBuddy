# 无隅 BizBuddy MVP 管理后台技术设计

> 上游文档：`docs/MVP_PRD.md`（6.4/6.5/6.6 节）、`docs/MVP_Task_Breakdown.md`（模块 F）、`docs/MVP_Client_Tech_Design.md`（总体架构）
> 对应原型：`wuyu_product_mvp_admin.html`
> 负责角色：4 号（D + F）；工作量 4 周（W2 动工，W8 完成）
> 状态：草案 v1

---

## 1. 目标与范围

管理后台是给企业 IT 管理员的 Web 端控制台，覆盖 PRD 中的五个管理页面：

| 页面 | 对应 PRD | 核心能力 |
|------|----------|----------|
| 文档与索引 | 6.4.1 | 全量文档管理、RAG 索引状态、重建索引/重新解析/删除 |
| DCS 接入 | 6.4.2 | 数据源 CRUD、测试连接、启停、点位配置（含批量导入） |
| 接入客户端 | 6.4.3 | 采集客户端心跳/延迟/状态（只读） |
| 模型配置 | 6.5 | OpenAI 兼容端点 CRUD、默认模型、测试连接、本地数据路径 |
| 轨迹观测 | 6.6 | 执行记录列表 + 详情展开（计划步骤/工具调用/引用/token） |

**不做**（与 PRD 对齐）：多租户、点位图表可视化、客户端远程操作、费用统计、成功率趋势、本地 LLM 配置。

---

## 2. 总体架构与部署形态

```
┌────────────────────────────────────────────────────────┐
│ 管理员浏览器                                              │
│  http://127.0.0.1:{port}/admin  （或从桌面端入口打开）      │
└───────────────────────┬────────────────────────────────┘
                        │ HTTP（仅 loopback）+ Admin Token
┌───────────────────────▼────────────────────────────────┐
│ Python Sidecar（模块 C，FastAPI）                         │
│  ├─ /api/admin/documents*      → RAG 索引管理（C）        │
│  ├─ /api/admin/ts-sources*     → 数据源配置（D 消费配置）   │
│  ├─ /api/admin/clients         → collector_clients 表    │
│  ├─ /api/admin/models*         → 模型配置（G 消费）        │
│  └─ /api/admin/traces*         → 内核会话日志投影（B 提供） │
│  静态托管：admin/dist（Vue3 SPA 构建产物）                  │
└────────────────────────────────────────────────────────┘
```

**关键决策**：

- **管理后台是本地 Web，不是云端系统**。整个产品运行在用户本机，管理后台由 sidecar 在本机 loopback 端口托管 SPA 静态文件，管理员用浏览器访问。桌面端「管理后台」入口 = 调起默认浏览器打开该地址（避免 Electron 内再嵌一套路由）。
- **技术栈与客户端一致**：Vue 3 + TypeScript + Vite，新建 `admin/` 目录，复用 `client/` 的样式变量与基础组件（表格、状态点、卡片），但不共享运行时代码——两个应用独立构建，避免桌面端发布被管理端阻塞。
- **数据不出本机**：所有管理 API 只监听 `127.0.0.1`；管理员鉴权用本地 token（见第 6 节）。

---

## 3. 前端设计

### 3.1 工程结构

```
admin/
├── package.json  / vite.config.ts / tsconfig.json
├── index.html
└── src/
    ├── main.ts / App.vue
    ├── api/                    # API 客户端层（fetch 封装 + 类型）
    │   ├── client.ts           # baseURL、token 注入、错误归一化
    │   ├── documents.ts
    │   ├── dcs.ts
    │   ├── models.ts
    │   └── traces.ts
    ├── types.ts                # AdminDocument / TsSource / CollectorClient / ModelEndpoint / Trace…
    ├── router.ts               # vue-router，5 个页面 + 登录页
    └── views/
        ├── LoginView.vue
        ├── DocsIndexView.vue   # 文档与索引
        ├── DcsSourcesView.vue  # DCS 接入（含数据源编辑弹窗）
        ├── ClientsView.vue     # 接入客户端
        ├── ModelsView.vue      # 模型配置
        └── TracesView.vue      # 轨迹观测（含详情抽屉）
```

布局与交互严格按 `wuyu_product_mvp_admin.html`：顶部通栏（品牌 + 管理员身份）、左侧分组导航（知识库 / 数据接入 / 系统）、右侧内容区。

### 3.2 关键交互

| 交互 | 设计 |
|------|------|
| 测试连接（数据源/模型） | 按钮进入 loading，调用 test API，结果显示内联成功/失败 + 错误详情；数据源表单**保存按钮在测试通过前禁用**（PRD 6.4.2 硬性要求） |
| 点位批量导入 | 编辑弹窗内支持粘贴 CSV / 上传 `.csv`（列：tag_name, display_name, unit, description），前端解析预览后随表单提交 |
| 重建索引 / 重新解析 | 点击后轮询文档状态（2s 间隔，指数退避封顶 10s），状态流转：解析中 → 完成/失败（含原因） |
| 接入客户端 | 只读表格，5s 轮询刷新；状态由「最近心跳」推导：≤30s 在线，>30s 离线 |
| 轨迹详情 | 列表行点击展开抽屉：计划步骤时间线、每次工具调用的入参/出参摘要/耗时、引用来源、token 消耗 |
| 空态/异常态 | 每个页面都有空态（如未接入数据源时引导「+ 添加数据源」）和加载失败重试 |

---

## 4. API 设计（sidecar 提供，统一前缀 `/api/admin`）

通用约定：JSON；错误统一 `{ "error": { "code": "...", "message": "..." } }`；列表支持 `?q=` 搜索与分页 `?page=&size=`（MVP 数据量小，可先全量返回）；除登录外全部需要 `Authorization: Bearer <admin-token>`。

### 4.1 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/admin/login` | 入参 `{ password }`，返回 `{ token, expiresAt }`；密码首次启动时由管理员设置（首次访问进入设置页） |

### 4.2 文档与索引（模块 C 实现）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/rag/status` | 概览：`{ total, indexed, parsing, failed }` |
| GET | `/api/admin/documents` | 全量文档列表，每项含 `id/name/uploader/sizeBytes/parseStatus/failReason/chunkCount/vectorCount/uploadedAt` |
| GET | `/api/admin/documents/{id}` | 详情（含切片预览前 N 条） |
| POST | `/api/admin/documents/{id}/reindex` | 重建索引（异步，返回 202） |
| POST | `/api/admin/documents/{id}/reparse` | 重新解析（失败文档用） |
| DELETE | `/api/admin/documents/{id}` | 删除文档并同步删向量 |

### 4.3 DCS 接入（模块 D 实现）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/ts-sources` | 数据源列表：`id/name/protocol/address/tagCount/status/enabled` |
| POST | `/api/admin/ts-sources` | 创建（含 tags 数组） |
| GET/PUT/DELETE | `/api/admin/ts-sources/{id}` | 详情 / 更新 / 删除 |
| POST | `/api/admin/ts-sources/test` | 测试连接（**不落库**，入参为表单草稿，返回 `{ ok, latencyMs, error? }`） |
| POST | `/api/admin/ts-sources/{id}/toggle` | 启用/停用 |

数据源配置结构：

```jsonc
{
  "name": "二号线环保监测",
  "protocol": "opcua",                    // opcua / modbus / mqtt（MVP 仅 opcua 实际可用）
  "connection": { "endpoint": "opc.tcp://10.20.1.15:4840", "username": "", "password": "" },
  "tags": [
    { "tagName": "line2.so2_outlet", "displayName": "二号线排放口 SO₂", "unit": "mg/m³", "description": "" }
  ]
}
```

### 4.4 接入客户端（模块 D 实现）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/clients` | `id/name/protocol/lastHeartbeatAt/latencyMs/status`（status 由心跳推导，不落库） |

### 4.5 模型配置（模块 G 实现）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/models` | 端点列表（**apiKey 永远脱敏返回** `sk-****1234`） |
| POST | `/api/admin/models` | 新增端点 |
| PUT/DELETE | `/api/admin/models/{id}` | 更新 / 删除（默认模型不可删除） |
| POST | `/api/admin/models/{id}/default` | 设为默认 |
| POST | `/api/admin/models/test` | 测试连接（支持未保存的草稿，同 4.3） |
| GET/PUT | `/api/admin/settings/storage` | 本地数据路径查看/修改 |

### 4.6 轨迹观测（模块 B 提供数据，sidecar 透传）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/traces` | 列表：`id/time/question/status/citationCount/durationMs` |
| GET | `/api/admin/traces/{id}` | 详情：`plan[]、toolCalls[]{name,args,ok,ms}、citations[]、usage{prompt,completion}、answer` |

> 数据源是内核（模块 B）的 dsh 会话日志投影。sidecar 通过内核暴露的读取接口取数后转发，管理后台不直连内核。

---

## 5. 数据模型（SQLite，与 sidecar 同库）

```sql
-- 文档（在现有 documents 表上补字段）
ALTER TABLE documents ADD COLUMN uploader TEXT;
ALTER TABLE documents ADD COLUMN parse_status TEXT DEFAULT 'pending';  -- pending/parsing/done/failed
ALTER TABLE documents ADD COLUMN fail_reason TEXT;
ALTER TABLE documents ADD COLUMN chunk_count INTEGER DEFAULT 0;
ALTER TABLE documents ADD COLUMN vector_count INTEGER DEFAULT 0;

-- 时序数据源
CREATE TABLE time_series_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    protocol TEXT NOT NULL,               -- opcua / modbus / mqtt
    connection_config TEXT NOT NULL,      -- JSON，密码字段加密存储
    enabled INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

-- 时序点位
CREATE TABLE time_series_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER REFERENCES time_series_sources(id) ON DELETE CASCADE,
    tag_name TEXT NOT NULL,
    display_name TEXT,
    unit TEXT,
    description TEXT
);

-- 采集客户端（心跳上报；与数据源动态关联，不做静态绑定）
CREATE TABLE collector_clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    protocol TEXT NOT NULL,
    last_heartbeat_at TEXT,
    latency_ms INTEGER
);

-- 模型端点
CREATE TABLE model_endpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    model_id TEXT NOT NULL,
    base_url TEXT NOT NULL,
    api_key_enc TEXT NOT NULL,            -- 主进程 safeStorage 加密后写入
    is_default INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

-- 管理员
CREATE TABLE admin_auth (
    id INTEGER PRIMARY KEY CHECK (id = 1),  -- 单行
    password_hash TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now'))
);
```

轨迹数据**不建表**，由内核会话日志实时投影（避免双写不一致）。

---

## 6. 权限与安全

- **单管理员模型**：本地应用只有一个管理员；首次访问管理后台时设置密码（bcrypt 哈希存 `admin_auth`），之后凭密码登录换 token（内存签发，24h 过期，重启 sidecar 即失效——MVP 不做持久会话）。
- **loopback only**：sidecar 只绑 `127.0.0.1`，管理后台天然不可被局域网访问。
- **敏感字段**：数据源连接密码、模型 API Key 加密落库（复用主进程 safeStorage 体系），API 返回一律脱敏；日志中禁止打印。
- **桌面端入口**：桌面应用内「管理后台」入口通过主进程生成一次性 URL token 打开浏览器，避免管理员重复登录（可选优化，W8 视排期决定）。

---

## 7. 与其他模块的接口契约

| 接口 | 提供方 | 管理后台消费点 | 冻结时间 |
|------|--------|----------------|----------|
| 文档/索引管理 API | C（sidecar） | 文档与索引页 | W2 |
| 数据源/客户端 API | D（collector 配置面） | DCS 接入、接入客户端页 | W2 |
| 模型配置 API | G | 模型配置页 | W3 |
| 轨迹投影接口 | B（内核）→ sidecar 透传 | 轨迹观测页 | W4 |

前端开发不等后端：`admin/src/api/` 先按上述契约写 mock adapter（参考 `client/src/mock/api.ts` 的模式），后端就绪后切换 baseURL 即可。

---

## 8. 排期（4 周，对齐任务拆解 W2-W8）

| 周 | 内容 | 产出 |
|----|------|------|
| W2 | 工程初始化 + 布局骨架 + 登录/鉴权 + API 客户端层（mock） | 五个空页面可导航 |
| W3 | 文档与索引页 + DCS 接入页（表单/测试连接/点位导入） | 两个核心页面对 mock 可用 |
| W4-W5 | 接入客户端 + 模型配置 + 轨迹观测页 | 全部页面对 mock 可用 |
| W6-W8 | 切真实 API 联调（C/D/G/B 陆续就绪）、异常态打磨、验收 | 交付验收 |

依赖节奏：C 的 API 预计 W3 就绪（最早联调对象），D 的配置面 W5，G W4，B 的轨迹投影 W6。**轨迹观测排最后联调**。

---

## 9. 验收标准

1. 管理员能独立完成 PRD 流程 3：添加 OPC UA 数据源 → 测试连接通过 → 保存 → 接入客户端页看到客户端在线且有心跳
2. 文档与索引页：能看到全部用户文档的解析/索引状态；对一个失败文档执行「重新解析」并看到状态流转；「重建索引」后向量条数刷新
3. 模型配置页：新增一个端点并测试通过、设为默认后，桌面端对话立即可用；API Key 全程脱敏
4. 轨迹观测页：桌面端完成一次问答后 5s 内，列表出现该记录且详情含计划/工具调用/引用/token
5. 未登录直接访问任何 `/api/admin/*` 返回 401；sidecar 端口从局域网其他机器不可达

---

## 10. 风险

| 风险 | 应对 |
|------|------|
| 管理后台与桌面端样式/交互漂移 | 复用同一套 CSS 变量与组件规范；以 `wuyu_product_mvp_admin.html` 为唯一视觉基准 |
| 轨迹投影接口晚于前端就绪 | mock adapter 先行；W4 冻结契约后 B 侧不得改字段 |
| 浏览器轮询心跳/状态造成 sidecar 压力 | 本地单用户无压力；轮询间隔已保守取值（2~5s + 退避） |
| 管理员忘记密码 | MVP 提供命令行重置（`sidecar --reset-admin`），不做找回流程 |
