# 无隅 BizBuddy MVP 客户端技术设计

> 对应产品文档：`docs/MVP_PRD.md`
> 内核选型：DeepSeek Harness（`dsh`）；桌面 UI 选型：Electron
> 部署基线：本地桌面客户端 + 企业私有云服务；RAG 仅部署在企业私有云
> 状态：草案 v2（按私有云 RAG 架构修订）

---

## 1. 设计目标

按 MVP PRD 交付一个安装在用户电脑上的桌面客户端，并连接企业私有云完成业务处理：

- 统一对话入口，内置一个「安全环保合规专家」Agent
- 用户从桌面端上传文档，由私有云完成解析、切片、Embedding、索引和检索
- DCS 时序数据由管理员在私有云管理后台接入，由 Agent 自动查询
- 模型配置、模型调用、对话历史和执行轨迹由私有云统一管理
- 桌面端只保存连接配置、认证凭证和必要的会话展示缓存，不部署本地 RAG

技术约束：

- **桌面壳**：Electron；支持 macOS 12+ 和 Windows 10/11
- **桌面 UI**：Vue 3 + TypeScript + Vite
- **Agent 内核**：DeepSeek Harness（Node.js / TypeScript），部署在企业私有云
- **RAG 服务**：复用 `backend/` 的 Python 文档解析、BGE Embedding、rerank 和检索能力，以私有云 sidecar 运行
- **数据存储**：PostgreSQL + pgvector 保存元数据与向量；原始文档和解析产物保存在私有云持久化文件存储；DCS 数据保留 7 天
- **网络边界**：桌面端只通过企业内网 HTTPS 访问私有云统一入口，不直接访问内核、RAG sidecar、数据库或外部模型 API

---

## 2. 总体架构

```
┌────────────────────── 用户电脑：Electron 桌面客户端 ──────────────────────┐
│                                                                          │
│  Renderer（Vue 3）                                                       │
│  ├─ 新对话 / 能力 / 数据库                                                │
│  ├─ 文档上传与处理状态                                                    │
│  └─ 管理后台入口（仅打开企业内网 Web 控制台）                              │
│                  │ IPC                                                    │
│  Main 主进程                                                             │
│  ├─ 窗口、单实例、自动更新                                                │
│  ├─ 文件选择与流式上传                                                    │
│  ├─ 私有云地址、连接状态、认证 token                                      │
│  └─ 受保护的本地展示缓存                                                  │
└──────────────────────────┬───────────────────────────────────────────────┘
                           │ 企业内网 HTTPS（JSON / SSE / multipart）
                           ▼
┌──────────────────────── 企业私有云 ──────────────────────────────────────┐
│ service（唯一对外入口）                                                   │
│ ├─ /api/client/*：客户端认证、文档、对话、历史                            │
│ ├─ /api/admin/*：管理员鉴权与管理 API                                     │
│ ├─ 托管 admin/dist SPA                                                    │
│ └─ 限流、审计、错误归一化                                                 │
│           │                         │                                     │
│           ▼                         ▼                                     │
│ Agent 内核（dsh）              Python RAG sidecar                         │
│ ├─ Model 插件                  ├─ 文档解析 / 切片                          │
│ ├─ doc_search / ts_query       ├─ Embedding / rerank                     │
│ ├─ 安全环保专家定义             └─ pgvector 检索                           │
│ └─ 会话与执行轨迹                                                        │
│           │                         │                                     │
│           └───────────┬─────────────┘                                     │
│                       ▼                                                   │
│ PostgreSQL + pgvector · 文档持久化存储 · 7 天时序数据                      │
│                       ▲                                                   │
│ DCS Collector（独立工作负载或厂区采集客户端）                              │
│ └─ 拉取配置、采集点位、上报数据与心跳                                      │
└──────────────────────────┬───────────────────────────────────────────────┘
                           │ HTTPS
                           ▼
                 外部 OpenAI 兼容模型服务
```

**核心原则**：Electron 是私有云服务的桌面交互入口，不承载 Agent、RAG 或 DCS 采集任务。文档只从桌面端上传，后续处理与检索全部在私有云；模型 API Key 永不下发到桌面端。

---

## 3. 模块设计

### 3.1 Electron Main 主进程

职责：

- 窗口管理、应用生命周期、单实例锁、深色模式和高分屏适配
- 使用 `electron-updater` 完成应用内自动更新
- 保存私有云 Base URL，启动时调用 `/ready` 和 `/version` 完成连通性与兼容性检查
- 管理客户端认证 token；token 使用 `electron.safeStorage` 加密后落盘，不进入 Renderer 持久化存储
- 通过系统文件选择器选择待上传文档，并以流式 multipart 请求上传；不把文档复制到应用数据目录
- 维护必要的会话展示缓存；若缓存包含业务内容，使用随机数据密钥加密，数据密钥由 `safeStorage` 保护
- 通过系统默认浏览器打开私有云管理后台，不在 Electron 内嵌管理后台页面

Main 主进程不承担以下职责：

- 不启动或守护 Agent、Python RAG sidecar、DCS collector
- 不保存模型 API Key
- 不执行文档解析、Embedding、向量检索或时序查询

### 3.2 Renderer（Vue 3）

- 页面范围：新对话、能力、数据库，以及管理员可见的管理后台入口
- 所有网络请求通过 preload 暴露的窄 IPC 接口发给 Main，不向 Renderer 暴露文件路径、认证 token 或 Node 能力
- 对话使用 SSE 或基于 `fetch` 的流式响应，渲染检索中、文本分片、引用、完成和错误事件
- 数据库页显示上传进度及云端处理状态：上传中 / 解析中 / 已入知识库 / 失败
- 私有云不可达、外部模型不可达或模型未配置时，显示可区分原因的状态提示
- 私有云不可达时只允许浏览已缓存历史，不提供上传、删除或问答操作

### 3.3 私有云 service

service 是桌面客户端和管理后台的唯一网络入口：

- 校验客户端与管理员身份，区分 `/api/client/*` 和 `/api/admin/*` 权限
- 为上传文档记录上传人和来源客户端，流式写入私有云文档存储，再提交异步解析任务
- 将对话请求交给 Agent 内核，并把内核事件转换为稳定的客户端流式协议
- 将文档管理请求转发给 RAG sidecar，将 DCS 管理请求转发给 collector 配置面
- 读取模型配置并安全注入 Agent 内核；API Key 由服务端密钥管理能力加密保存
- 对外返回统一错误结构和关联请求 ID，日志中禁止记录 token、API Key、DCS 密码和完整文档正文

MVP 客户端最小 API：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/ready` | 私有云服务就绪状态，包含模型/RAG/数据库子状态 |
| GET | `/version` | 服务版本与最低客户端版本 |
| POST | `/api/client/session` | 客户端登录或部署凭证换取短期 token |
| GET | `/api/client/documents` | 当前企业知识库文档列表与处理状态 |
| POST | `/api/client/documents` | multipart 流式上传文档，返回文档 ID 和初始状态 |
| GET | `/api/client/documents/{id}` | 查询上传与处理状态、失败原因 |
| DELETE | `/api/client/documents/{id}` | 删除文档、解析产物和向量 |
| POST | `/api/client/chats` | 新建会话并开始流式问答 |
| GET | `/api/client/chats` | 查询会话历史 |
| GET | `/api/client/chats/{id}` | 查询消息、引用和完成状态 |

所有资源按企业部署作用域隔离；文档记录必须包含稳定的 `uploaderId` 和 `sourceClientId`，不能仅依赖用户填写的展示名称。

### 3.4 Agent 内核（dsh，私有云）

dsh 作为 service 管理的私有云进程运行，外部通过稳定的 `AgentKernel` 适配层调用：

| dsh 插件层 | MVP 实现 |
|------------|----------|
| Model | OpenAI 兼容 provider；从服务端模型配置读取默认端点，Key 只在服务端内存中解密 |
| Tool | `doc_search`、`ts_query`、`ts_list`；仅通过私有云内部接口调用 RAG/时序服务 |
| Skill | 启动时从服务端 `skills/` 目录加载内置安全环保技能包 |
| Session | 会话、计划、工具调用、引用、耗时和 token 使用写入私有云执行日志 |
| Storage | 使用 PostgreSQL 持久化会话元数据，不在桌面端建立内核存储 |
| Sandbox | MVP 不涉及代码执行，关闭默认代码执行类工具 |

`AgentKernel` 至少提供 `send`、`stream`、`trace`、`loadSkill` 和健康检查接口，避免 dsh 版本变化影响客户端协议。

### 3.5 Python RAG sidecar（私有云）

从现有 `backend/` 复用并服务化：

- 文档解析与切片：PDF / Word / Excel / 图片
- BGE Embedding、rerank 和基于 pgvector 的向量检索
- 文档处理状态、失败原因、切片数和向量数
- 按文档重新解析、重建索引和级联删除

sidecar 与 service 部署在同一私有云 Pod 或受控服务网络，仅监听内部地址；优先使用 loopback，并通过内部 token 限制调用方。sidecar 不直接向桌面客户端或管理后台暴露端口。

数据分工：

- PostgreSQL：文档元数据、处理状态、切片元数据、向量、会话、配置和执行日志
- 私有云文件存储：上传后的原始文档、解析中间产物
- 任务执行：文档上传成功后异步处理，重复任务按文档 ID 幂等

### 3.6 DCS Collector（私有云或厂区网络）

- Collector 不随桌面客户端安装；作为独立工作负载部署在能访问工业设备且能访问私有云的受控网络
- MVP 实际启用 OPC UA；未实现的 Modbus/MQTT 在管理 UI 中禁用或明确标记不可用
- Collector 使用独立凭证或 mTLS 注册，定期拉取已测试通过且启用的数据源配置
- 数据源测试请求由 service 路由到具备对应协议且网络可达的在线 Collector 执行；测试路由不形成静态绑定
- 采集点位后通过受认证的写入接口上报私有云，并每 5 秒上报心跳和数据延迟
- 时序数据在私有云滚动保留 7 天；Agent 通过 `ts_query` / `ts_list` 查询，不直连工业设备
- 数据源新增、修改、启停后通过配置版本号热加载，失败时保留上一个可用版本并上报错误

---

## 4. 关键流程

### 4.1 启动与就绪检查

1. Main 读取私有云 Base URL 和受保护的客户端 token。
2. 调用 `/version` 校验客户端兼容性，再调用 `/ready` 获取数据库、RAG 和默认模型状态。
3. token 失效时进入登录或部署凭证兑换流程；不把认证信息交给 Renderer。
4. 根据就绪状态启用对话和上传，或在 UI 中显示私有云不可达、服务升级中、模型未配置等具体原因。

### 4.2 文档上传与索引

1. 用户在数据库页选择文件，Renderer 仅获得用于展示的文件元数据。
2. Main 将文件流式上传到 `/api/client/documents`，UI 显示上传进度。
3. service 持久化文件并创建文档记录，RAG sidecar 异步解析、切片、Embedding 和写入 pgvector。
4. 客户端按文档 ID 查询状态，直到已入知识库或失败；失败时展示服务端原因并允许重试。
5. 删除文档时，service 级联删除原始文件、解析产物、切片和向量；删除完成后不得再被检索命中。

### 4.3 对话问答（文档 + 时序联合）

1. Renderer 通过 Main 创建或继续会话，service 将请求交给 Agent 内核。
2. Agent 按问题调用 `doc_search`；涉及时序数据时再调用 `ts_list` / `ts_query`。
3. Agent 使用管理员配置的默认模型生成回答，service 以流式事件返回文本和引用。
4. 客户端持久化必要的加密展示缓存；完整会话和执行轨迹保存在私有云。
5. 管理员可在管理后台查看对应执行记录、计划、工具调用、引用和 token 使用。

### 4.4 DCS 接入

1. 管理员在私有云管理后台填写数据源配置，service 将连接测试路由到符合条件的在线 Collector。
2. 测试通过后返回与配置内容绑定且短期有效的测试凭证；保存时服务端必须校验该凭证，并生成新配置版本。
3. 符合条件的 Collector 拉取并热加载新配置；数据源与 Collector 不建立静态绑定。
4. Collector 开始采集、上报数据和心跳，管理后台显示在线状态与延迟。
5. Agent 查询私有云中的时序数据，不直接访问 Collector 或 DCS 设备。

### 4.5 网络异常

- **外部模型不可达**：私有云文档上传、处理和管理功能可用；对话不可用并显示模型连接错误。
- **私有云不可达**：客户端停止对话、上传和管理操作，只允许浏览已缓存历史并持续低频重试健康检查。
- **流式回答中断**：保留私有云会话 ID，恢复连接后查询最终状态；不得把半条回答错误标记为已完成。

---

## 5. 目录与部署形态

```
桌面安装包（electron-builder）
├── app/                     # Electron Main / preload / Vue Renderer
├── assets/                  # 静态资源
└── update/                  # 自动更新配置

桌面应用数据目录
├── connection.json          # 私有云地址等非敏感配置
├── credentials.enc          # safeStorage 保护的客户端凭证
└── cache.db.enc             # 可清理的加密会话展示缓存

企业私有云部署
├── service/                 # 客户端与管理端统一入口
├── kernel/                  # dsh + AgentKernel 适配层 + 内置技能
├── rag-sidecar/             # Python 文档处理与 RAG
├── admin/dist/              # 管理后台 SPA
├── collector/               # 独立部署或部署于厂区网络
├── PostgreSQL + pgvector
└── documents/               # PVC 或企业对象/文件存储
```

桌面安装包不包含 Python、Embedding 模型、向量库、Agent 内核或 DCS 协议依赖，以降低包体积、内存占用和杀软误报风险。

---

## 6. 安全与数据保护

- 桌面客户端、管理后台与私有云 API 全部使用 HTTPS；生产环境禁止跳过证书校验
- 客户端 token 与缓存密钥使用操作系统级安全存储；模型 API Key 和 DCS 密码只在服务端加密保存
- 文档、向量、对话、执行日志、时序数据及备份需要静态加密，并限制为企业部署作用域访问
- 外部模型只接收当前问题和生成回答所需的最小检索上下文，不上传整库文档
- 上传文件需要校验类型、大小和内容，隔离解析任务并限制 CPU、内存与执行时间
- 文档删除必须覆盖原始文件、解析产物、向量和缓存，并写入管理员审计日志
- 管理员接口与客户端接口使用不同凭证和权限；sidecar、数据库和 Collector 配置面不得从企业网络直接访问

---

## 7. 风险与建议

### 7.1 DeepSeek Harness 稳定性

- dsh 仍可能出现 breaking changes，必须锁定版本并在外层维护 `AgentKernel` 适配接口
- W1 spike 验证自定义 model/tool/skill、流式事件、会话日志和服务端并发模型
- 禁用默认代码执行与沙箱工具，减少无关攻击面

### 7.2 私有云依赖

- 桌面端核心能力依赖私有云可达，需要区分服务不可达、模型不可达和版本不兼容
- 文档可能较大，必须采用流式上传、服务端大小限制、失败重试和幂等处理，避免 Electron 内存峰值
- 私有云需提前准备 HTTPS 证书、持久化卷、数据库备份与恢复方案

### 7.3 工业网络接入

- DCS 网络通常不能被 K8s Pod 直接访问，Collector 应允许独立部署在厂区网络并主动连接私有云
- Collector 注册、配置拉取、数据写入和心跳协议必须在联调前冻结
- 数据源修改失败时不能中断现有采集，应保留上一版本并向管理后台报告错误

### 7.4 Electron

- Electron 只做 UI、文件上传和受保护缓存，不承载 Python/模型依赖，预计安装包和空闲内存明显低于本地 RAG 方案
- macOS 公证、Windows 签名和自动更新通道仍需在 W1 启动准备
- Renderer 必须启用 `contextIsolation`，关闭 `nodeIntegration`，并使用最小化 preload API

---

## 8. 里程碑建议（对齐 2~3 个月 MVP）

| 阶段 | 周 | 内容 |
|------|----|------|
| M0 架构与契约 | W1 | dsh 服务端 spike；冻结客户端认证、上传、流式对话、Collector 和管理 API 契约 |
| M1 私有云主链路 | W2-W5 | service、PostgreSQL/pgvector、文档上传与 RAG、模型配置、基础执行日志 |
| M2 对话与数据接入 | W6-W8 | Agent 联合检索、引用协议、OPC UA Collector、DCS 管理和轨迹观测 |
| M3 桌面交付 | W9-W11 | Electron 联调、异常/缓存、签名、公证、自动更新和双平台测试 |
| M4 试用 | W12 | ≥3 个安环场景验证、性能基线、备份恢复演练和问题修复 |
