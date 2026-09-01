# 无隅 BizBuddy MVP 客户端技术设计

> 对应产品文档：`docs/MVP_PRD.md`
> 内核选型：DeepSeek Harness（`dsh`）；UI 选型：Electron
> 状态：草案 v1（含选型建议与风险说明）

---

## 1. 设计目标

按 MVP PRD 交付一个跑在用户本地电脑的桌面应用：

- 统一对话入口，内置一个「安全环保合规专家」Agent
- 本地文档 → RAG 知识库，对话自动检索
- DCS 时序数据由管理员在管理后台接入，对话自动查询
- 模型推理走云端 OpenAI 兼容 API（管理员配置）
- 本地保存文档、向量索引、对话历史、执行轨迹

技术约束：

- **Agent 内核**：DeepSeek Harness（Node.js / TypeScript，Cordis 插件内核，MIT，[GitHub](https://github.com/deepseek-ai/deepseek-harness)）
- **UI 壳**：Electron
- **复用现有资产**：`backend/`（Python FastAPI：文档解析、BGE Embedding、rerank、RAG 检索）、`frontend/`（Vue3）、`skills/`（SKILL.md 技能包）

---

## 2. 总体架构

```
┌──────────────────────────── 桌面应用（Electron 安装包）────────────────────────────┐
│                                                                                  │
│  ┌─────────────────────┐                                                         │
│  │ Renderer（UI）       │  Vue3（复用 frontend/ 改造）                             │
│  │ 对话 / 能力 / 数据库  │                                                         │
│  │ 管理后台 / 模型配置   │                                                         │
│  │ 轨迹观测             │                                                         │
│  └─────────┬───────────┘                                                         │
│            │ IPC                                                                 │
│  ┌─────────▼───────────┐                                                         │
│  │ Main 主进程          │  窗口/生命周期/自动更新/密钥保管(safeStorage)/进程编排     │
│  └─────────┬───────────┘                                                         │
│            │ 进程内调用                                                            │
│  ┌─────────▼───────────────────────────────────────────────┐                     │
│  │ Agent 内核（Utility Process，Node）                        │                     │
│  │ DeepSeek Harness（dsh）                                   │                     │
│  │ ├─ Model 插件      → 云端 OpenAI 兼容 API（HTTPS）         │──────► 云端 LLM     │
│  │ ├─ Tool 插件       → doc_search / ts_query / ts_list     │                     │
│  │ ├─ Skill 插件      → skills/ 目录 SKILL.md 技能包          │                     │
│  │ ├─ Session 插件    → 追加式会话日志（轨迹观测数据源）         │                     │
│  │ └─ Storage 插件    → 本地 SQLite                          │                     │
│  └─────────┬───────────────────────────────────────────────┘                     │
│            │ HTTP 127.0.0.1（仅 loopback）                                         │
│  ┌─────────▼───────────┐   ┌─────────────────────────────┐                       │
│  │ Python Sidecar       │   │ DCS Collector（独立进程）     │                       │
│  │ （复用 backend/）     │   │ asyncua / pymodbus / mqtt   │                       │
│  │ 文档解析/切片/Embedding│◄──│ 按数据源配置采集点位           │                       │
│  │ RAG 检索/rerank      │   │ 心跳上报 + 数据写入           │                       │
│  │ 管理后台 API          │   └────────────┬────────────────┘                       │
│  └─────────┬───────────┘                │                                        │
│  ┌─────────▼────────────────────────────▼───────────────┐                        │
│  │ 本地数据目录（用户目录下，如 ~/Library/Application Support）│                        │
│  │ SQLite（元数据/会话/配置） · 向量库（LanceDB）· 文档文件   │                        │
│  │ 时序数据（SQLite/Parquet，保留 7 天）· 会话日志            │                        │
│  └──────────────────────────────────────────────────────┘                        │
└──────────────────────────────────────────────────────────────────────────────────┘
```

**核心思路**：dsh 是 Node 技术栈，与 Electron 主进程天然同构，作为 utility process 嵌入；现有 Python 后端不重写，以 sidecar 形式保留文档/RAG 能力；DCS 采集独立成进程，与 PRD 中「采集客户端心跳上报」的模型一致。

---

## 3. 模块设计

### 3.1 Electron Main 主进程

职责：

- 窗口管理、应用生命周期、单实例锁
- 启动/守护子进程：内核（utility process）、Python sidecar、DCS collector；崩溃自动重启
- API Key 保管：用 `electron.safeStorage`（底层走 macOS Keychain / Windows DPAPI）加密后落盘，不进入渲染进程
- 自动更新：`electron-updater`（Squirrel / NSIS）
- 管理员能力门禁：MVP 单用户本地应用，「管理员」为应用内角色标记；渲染进程请求管理后台 API 时由主进程附带凭证

### 3.2 Agent 内核（dsh 集成）

dsh「一切皆插件」，我们只做插件开发和配置，不改框架源码：

| dsh 插件层 | 我们的实现 |
|------------|-----------|
| Model | OpenAI 兼容 provider，读取管理员的模型配置（Base URL / 模型名 / Key），支持运行时切换默认模型 |
| Tool | `doc_search`（检索本地 RAG）、`ts_query`（查时序点位）、`ts_list`（列出已接入点位）；均通过 HTTP 调 sidecar |
| Skill | 启动时扫描 `skills/` 目录（含 `.zip`），把 SKILL.md 注册为 dsh skill 插件——与现有 `skill_package.py` 的加载逻辑对齐 |
| Session | 使用 dsh 原生追加式会话日志（resume / fork / replay），轨迹观测页直接读这份日志 |
| Storage | 适配到本地 SQLite，替代默认存储 |
| Sandbox | MVP 不涉及代码执行，关闭 |

专家 Agent 的定义（角色 prompt + 可用工具集 + 技能集）用 dsh 的配置/插件描述，prompt 文本继续沿用 jinja2 模板管理（与后端现有约定一致）。

### 3.3 Python Sidecar（复用 backend/）

从现有 `backend/` 裁剪，去掉 Postgres / Redis / 多用户鉴权，保留：

- 文档解析与切片（PDF / Word / Excel / 图片）
- Embedding（BGE）与 rerank
- RAG 检索（向量库从 PG/pgvector 换为嵌入式 LanceDB）
- 时序数据读写 API（`ts_query` / `ts_list` 的实际实现）
- 管理后台 API：文档与索引状态、重建索引、数据源 CRUD、客户端心跳查询

以 FastAPI 起在 `127.0.0.1` 随机端口，只监听 loopback；用 PyInstaller 打成单可执行文件随安装包分发。

> 桌面单用户场景不再需要 Postgres：元数据（documents / ts_sources / ts_tags / collector_clients / models / executions）全部落 SQLite，schema 与 PRD 7.2 保持一致，仅方言调整。

### 3.4 DCS Collector（独立进程）

- 独立于 sidecar 的原因：工业协议连接不稳定（断线、阻塞），不能让采集故障拖垮 RAG 服务；也对应 PRD 中 collector_clients 心跳模型
- 协议库：`asyncua`（OPC UA）、`pymodbus`（Modbus）、`paho-mqtt`（MQTT），MVP 先做 OPC UA 一种（PRD 允许三选一）
- 行为：读取数据源配置 → 采集点位 → 写入本地时序存储（SQLite 或 Parquet 分区，滚动保留 7 天）；每 5s 向 sidecar 上报心跳与延迟
- 数据源的新增/停用由管理后台写 SQLite，collector 监听配置变更并热加载——**客户端与数据源的关联是动态的**，不在 UI 展示静态绑定

### 3.5 Renderer（UI）

- 复用 `frontend/`（Vue3 + Vite）改造，页面结构按 `wuyu_product_mvp.html`：新对话 / 能力 / 数据库 / 管理后台（三 Tab）/ 模型配置 / 轨迹观测
- 与主进程走 IPC；对话流式输出：内核 → 主进程 → IPC event → 渲染进程逐 token 渲染
- 渲染进程不直接持有 API Key、不直接访问文件系统

---

## 4. 关键流程

### 4.1 对话问答（文档 + 时序联合）

1. 渲染进程发送问题 → 主进程 → dsh 内核（携带会话 ID）
2. dsh 会话日志记录用户消息；模型规划后调用工具：
   - `doc_search(query)` → sidecar RAG 检索，返回带引用的文档片段
   - `ts_query(tags, range)`（涉及时）→ sidecar 读本地时序存储，返回统计摘要
3. 模型生成回答（流式），引用以 `[1] [2]` 标注
4. 全过程（模型调用、工具调用、token 消耗）写入 dsh 会话日志 → 轨迹观测页查询展示

### 4.2 文档上传与索引

1. 数据库页选择文件 → 主进程复制到本地数据目录 → sidecar 异步解析/切片/Embedding/写入向量库
2. 状态轮询：解析中 → 已入知识库 / 失败（含原因）
3. 管理后台可见全量文档的索引状态（切片数/向量条数），支持重建索引、重新解析、删除（同步删向量）

### 4.3 DCS 接入

1. 管理员在管理后台添加数据源 → sidecar 写 SQLite
2. 保存前「测试连接」：sidecar 临时建连验证
3. collector 检测到新配置 → 上线采集、开始心跳 → 「接入客户端」Tab 显示在线/延迟

---

## 5. 目录与部署形态

```
安装包（electron-builder 产出）
├── app/                     # Electron main + renderer（Vue3 构建产物）
├── kernel/                  # dsh + 自研插件（构建期锁定版本）
├── sidecar/                 # PyInstaller 打包的 backend 单文件
├── collector/               # PyInstaller 打包的采集进程
└── skills/                  # 内置技能包（SKILL.md）

用户数据目录（运行时创建）
├── bizbuddy.db              # SQLite：元数据/配置/会话
├── vectors/                 # LanceDB
├── documents/               # 原始文档
├── timeseries/              # 时序数据（7 天滚动）
└── sessions/                # dsh 会话日志（轨迹观测）
```

---

## 6. 风险与建议

### 6.1 关于 deepseek-harness（重点）

- **它是 developer preview**（2026-08-13 发布），官方明确说会有 breaking changes。建议：
  1. **在内核外做一层适配**（`AgentKernel` 接口：send/stream/trace/loadSkill），dsh 只是第一个实现。将来换内核（或 dsh API 大改）时 UI 和 sidecar 不受影响
  2. **锁版本 + vendoring**：pnpm 锁定具体版本，必要时 fork 一份进仓库
  3. **立项第一周做 spike 验证三件事**：能否以库形式嵌入（而非 `dsh web` 独立服务）；自定义 tool/skill 插件的开发体验；会话日志能否支撑轨迹观测页的展示需求
- dsh 的 session 追加日志（resume/fork/replay）恰好是轨迹观测的现成数据源，这是选它的最大收益
- dsh 面向 coding agent 设计，工具调用和沙箱能力强；我们用不到沙箱，注意把默认的代码执行类工具关掉，减少攻击面

### 6.2 关于 Electron

- 选 Electron 是合理的：**内核 dsh 本身就是 Node**，同进程族集成最顺；若选 Tauri（Rust 壳）反而还要再带一个 Node sidecar 跑 dsh，得不偿失
- 代价是包体积（Electron + Node 内核 + Python sidecar，预计 300MB+）。可接受，Codex/Claude Code 类工具都在这个量级；后续可通过 sidecar 精简约束
- 注意 macOS 公证（notarization）和 Windows 签名要尽早打通，Python sidecar 的 PyInstaller 产物经常被杀软误报，预留处理时间

### 6.3 其他建议

- **不要重写 Python RAG**：BGE embedding / rerank 的模型和依赖在 Python 生态，重写为 TS 成本高收益低；sidecar 是务实选择
- **向量库用嵌入式 LanceDB 或 sqlite-vec**，不要带 PG/pgvector——桌面单用户没有服务端数据库的位置
- **模型配置只放主进程**：渲染进程永远拿不到 Key；所有云端调用由内核发起，Key 由主进程注入内核环境
- **单专家先简单做**：MVP 一个专家 = 一套 system prompt + 工具集 + 技能包，不需要路由模块；但 Agent 定义要保持「声明式配置」，V1.1 加专家和路由时只是加配置
- **SKILL.md 技能包机制保留**：现有 `skills/` 目录 + zip 扫描加载的设计与 dsh 的 skill 插件模型天然契合，直接把加载器移植为 dsh skill 插件

---

## 7. 里程碑建议（对齐 2~3 个月 MVP）

| 阶段 | 周 | 内容 |
|------|----|------|
| M0 验证 | W1 | spike：dsh 嵌入 Electron、自定义 tool/skill 插件、会话日志读取；确认可行后定版 |
| M1 主链路 | W2-W5 | Electron 壳 + 内核适配层 + 模型配置 + 对话流式问答（仅文档 RAG，sidecar 裁剪完成） |
| M2 数据接入 | W6-W8 | 文档上传/索引状态/管理后台文档 Tab；DCS collector（OPC UA）+ ts_query 工具 + 管理后台两个 Tab |
| M3 打磨 | W9-W11 | 轨迹观测页、引用展示、异常处理、打包签名、安装包 |
| M4 试用 | W12 | 内部试用（≥3 个安环场景验证）、修问题 |
