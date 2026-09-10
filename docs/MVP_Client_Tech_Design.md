# 无隅 BizBuddy MVP 客户端技术设计

> 对应产品文档：`docs/MVP_PRD.md`
> 内核选型：DeepSeek Harness（`dsh`）；桌面 UI 选型：Electron
> 部署基线：客户端运行 Agent Kernel 并保存完整会话历史；私有云承载 RAG、DCS、模型网关和历史镜像
> 状态：草案 v3（按客户端 Agent Kernel 与双端历史架构修订）

---

## 1. 设计目标与边界

按 MVP PRD 交付一个安装在员工电脑上的桌面 Agent：

- 统一对话入口，内置一个「安全环保合规专家」Agent
- Agent Kernel 随 Electron 客户端安装并在本地运行，负责会话编排、计划、工具调用和流式事件生成
- 客户端保存完整对话历史，私有云保存一份可重试、可审计的历史镜像
- 用户从桌面端上传文档，私有云完成存储、解析、切片、Embedding、索引和检索
- DCS 时序数据由管理员在私有云管理后台接入，本地 Agent 通过私有云工具 API 查询
- 模型端点与 API Key 由管理员在私有云统一配置；本地 Agent 通过私有云模型网关调用，不接触模型 API Key
- 客户端不部署 Python RAG、Embedding 模型、向量库或 DCS Collector

技术约束：

- **桌面壳**：Electron；支持 macOS 12+ 和 Windows 10/11
- **桌面 UI**：Vue 3 + TypeScript + Vite
- **Agent 内核**：DeepSeek Harness（Node.js / TypeScript），随桌面安装包分发，由 Electron Main 启动和守护
- **本地存储**：加密 SQLite，完整保存会话、消息、引用、可展示过程事件和同步状态
- **私有云 RAG**：复用 `backend/` 的 Python 文档解析、BGE Embedding、rerank 和检索能力
- **私有云数据存储**：PostgreSQL + pgvector、文档持久化存储及最近 7 天 DCS 数据
- **网络边界**：客户端只通过企业内网 HTTPS 访问私有云统一入口；不直接访问 RAG sidecar、数据库、Collector、DCS 设备或外部模型 API

---

## 2. 总体架构

```
┌────────────────────── 用户电脑：Electron 桌面客户端 ──────────────────────┐
│                                                                          │
│  Renderer（Vue 3）                                                       │
│  ├─ 新对话 / 历史 / 能力 / 数据库                                        │
│  ├─ 流式答案、引用卡和可折叠过程区                                        │
│  └─ 管理后台入口（打开企业内网 Web 控制台）                               │
│                  │ 最小化 IPC                                             │
│  Main 主进程                                                             │
│  ├─ 窗口、文件、自动更新、认证 token                                      │
│  ├─ AgentKernel 生命周期与事件转发                                        │
│  ├─ 加密 SQLite：完整会话历史 + 执行事件                                  │
│  └─ History Mirror：增量上传、重试、删除同步                              │
│                  │ 进程内调用 / Utility Process                           │
│  Agent Kernel（dsh）                                                     │
│  ├─ 安全环保专家、固定 Skills                                             │
│  ├─ Session / plan / tool orchestration                                  │
│  ├─ doc_search / ts_list / ts_query                                      │
│  └─ model provider → 私有云模型网关                                      │
└──────────────────────────┬───────────────────────────────────────────────┘
                           │ 企业内网 HTTPS（JSON / streaming / multipart）
                           ▼
┌──────────────────────── 企业私有云 ──────────────────────────────────────┐
│ service（客户端与管理端唯一入口）                                         │
│ ├─ 客户端认证、版本与就绪检查                                             │
│ ├─ 文档上传、状态与管理                                                   │
│ ├─ Agent Tool API：RAG / DCS 查询                                        │
│ ├─ Model Gateway：注入管理员配置的模型端点与 Key                          │
│ ├─ History Mirror：会话、事件与执行轨迹镜像                               │
│ └─ /api/admin/* + admin/dist                                             │
│            │                  │                    │                      │
│            ▼                  ▼                    ▼                      │
│  Python RAG sidecar    DCS 查询与 7 天缓存      外部模型 API               │
│            │                  ▲                                           │
│            ▼                  │                                           │
│  PostgreSQL + pgvector   DCS Collector（厂区网络或独立工作负载）            │
│  文档持久化存储          └─ 采集、上报、心跳                               │
└──────────────────────────────────────────────────────────────────────────┘
```

核心原则：

1. **Agent 本地运行**：会话状态和编排不依赖云端 Agent 进程。
2. **业务数据服务化**：RAG、文档处理、DCS 数据和模型密钥仍受企业私有云统一管理。
3. **历史双端保存**：本地保存完整历史并优先落盘，云端接收增量镜像；镜像失败不影响本地历史完整性。
4. **不暴露思维链**：客户端只保存和展示 Agent 产生的简短计划/过程摘要，不保存或展示模型原始 chain-of-thought。

---

## 3. 客户端模块设计

### 3.1 Electron Main 主进程

职责：

- 管理窗口、应用生命周期、单实例、主题、高分屏和自动更新
- 保存私有云 Base URL，启动时调用 `/version` 和 `/ready`
- 管理客户端认证 token；token 通过 `electron.safeStorage` 加密，不进入 Renderer 持久化存储
- 启动和守护 AgentKernel；异常退出只自动恢复一次，避免无限重启
- 通过窄 IPC 接收提问、取消、历史操作和文档操作，并转发内核流式事件
- 管理加密本地历史库，所有用户消息和 Agent 事件先在本地事务性落盘
- 执行 History Mirror：批量同步、断点续传、失败退避和删除同步
- 通过系统文件选择器读取文档并流式上传私有云，不把上传副本保存为本地 RAG 数据
- 通过默认浏览器打开管理后台，不在 Electron 内嵌管理页面

Main 不承担：

- 文档解析、切片、Embedding、rerank 或向量检索
- DCS 协议连接、数据采集或时序数据长期缓存
- 模型 API Key 保存和外部模型端点直连
- 原始模型思维链的收集或展示

### 3.2 Agent Kernel（dsh，本地）

Electron Main 通过稳定的 `AgentKernel` 适配层调用 dsh，避免 dsh breaking changes 影响 UI 和本地数据协议：

```ts
interface AgentKernel {
  start(config: KernelLaunchConfig): Promise<void>
  prompt(sessionId: string, text: string, requestId: string): AsyncIterable<BizBuddyEvent>
  abort(requestId: string): Promise<void>
  listSessions(): Promise<SessionSummary[]>
  loadSession(sessionId: string): Promise<SessionDetail>
  deleteSession(sessionId: string): Promise<void>
  shutdown(): Promise<void>
  onExit(listener: (event: KernelExitEvent) => void): () => void
}
```

| dsh 插件层 | MVP 实现 |
|------------|----------|
| Model | 调用私有云 Model Gateway；只接收流式模型输出，不获得管理员 API Key |
| Tool | `doc_search`、`ts_list`、`ts_query`；通过受认证 HTTPS 调用私有云 Tool API |
| Skill | 从安装包 `resources/agent-kernel/skills/` 加载固定安全环保技能包 |
| Session | 管理多轮上下文、计划和本轮执行状态 |
| Storage | 通过适配层写入本地加密 SQLite；本地保存完整历史 |
| Sandbox | MVP 不涉及代码执行，关闭代码执行、Shell 和任意文件写入类工具 |

`KernelLaunchConfig` 只包含本地目录、私有云地址和短期客户端凭证引用，不包含模型 API Key、RAG 内部地址或 DCS 密码。

### 3.3 Renderer（Vue 3）

- 页面范围：新对话、历史、能力、数据库，以及管理员可见的管理后台入口
- 通过 preload 暴露的最小 IPC 使用 AgentKernel，不获得 Node 能力、认证 token 或任意文件路径
- 渲染文本增量、文档引用、DCS 数据来源、完成/失败状态和可折叠过程区
- 过程区展示结构化 `plan` 与工具状态的安全摘要，默认在本轮完成后收起
- 从本地历史库恢复完整消息、引用、DCS 数据来源和过程事件
- 数据库页展示云端上传及处理状态：上传中 / 解析中 / 已入知识库 / 失败
- 私有云不可达时禁止问答、上传和删除，但完整本地历史仍可读取

### 3.4 本地完整历史库

本地历史是 Agent 执行和客户端展示的完整副本。采用追加事件 + 消息快照，至少包含：

```ts
type LocalSession = {
  sessionId: string
  title: string
  status: 'active' | 'completed' | 'deleted'
  version: number
  createdAt: number
  updatedAt: number
  syncStatus: 'local_only' | 'pending' | 'synced' | 'conflict'
  mirroredVersion?: number
}

type LocalMessage = {
  messageId: string
  sessionId: string
  requestId: string
  role: 'user' | 'assistant'
  text: string
  status: 'streaming' | 'completed' | 'interrupted' | 'failed'
  createdAt: number
  updatedAt: number
}

type LocalEvent = {
  eventId: string
  sessionId: string
  requestId: string
  seq: number
  type: BizBuddyEvent['type']
  payload: unknown
  createdAt: number
}
```

约束：

- `sessionId`、`messageId`、`requestId`、`eventId` 均由客户端生成且全局唯一
- 同一 `requestId` 的事件按 `seq` 单调递增；`eventId` 用于本地去重和云端幂等
- 用户消息先提交本地事务，再交给 AgentKernel，避免崩溃后丢失问题
- 流式事件先追加到事件表，再更新消息快照；异常重启后把未结束消息标记为 `interrupted`
- 删除会话写入 tombstone，不立即丢弃同步信息；云端确认后再按保留策略物理清理
- 本地数据库使用 SQLCipher 或等价方案加密，数据密钥随机生成并由 `safeStorage` 保护

### 3.5 客户端事件协议

所有事件必须包含 `eventId`、`requestId`、`sessionId` 和请求内单调递增的 `seq`。MVP 支持：

| 事件 | 用途 | 是否进入完整历史 |
|------|------|------------------|
| `plan` | 可展示的计划步骤及状态，不包含原始思维链 | 是 |
| `tool_start` | 工具开始的安全摘要 | 是 |
| `tool_end` | 工具完成/失败及安全摘要 | 是 |
| `text_delta` | 助手正文增量 | 是 |
| `citation` | 文档引用卡 | 是 |
| `data_reference` | DCS 指标、时间范围、数据源、单位及聚合说明 | 是 |
| `done` | 本轮完成及 token/耗时摘要 | 是 |
| `error` | 本轮失败、中断及可重试信息 | 是 |

`plan` 使用结构化步骤，不允许将模型原始推理文本直接透传：

```ts
type PlanEvent = {
  type: 'plan'
  eventId: string
  requestId: string
  sessionId: string
  seq: number
  steps: Array<{
    stepId: string
    message: string
    status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped'
  }>
}
```

同一 `stepId` 可被后续 `plan` 事件更新。重新打开历史会话时，Renderer 从本地事件重建过程区；云端镜像也保存相同的安全过程事件，供管理员查看轨迹。

---

## 4. 私有云接口与模块

### 4.1 私有云 service

service 是客户端和管理后台的唯一网络入口：

- 校验客户端和管理员身份，隔离 `/api/client/*` 与 `/api/admin/*`
- 接收文档并提交 RAG 异步处理任务
- 为本地 Agent 提供稳定的 RAG、DCS 工具接口
- 通过 Model Gateway 读取管理员配置并调用外部 OpenAI 兼容 API
- 接收本地历史和执行事件的增量镜像
- 对外统一错误、请求 ID、限流与审计；禁止记录 token、API Key、DCS 密码和完整文档正文

MVP 客户端最小 API：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/version` | 服务版本、最低客户端版本与协议版本 |
| GET | `/ready` | 私有云、模型、RAG、DCS 和历史镜像子状态 |
| POST | `/api/client/session` | 登录或部署凭证换取短期 token |
| GET | `/api/client/documents` | 文档列表与处理状态 |
| POST | `/api/client/documents` | multipart 流式上传文档 |
| GET | `/api/client/documents/{id}` | 文档详情、处理状态和失败原因 |
| DELETE | `/api/client/documents/{id}` | 删除文档、解析产物和向量 |
| POST | `/api/client/tools/doc-search` | RAG 检索，返回稳定引用标识 |
| POST | `/api/client/tools/ts-list` | 查询可用时序指标 |
| POST | `/api/client/tools/ts-query` | 查询时序数据与聚合摘要 |
| POST | `/api/client/model/responses` | Model Gateway 流式响应；服务端注入模型配置 |
| POST | `/api/client/history/events:batch` | 幂等上传本地历史事件与 tombstone |
| GET | `/api/client/history/sync-state` | 查询客户端已确认的同步游标/版本 |

所有资源按企业部署作用域隔离。请求携带稳定的 `clientId` 和用户身份；服务端不得仅依赖展示名称确定数据归属。

### 4.2 History Mirror

云端历史是本地完整历史的镜像，不是本地 Agent 的运行前置依赖：

- Main 按本地提交顺序批量上传 session、message、event 和 tombstone
- 服务端以 `clientId + eventId` 幂等写入，返回连续确认游标和各 session 的 `mirroredVersion`
- 网络失败时保留 `pending` 状态并指数退避；下次启动或网络恢复后继续同步
- 同一客户端重试不得产生重复消息、重复引用或重复轨迹
- MVP 默认一个用户在一个客户端产生会话；若检测到同一 session 的不同分支，标记 `conflict`，不静默覆盖
- 本地删除先写 tombstone，镜像成功后云端按审计和保留策略处理；云端管理操作不得在客户端离线时无提示地覆盖本地完整历史
- 云端管理后台从镜像读取执行记录；镜像延迟时显示“待同步”，不得把缺失事件显示为完整轨迹

### 4.3 Model Gateway

- 模型 Base URL、模型 ID 和 API Key 仅由管理员在私有云配置
- 本地 Agent 请求包含当前问题、必要会话上下文和工具结果，不包含整库文档
- service 注入模型配置后转发外部 API，并把标准化流式结果返回本地 Agent
- API Key 不下发客户端、不写入本地日志，也不出现在错误消息中
- 网关返回关联请求 ID、错误分类和可重试标记，便于本地事件落盘和管理端审计

### 4.4 Python RAG sidecar（私有云）

- 支持 PDF / Word / Excel / 图片的解析与切片
- 使用 BGE Embedding、rerank 和 pgvector 检索
- 保存文档状态、失败原因、切片数和向量数
- 支持按文档重新解析、重建索引和级联删除
- 只监听私有云内部地址，不向桌面客户端或管理后台直接暴露端口

### 4.5 DCS Collector（私有云或厂区网络）

- Collector 不随桌面客户端安装，部署在能访问工业设备且可连接私有云的受控网络
- MVP 启用 OPC UA；未实现的 Modbus/MQTT 在管理 UI 中禁用
- Collector 使用独立凭证或 mTLS 注册，拉取已启用的数据源配置
- 数据源测试由 service 路由到网络可达的在线 Collector，不建立静态客户端绑定
- 采集结果上报私有云，时序数据滚动保留 7 天
- 本地 Agent 只查询私有云时序 API，不直连 Collector 或工业设备

---

## 5. 关键流程

### 5.1 启动与恢复

1. Main 打开加密历史库，恢复会话列表，将异常退出时仍为 `streaming` 的消息标为 `interrupted`。
2. Main 启动 AgentKernel，注入本地目录、私有云地址和客户端认证能力。
3. 调用 `/version` 和 `/ready` 检查协议、RAG、DCS、模型网关和镜像状态。
4. 恢复 History Mirror，从服务端确认游标之后继续上传本地待同步事件。
5. 私有云不可达时仍可浏览完整本地历史，但不能发起依赖模型/RAG/DCS的新问答。

### 5.2 对话问答

1. Renderer 生成或沿用 `sessionId`，生成 `requestId`，通过 IPC 发送问题。
2. Main 在本地事务中写入用户消息及同步队列，然后调用 `AgentKernel.prompt`。
3. Agent 产生安全的 `plan` 事件，并按需调用私有云 `doc_search`、`ts_list`、`ts_query`。
4. Agent 通过 Model Gateway 获取流式模型输出，生成正文、引用和 DCS 数据来源事件。
5. Main 按顺序持久化每个事件，再转发 Renderer；Renderer 不作为历史事实来源。
6. `done` 或 `error` 结束本轮并更新消息快照；History Mirror 异步上传新增记录。

### 5.3 历史打开与继续对话

1. 历史列表和详情优先读取本地完整历史库，不以私有云可达为前提。
2. `loadSession` 返回消息、引用、DCS 数据来源、过程事件和每轮最终状态。
3. 用户继续提问时沿用 `sessionId`，AgentKernel 从本地历史恢复上下文。
4. 镜像落后不阻塞继续提问；新事件保持本地顺序并在网络恢复后统一同步。

### 5.4 文档上传与索引

1. 用户在数据库页选择文件，Renderer 只获得展示所需元数据。
2. Main 将文件流式上传 `/api/client/documents`，UI 显示上传进度。
3. 私有云持久化文件，RAG sidecar 异步解析、切片、Embedding 和写入 pgvector。
4. 客户端查询文档处理状态，直到已入知识库或失败。
5. 删除文档由私有云级联删除原文件、解析产物、切片和向量，并写管理员审计日志。

### 5.5 网络异常

- **仅外部模型不可达**：文档上传、处理和管理可用；新问答失败并记录明确的本地 `error` 事件。
- **私有云不可达**：本地历史完整可读；问答、上传、删除、RAG 和 DCS 查询不可用；镜像事件保持 `pending`。
- **镜像接口异常**：不影响当前问答和本地落盘；后台退避重试并在 UI 显示同步状态。
- **模型流中断**：保留已收到的事件，将消息标为 `interrupted` 或 `failed`，不得标记为完整答案。
- **AgentKernel 异常退出**：Main 只自动恢复一次；未结束请求本地标为 `interrupted`，恢复后允许用户重试。

---

## 6. 目录与部署形态

```
桌面安装包（electron-builder）
├── app/                              # Electron Main / preload / Renderer
├── resources/agent-kernel/           # dsh、适配层、cordis.yml
│   └── skills/                       # 固定安全环保技能包
├── assets/                           # 静态资源
└── update/                           # 自动更新配置

桌面应用数据目录
├── connection.json                   # 私有云地址等非敏感配置
├── credentials.enc                   # safeStorage 保护的客户端凭证
├── history.db.enc                    # 完整会话、消息、引用、事件、同步队列
└── workspace/                        # AgentKernel 工作目录；不包含 RAG 数据

企业私有云部署
├── service/                          # 客户端与管理端统一入口
├── model-gateway/                    # 管理员模型配置和外部模型代理
├── history-mirror/                   # 历史/事件镜像和管理端轨迹读取
├── rag-sidecar/                      # Python 文档处理与 RAG
├── admin/dist/                       # 管理后台 SPA
├── collector/                        # 独立部署或部署于厂区网络
├── PostgreSQL + pgvector
└── documents/                        # PVC 或企业对象/文件存储
```

桌面安装包包含 Node AgentKernel，但不包含 Python、Embedding 模型、向量库、RAG sidecar 或 DCS 协议依赖。

---

## 7. 安全与数据保护

- 客户端、管理后台与私有云 API 全部使用 HTTPS；生产环境禁止跳过证书校验
- 本地完整历史必须加密；数据库密钥由操作系统安全存储保护
- 客户端 token 使用 `safeStorage`；模型 API Key 和 DCS 密码只在私有云加密保存
- Model Gateway 只接收当前回答必需的问题、会话上下文和检索结果，不接收整库文档
- `plan` 和过程事件只包含面向用户的步骤摘要，不保存或同步模型原始 chain-of-thought
- Tool 事件默认不持久化密码、token、完整文档正文或未经裁剪的 DCS 配置
- Renderer 启用 `contextIsolation`、关闭 `nodeIntegration`，只使用白名单 preload API
- 文档上传需校验类型、大小和内容；私有云隔离解析任务并限制资源
- 本地历史删除、云端镜像删除和文档删除都必须有明确的审计与保留策略

---

## 8. 风险与建议

### 8.1 本地 AgentKernel 稳定性

- dsh 仍可能有 breaking changes，必须锁定版本并维护 `AgentKernel` 适配接口
- W1 spike 验证 Electron 集成、进程退出、流式事件、取消和本地会话恢复
- Windows x64、macOS arm64 和 macOS x64 分别验证 dsh 运行文件与打包路径

### 8.2 历史双写一致性

- 本地落盘是提问成功接收的前置条件，云端镜像不得进入本轮回答的阻塞路径
- 必须通过稳定 ID、版本、游标、幂等和 tombstone 避免重复或复活已删除会话
- MVP 明确单客户端优先；多客户端同一会话只检测冲突，不做自动合并
- 管理端必须展示镜像新鲜度，避免把尚未同步的执行记录误判为缺失

### 8.3 私有云依赖

- 本地 Agent 仍依赖私有云的模型网关、RAG 和 DCS；离线能力只覆盖完整历史浏览
- 文档必须流式上传并支持服务端大小限制、失败重试和幂等
- 私有云需要 HTTPS 证书、持久化卷、数据库备份和历史镜像恢复方案

### 8.4 工业网络接入

- Collector 应部署在厂区受控网络并主动连接私有云
- Collector 注册、配置拉取、数据写入和心跳协议必须在联调前冻结
- 配置热加载失败时保留上一可用版本，不能中断现有采集

---

## 9. 里程碑建议（对齐 2~3 个月 MVP）

| 阶段 | 周 | 内容 |
|------|----|------|
| M0 架构与契约 | W1 | 验证 dsh 本地集成；冻结 AgentKernel、事件、工具、模型网关和 History Mirror 协议 |
| M1 本地 Agent 主链路 | W2-W4 | Electron、AgentKernel、加密历史库、`plan`/工具/正文/引用事件和历史恢复 |
| M2 私有云能力 | W3-W7 | 文档上传与 RAG、模型网关、DCS Tool API、History Mirror 和基础管理端轨迹 |
| M3 联调与数据接入 | W7-W9 | 联合检索、OPC UA Collector、DCS 数据来源、同步异常和删除流程 |
| M4 桌面交付 | W9-W11 | 双平台打包、签名、公证、自动更新、安全与网络异常测试 |
| M5 试用 | W12 | ≥3 个安环场景验证、性能基线、镜像恢复演练和问题修复 |
