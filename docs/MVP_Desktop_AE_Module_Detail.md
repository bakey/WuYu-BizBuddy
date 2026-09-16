# MVP 模块 A/E：桌面壳与三页交互设计

员工使用三页：新对话、能力、数据库。主程序管窗口、IPC、客户端凭证、接入本机内核、访问企业入口、安装与更新。三页不含管理后台；入口只打开系统浏览器。

本机运行内核，负责流式问答和本机历史。私有云另有文档服务、采集、模型配置和管理端网页。桌面是企业入口的**用户端客户端**：认证、文档、对话与历史、轨迹上报走 `/api/client/*`（路径以企业入口为准）。供应商模型 API Key 只在私有云保存并注入云上能力，**不写入桌面、不出现在页面和日志**。

---

## 1. 主程序与内核

主程序导入 `@wuyu/bizbuddy-agent-kernel`，不启动 B.exe，不直连 DSH，不直连文档服务进程内部地址。

```
页面  ←IPC→  主程序
               ├ 客户端登记 / 凭证 → 企业入口 /api/client/*
               ├ AgentKernel → DSH → 企业模型入口（无供应商 Key）
               │    ├ doc_search → 企业入口 → 文档服务
               │    └ ts_list / ts_query → 企业入口 → 采集
               ├ 上传 / 列表 / 删除 / 任务查询 → 企业入口（同一基址）
               ├ 本轮结束后上报轨迹与会话增量 → 企业入口
               └ 本机 sessions.sqlite（界面快照与离线已有历史）
```

`prompt` 只处理这一问。先打开存储，客户端已登记且企业入口可达再 `start`。`start` 成功即就绪，无 `kernel_ready`。未完成客户端登记也可看本机已有历史，不能提问、不能新上传。

| 阶段 | 处理 |
|---|---|
| 初始化 | 订阅 IPC → `initializeStorage` → 读本机设置（企业入口、客户端凭证，无供应商 Key） |
| 启动问答 | 已登记 → 订阅 `onExit` → `start` 成功 → 开放发送 |
| 生成 | 每轮一次 `prompt`；同会话串行；桌面同时只一轮生成 |
| 本轮结束 | 写入本机历史；尽快把本轮轨迹与会话增量交给企业入口，供管理端观测 |
| 异常退出 | `expected=false`：保留已出内容，自动 `shutdown`/`start` 一次；再失败黄条「Agent 服务不可用，请重试或重启应用」 |
| 企业默认模型变更 | 不必重启桌面、不必 `shutdown`。新的 `prompt` 经企业模型入口使用当前默认 |
| 退出 | 停收请求 → `abort`，最多 5 秒 → 必要时 `shutdown` → `closeStorage`。不取消已受理的文档任务 |

`shutdown` 幂等。超时须结束 DSH。主动关闭 `expected=true`，不自动再拉。

---

## 2. 页面 ↔ 主程序

所有 `invoke` 统一返回：

```
{ "ok": true, "data": { ... } }
{ "ok": false, "error": { "code": "SESSION_BUSY", "message": "...", "retryable": false } }
```

提问收下：`ok: true`，`data` 含 `requestId`、`sessionId`。拒绝：`ok: false`。推送通道不是 invoke。

| 通道 | 入参 | data（成功时） |
|---|---|---|
| `bizbuddy:register-client` | `{enterpriseBaseUrl}` | `{clientId}`；主程序完成客户端登记，凭证只留主程序 |
| `bizbuddy:prompt` | `{requestId,sessionId,text}` | `{requestId,sessionId}`；立刻返回 |
| `bizbuddy:abort` | `{requestId,sessionId}` | `{requestId,sessionId}` |
| `bizbuddy:list-sessions` | — | `SessionSummary[]` |
| `bizbuddy:load-session` | `{sessionId}` | `SessionSnapshot` |
| `bizbuddy:delete-session` | `{sessionId}` | `{deleted: true}` |
| `bizbuddy:open-citation` | `{documentId,page?,chunkId?}` | 找到 `ok: true`，找不到 `ok: false` |
| `bizbuddy:prepare-upload` | picker 或 drop+paths | 文件候选 |
| `bizbuddy:upload-document` | `{uploadId}` | `{documentId,jobId}` |
| `bizbuddy:list-documents` | 可选分页与筛选 | 文档分页 |
| `bizbuddy:delete-document` | `{documentId}` | `{jobId,status:"DELETING"}` |
| `bizbuddy:get-settings` | — | 企业入口等，无供应商 Key、无客户端密钥 |
| `bizbuddy:save-settings` | 草稿 | 同上 |
| `bizbuddy:test-connection` | 草稿 | 探测企业入口可达；不保存 |
| `bizbuddy:get-app-state` | — | `{storage,kernel,client}` |
| `bizbuddy:list-traces` / `read-trace` | — | 本机诊断；员工页不调用 |

| 推送 | 内容 |
|---|---|
| `bizbuddy:event` | 五种内核事件原样 |
| `bizbuddy:request-state` | `aborting` / `failed` / `abort_failed` |
| `bizbuddy:document-state` | 传输与任务进度 |
| `bizbuddy:app-state` | `storage` / `kernel` / `client` 变化 |

渲染进程不暴露 `ipcRenderer`，不持有供应商 Key 或客户端凭证。`requestId`、`sessionId` 由页面生成；点「新对话」只换 `sessionId`，无单独创建通道。`text` 去空白后非空。

提问 `ok: true` 只表示收下。本轮结束只认内核 `done`/`error`。中断先 `aborting`，解锁认 `USER_ABORTED`。`abort_failed` 且内核仍在跑：不能并行再发。同一 `sessionId+requestId+text` 重复提交：返回首次成功 `data`，不再调内核。

| code | 含义 |
|---|---|
| `APP_BUSY` | 桌面已有一轮生成 |
| `SESSION_BUSY` | 同一 `sessionId` 在内核未结束 |
| `KERNEL_NOT_READY` | 尚未 `start`、正在救一轮、正在更换 Skills |
| `CLIENT_NOT_READY` | 未登记客户端或企业入口不可用 |
| `SESSION_NOT_FOUND` | 会话不存在或已删除 |
| `STORAGE_NOT_READY` | 存储未打开 |

---

## 3. 主程序 ↔ 内核

```ts
type KernelLaunchConfig = {
  configPath: string
  workspaceDir: string
  dataDir: string
  skillsDir: string
  ragBaseUrl: string
  collectorBaseUrl: string
  model: { baseUrl: string; model?: string; maxTokens?: number }
  clientToken: string
  requestTimeoutMs?: number
}

type ProcessStep = { seq: number; callId: string; tool: string; message: string }

type Citation = {
  citationId: string
  documentId: string
  documentName: string
  chunkId: string
  content: string
  page?: number
  score?: number
}

type TraceEvent = {
  sessionId: string
  requestId?: string
  seq: number
  time: number
  type: string
  callId?: string
  durationMs?: number
  usage?: { inputTokens?: number; outputTokens?: number; totalTokens?: number }
  data: unknown
}

interface AgentKernel {
  initializeStorage(config: { dataDir: string }): Promise<void>
  closeStorage(): Promise<void>
  start(config: KernelLaunchConfig): Promise<void>
  prompt(sessionId: string, text: string, requestId: string): AsyncIterable<BizBuddyEvent>
  abort(requestId: string): Promise<void>
  listSessions(): Promise<SessionSummary[]>
  loadSession(sessionId: string): Promise<SessionSnapshot>
  deleteSession(sessionId: string): Promise<void>
  listTraces(): Promise<TraceSummary[]>
  readTrace(sessionId: string, fromSeq?: number): Promise<TraceEvent[]>
  shutdown(): Promise<void>
  onExit(listener: (e: { code: 'KERNEL_EXITED'; message: string; expected: boolean }) => void): () => void
}
```

`model.baseUrl` 为企业模型入口，不是供应商地址。不传供应商 `apiKey`。`model.model` 可空，空则使用企业当前默认；管理员改默认后，新的 `prompt` 自动走新默认，不必 `shutdown`。`clientToken` 是客户端凭证，由主程序注入请求头，页面拿不到。

`ragBaseUrl` 与文档、客户端、轨迹上报为同一企业入口。空串表示未配置。`collectorBaseUrl` 可与该入口同一基址；空则测点工具返回 `DCS_UNAVAILABLE`。

不用 `BIZBUDDY_MODEL_NAME`、`BIZBUDDY_DATA_DIR`、`kernel_ready`。供应商 Key 不进页面、提示词、轨迹、日志、本机设置文件。

---

## 4. 流式事件与过程区

每条事件带 `requestId`、`sessionId`、`seq`（该次请求内从 1 递增）。按 `seq` 排序去重；引用按 `citationId` 合并。每轮恰好一个 `done` 或 `error`。

| 类型 | 必填 | 窗口 |
|---|---|---|
| `searching` | `callId`、`tool`、`message` | 仅 `doc_search` / `ts_list` / `ts_query`。`message` 进过程区 |
| `text_delta` | `text` | 按 `seq` 追加 |
| `citation` | `citations[]` | 点卡只用 `documentId` |
| `done` | `reason`：`completed` / `max_tokens` | 本轮结束 |
| `error` | `code`、`message`、`retryable` | `USER_ABORTED` 的 `retryable` 为 false |

```ts
type EventBase = { requestId: string; sessionId: string; seq: number }
type BizBuddyEvent =
  | (EventBase & { type: 'searching'; callId: string; tool: 'doc_search' | 'ts_list' | 'ts_query'; message: string })
  | (EventBase & { type: 'text_delta'; text: string })
  | (EventBase & { type: 'citation'; citations: Citation[] })
  | (EventBase & { type: 'done'; reason: 'completed' | 'max_tokens' })
  | (EventBase & { type: 'error'; code: string; message: string; retryable: boolean })
```

过程区只收集真实 `searching`。无工具的计划只进轨迹，不发 `searching`。监测结论写在过程提示和正文。无正文无引用且 `completed`：提示「未检索到可用内容」。文档服务不可用：`RAG_UNAVAILABLE`，不用 mock 答案。

---

## 5. 客户端与文档

主程序先向企业入口登记客户端，之后所有文档、历史同步、轨迹上报均带客户端凭证。上传人、来源客户端由入口从凭证解析，桌面不传可伪造的姓名或设备名。

文档 HTTP 走同一企业入口，不经过内核，不直连服务进程内部地址。路径与状态以文档服务及企业入口为准。检索由内核 `doc_search`，同一知识库。

与企业入口交互的时间用 UTC ISO 8601；本机内核与 IPC 仍用 Unix 毫秒，由主程序转换。

允许类型与大小以上线能力为准；空文件、类型不符当场失败。传输完成不等于已入知识库。

**上传：** 受理后显示解析中（对应文档服务 PARSING…INDEXING）；**READY** 才显示「已入知识库」。失败显示原因。重复文件合并到已有编号。断网标未知，重连后查原编号，不自动重传。

**删除：** `202` + 删除中 = 已受理。行保留并禁止再删，轮询同一任务。成功或文档已删除后去掉该行。失败可重试。任务查不到时改查文档详情，不能当成已删除。

对人显示：解析中、已入知识库、删除中、失败及原因。

**引用：** 按 `documentId` 拉详情并高亮。不存在或无权限：摘录保留，提示无法定位。无内置 PDF 预览。

---

## 6. 历史

界面与续问以本机内核会话库为准。本轮终态后，主程序把该轮会话增量交给企业入口（`/api/client` 对话与历史）。企业不可达时本机仍可看已有历史，不能新同步；恢复后补传。删除本机会话时同步删除云端对应记录；不撤销已上传文档。

```ts
type MessageStatus = 'streaming' | 'completed' | 'failed' | 'aborted' | 'interrupted'
type SessionSummary = {
  sessionId: string; question: string; createdAt: number; updatedAt: number
  messageCount: number; activeRequestId?: string
}
type SessionMessage = {
  messageId: string; requestId: string; position: number
  role: 'user' | 'assistant'; text: string; createdAt: number; updatedAt: number
  status: MessageStatus; finishReason?: 'completed' | 'max_tokens'
  error?: { code: string; message: string }; citations: Citation[]; process: ProcessStep[]
}
type SessionSnapshot = {
  session: SessionSummary; revision: number; messages: SessionMessage[]
  lastEventSeqByRequest: Record<string, number>
}
```

- 每轮两条消息。助手先 `streaming`，再进入一个终态。`question` 为首次提问前 80 字。
- 列表按 `updatedAt` 降序。点「新对话」只生成编号，首问写入后才进列表。
- `list`/`load` 本机数据不依赖模型与 `start`。存储未开返回 `STORAGE_NOT_READY`。
- 打开：先订阅再取快照。切会话不取消正在生成的那一轮，也不得并行再开一轮。
- 续问沿用 `sessionId`、换新 `requestId`。半截失败/中断不作为成功上下文。
- `USER_ABORTED` → `aborted`；普通 `error` → `failed`；进程没了 → `interrupted`。
- 有活动请求不可删该会话。

---

## 7. 轨迹与配置

本机内核把步骤记到 `dataDir/sessions.sqlite`。员工三页不展示轨迹。`listTraces` / `readTrace` 只返回本机记录，不含管理端列表多出的问题、引用数。

```ts
type TraceSummary = {
  sessionId: string
  createdAt: number
  updatedAt: number
  status: 'completed' | 'failed' | 'running'
  eventCount: number
  durationMs: number
  inputTokens?: number
  outputTokens?: number
  totalTokens?: number
}
```

本轮 `done`/`error` 后，主程序读取本轮轨迹，按管理端 `GET /api/admin/traces`、`GET /api/admin/traces/{id}` 的字段投影后交给企业入口。`id` 为本轮 `requestId`，`time` 为 UTC ISO 8601。目标：结束后 5 秒内这两个 GET 可返回该问。路径以企业入口为准；入口如何保存由入口定。网络失败入队重试，不挡下一问。不上报供应商 Key、DCS 凭证、完整文档正文。

```ts
type TraceReport = {
  id: string
  time: string
  question: string
  status: 'completed' | 'failed'
  citationCount: number
  durationMs: number
  plan: unknown[]
  toolCalls: { name: string; args: unknown; ok: boolean; ms: number }[]
  citations: Citation[]
  usage: { prompt?: number; completion?: number }
  answer: string
}
```

`question`：首次提问前 80 字，主程序计算。`citationCount`：`citations` 元素合计，主程序计算。

本机不保存供应商模型地址与 Key。设置页只配企业入口。测连接只测入口可达。管理员在网页改默认模型后，桌面新提问无需重启、无需 `shutdown`。

技能目录固定为安装包内 `Skills`。改技能须本轮结束后 `shutdown`/`start`。

---

## 8. 三页

未登记客户端可进三页，仅发送与新上传不可用，可看本机已有历史。设置页配置企业入口并完成登记。

| 情况 | 对话 | 数据库 |
|---|---|---|
| 未登记，企业入口未配 | 不能发 | 不能新写入 |
| 已登记，企业入口可达 | 可问 | 可查询、上传、删除 |
| 企业入口不可达 | 本机历史可看；不能新问、不能新同步 | 禁止新写入；已受理任务待恢复 |
| 正在生成 | 可看其他历史，不能再发，可停止本轮 | 可查询 |

欢迎区与能力示例对齐原型。能力页仅一张安全环保合规专家。单实例。

---

## 9. 安装与更新

同一套程序。Windows 10/11 x64；macOS 12+，arm64 与 x64 分打。不含文档服务运行时。

| 平台 | 安装 | 更新 | 签名 |
|---|---|---|---|
| Windows x64 | NSIS `.exe` | `latest.yml` | 测试包可未签名；发行包按企业要求签名 |
| macOS arm64 / x64 | 各一份 `.dmg` | zip + 对应 `latest-mac.yml` | 测试包只手装；发行包须签名并公证才能自动更新 |

开发运行不检查更新。检查失败不挡进三页。生成中途不装更新。升级保留本机历史和客户端登记。卸载不自动删用户数据。单包 ≤ 500MB。

---

## 10. 目录

```
安装目录或 App 包 / resources/agent-kernel/
  DSH（与本包架构一致，保持解包）
  cordis.yml
  Skills/

用户数据（app.getPath('userData')）
  workspace/
  data/sessions.sqlite
  settings/          企业入口等，无供应商 Key
```

Windows：`%APPDATA%\无隅 BizBuddy`。macOS：`~/Library/Application Support/无隅 BizBuddy`。客户端凭证走系统安全存储，页面拿不到。

---

## 11. 验收

1. 页面与日志中无供应商 API Key。客户端凭证不出现在渲染进程。
2. 未登记可进三页，不能发送；登记且入口可达后可问。
3. 提问可见过程区、逐字、引用、结束；中断后可再问；半截不当成功。
4. 点引用能定位该文档。READY 才算入库。删除受理后为删除中，成功才去掉行。上传带客户端身份，桌面不传可伪造的上传人。
5. 历史可列出、打开、续问、删除；企业可达时终态后同步对话与历史。
6. 本轮结束后 5 秒内，管理端轨迹列表可出现该问（含问题、状态、引用数、耗时）；详情含计划、工具摘要、引用、token。上报失败不挡下一问。
7. 管理员更改默认模型后，桌面新对话无需重启即可使用。
8. 公网模型不可达但企业入口可达时，文档上传/删除仍可进行，提问给出明确错误。
9. Windows 包可装可开。Mac 测试包可手装；自动更新只验已签名发行包。
