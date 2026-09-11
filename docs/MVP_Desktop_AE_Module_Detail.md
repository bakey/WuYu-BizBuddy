# MVP 模块 A/E：桌面壳与三页交互设计

员工使用三页：新对话、能力、数据库。主程序管窗口、IPC、本机凭证、接入内核、访问文档服务、安装与更新。三页不含管理后台。

本机内核与私有云内核不是同一进程。本机问答和历史只留在这台电脑。管理端走企业入口、读企业侧内核。本模块不传轨迹、不实现管理接口、不配置企业模型池。

---

## 1. 主程序与内核

主程序导入 `@wuyu/bizbuddy-agent-kernel`，不启动 B.exe，不直连 DSH。

```
页面  ←IPC→  主程序
               ├ AgentKernel → DSH → 云端模型
               │    ├ doc_search → 文档服务
               │    └ ts_list / ts_query → 采集入口
               ├ 上传 / 列表 / 删除 / 任务查询 → 文档服务（与 ragBaseUrl 同一企业入口）
               └ 凭证、窗口、更新
```

`prompt` 只处理这一问。DSH、技能、会话库、模型是进程级资源。先打开存储，有模型配置再 `start`。`start` 成功即就绪，无 `kernel_ready`。之后每问只调 `prompt`。未配模型也可看历史。

| 阶段 | 处理 |
|---|---|
| 初始化 | 订阅 IPC → `initializeStorage` → 读设置 |
| 启动问答 | 配置齐 → 订阅 `onExit` → `start` 成功 → 开放发送 |
| 生成 | 每轮一次 `prompt`；同会话串行；桌面同时只一轮生成，其他会话可看 |
| 异常退出 | `expected=false`：保留已出内容，自动 `shutdown`/`start` 一次；再失败黄条「Agent 服务不可用，请重试或重启应用」 |
| 改模型 | 生成中不可保存。须本轮结束或中断收到 `USER_ABORTED` 再 `shutdown`/`start`。不换 `dataDir` |
| 退出 | 停收请求 → `abort`，最多 5 秒 → 必要时 `shutdown` → `closeStorage`。不取消文档服务已受理的任务 |

`shutdown` 幂等。超时须结束 DSH。重启不重复注册监听器。主动关闭 `expected=true`，不自动再拉。

---

## 2. 页面 ↔ 主程序

所有 `invoke`（调用）统一返回：

```
{ "ok": true, "data": { ... } }
{ "ok": false, "error": { "code": "SESSION_BUSY", "message": "...", "retryable": false } }
```

提问被收下：`ok: true`，`data` 含 `requestId`、`sessionId`。被拒绝：`ok: false`，`error.code` 为 `APP_BUSY` / `SESSION_BUSY` / `KERNEL_NOT_READY` / `SESSION_NOT_FOUND` 等。不再另用 `accepted` 字段。

推送通道（`event`、`request-state`、`document-state`、应用状态）仍是单向推送，不是 invoke。

| 通道 | 入参 | data（成功时） |
|---|---|---|
| `bizbuddy:prompt` | `{requestId,sessionId,text}` | `{requestId,sessionId}`；立刻返回，不等模型 |
| `bizbuddy:abort` | `{requestId,sessionId}` | `{requestId,sessionId}`；无匹配请求也 `ok: true` |
| `bizbuddy:list-sessions` | — | `SessionSummary[]` |
| `bizbuddy:load-session` | `{sessionId}` | `SessionSnapshot` |
| `bizbuddy:delete-session` | `{sessionId}` | `{deleted: true}` |
| `bizbuddy:open-citation` | `{documentId,page?,chunkId?}` | `{found: true}` 或 `ok: false` |
| `bizbuddy:prepare-upload` | picker 或 drop+paths | 文件候选；取消为空数组 |
| `bizbuddy:upload-document` | `{uploadId}` | `{documentId,jobId}` |
| `bizbuddy:list-documents` | 可选分页与筛选 | 文档分页 |
| `bizbuddy:delete-document` | `{documentId}` | `{jobId,status:"DELETING"}`；删成后靠 `document-state` |
| `bizbuddy:get-settings` | — | 无密钥的设置 |
| `bizbuddy:save-settings` | 草稿 | 无密钥的已保存设置 |
| `bizbuddy:test-model` | 草稿 | 探测结果；不改已保存配置 |
| `bizbuddy:get-app-state` | — | `{storage,kernel,...}` |
| `bizbuddy:list-traces` | — | `TraceSummary[]`（员工页不调用） |
| `bizbuddy:read-trace` | `{sessionId,fromSeq?}` | `TraceEvent[]`（员工页不调用） |

| 推送 | 内容 |
|---|---|
| `bizbuddy:event` | 五种内核事件，原样 |
| `bizbuddy:request-state` | 本地过程：`aborting`；或无内核终态时的 `failed`；`abort_failed` 表示停不掉 |
| `bizbuddy:document-state` | 传输与任务进度 |
| `bizbuddy:app-state` | `storage` / `kernel` 变化 |

渲染进程不暴露 `ipcRenderer`，不提交任意路径。拖拽只接受真实文件，由主程序转路径。`uploadId` 绑定主程序句柄，窗口销毁后失效。`text` 去空白后必须非空。`requestId` 由页面生成。

`ok: true` 的提问只表示收下。本轮对员工结束，只认内核 `done`/`error`。迭代器抛错或流结束却没有 `done`/`error`：推 `request-state` 的 `failed` 并解锁，不伪造 `seq`。

中断：先推 `request-state` 的 `aborting`（正在停止）。**解锁发送、写入历史终态，以内核 `error` 且 `code=USER_ABORTED` 为准。** 不要把 `aborting` 算作本轮结束。`abort_failed` 且内核仍在跑：不能假装已停，不能并行再发。

同一 `sessionId+requestId+text` 重复提交：返回与第一次相同的成功 `data`，用快照恢复，不再调内核。

| code | 含义 |
|---|---|
| `APP_BUSY` | 桌面已有一轮生成 |
| `SESSION_BUSY` | 同一 `sessionId` 在内核未结束 |
| `KERNEL_NOT_READY` | 尚未 `start`、正在改模型、正在救一轮 |
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
  model: { baseUrl: string; model: string; apiKey: string; maxTokens?: number }
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

`initializeStorage` 不启动模型，同 `dataDir` 幂等。`start` 成功才允许提问。`prompt` 第三参必填，A 传入，B 不生成。会话库只在内核包内，主程序不直接读写 SQLite。`shutdown` 后仍可读历史，`closeStorage` 才关库。

| 配置 | 用途 |
|---|---|
| `configPath` / `workspaceDir` | DSH 配置与工作目录 |
| `dataDir` | `sessions.sqlite` |
| `skillsDir` | 安装包内固定 Skills |
| `ragBaseUrl` | 文档服务企业入口。主程序上传/列表/删除/任务查询与内核 `doc_search` **用同一地址**。空串表示未配置 |
| `collectorBaseUrl` | 采集可达地址；空串则 `DCS_UNAVAILABLE` |
| `model.*` | 注入模型环境变量 |

不用 `BIZBUDDY_MODEL_NAME`、`BIZBUDDY_DATA_DIR`、`kernel_ready`。密钥不进页面、提示词、轨迹、日志。

---

## 4. 流式事件与过程区

每条事件带 `requestId`、`sessionId`、`seq`（**该次请求内**从 1 递增）。按编号路由、按 `seq` 排序去重；引用按 `citationId` 合并。每轮恰好一个 `done` 或 `error`。

| 类型 | 必填 | 窗口 |
|---|---|---|
| `searching` | `callId`、`tool`、`message` | `tool` 仅为 `doc_search` / `ts_list` / `ts_query`。`message` 进过程区，不展示工具名 |
| `text_delta` | `text` | 按本轮 `seq` 追加 |
| `citation` | `citations[]` | 引用卡；点击只用 `documentId` |
| `done` | `reason`：`completed` / `max_tokens` | 本轮结束 |
| `error` | `code`、`message`、`retryable` | 失败或中止。`USER_ABORTED` 的 `retryable` 为 false |

过程区只收集真实 `searching`，按 `seq` 排列。生成中可展开；结束后默认收起，仍可再展开。无工具的计划只进内核轨迹，不发 `searching`，不新增事件类型。监测结论写在过程提示和正文；`citation` 不承载测点。

无正文无引用且 `completed`：提示「未检索到可用内容」。`ragBaseUrl` 为空或文档服务不可用：`RAG_UNAVAILABLE`，不用演示检索冒充答案。

---

## 5. 文档

主程序用 `ragBaseUrl` 调文档服务 HTTP，不经过内核，不直连服务进程内部地址。路径与状态以文档服务协议为准。提问检索由内核 `doc_search`，同一入口、同一知识库。

允许类型与大小以上线能力为准；空文件、类型不符当场失败。传输完成不等于已入知识库。

**上传：** 受理后拿到文档编号与任务编号，行显示解析中；轮询任务/详情，**READY** 才显示「已入知识库」。失败显示原因。重复文件合并到已有编号。断网标状态未知，重连后查原编号，不自动重传。

**删除：** `202` + 删除中 + 任务编号 = 已受理。行保留并禁止再删，轮询同一任务。成功、文档已删除或协议约定的成功空响应后去掉该行。失败保留并允许重试。任务查不到时改查文档详情，不能直接当成已删除。

对人显示：解析中、已入知识库、删除中、失败及原因。页面不展示内部任务编号和令牌。

**引用：** 按 `documentId` 拉详情并高亮，不依赖当前分页。不存在或无权限：摘录保留，提示无法定位。无内置 PDF 预览。

---

## 6. 历史

以内核会话库为准。主程序只保留展示快照和当前请求表。

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

- 每轮两条消息。助手先 `streaming`，再进入一个终态。`question` 为首次提问前 80 字，不随续问改写。
- 时间为 Unix 毫秒。列表按 `updatedAt` 降序。点「新对话」只生成编号，首问写入后才进列表。
- `list`/`load` 不依赖模型、`start`、联网。存储未开返回 `STORAGE_NOT_READY`，不得画成空列表。
- 打开：先订阅再取快照，只重放该 `requestId` 上游标之后的事件。切会话不取消正在生成的那一轮，也不得并行再开一轮。
- 续问沿用 `sessionId`、换新 `requestId`。`failed` / `aborted` / `interrupted` 的半截不作为成功上下文。
- `USER_ABORTED` → `aborted`；普通 `error` → `failed`；进程没了 → `interrupted`。重开不得停在「正在生成」。
- 有活动请求不可删该会话。删除成功后不能用旧编号续问。不撤销已上传文档，不改管理端数据。

---

## 7. 轨迹与配置

内核把步骤记到 `dataDir/sessions.sqlite`。员工三页不展示轨迹。主程序可调 `listTraces` / `readTrace` 做本机诊断，不把结果送到管理端。

`question` 为该会话首次提问摘要（与历史列表同一规则，前 80 字）。`citationCount` 为该条轨迹中引用条目个数（`citations` 数组元素合计，不是 `citation` 事件次数）。列表形状：时间、问题、状态、引用数、耗时。

```ts
type TraceSummary = {
  sessionId: string
  createdAt: number
  updatedAt: number
  question: string
  citationCount: number
  status: 'completed' | 'failed' | 'running'
  eventCount: number
  durationMs: number
  inputTokens?: number
  outputTokens?: number
  totalTokens?: number
}
```

`TraceEvent.type` 覆盖：用户输入、模型请求与输出、工具调用与结果、计划步骤、错误、本轮结束。管理端列表与详情由管理端经企业入口读取企业侧内核。本模块不上传本机轨迹、不为管理端开 HTTP。

模型只在本机引导和「模型设置」中配置，写入系统安全存储，启动时注入内核。不读取企业模型池。测连接由主程序发 HTTPS，只测草稿。生成中不能保存。换地址须重填密钥，不得把旧密钥发到新域名。保存失败保留旧配置。

技能目录固定为安装包内 `Skills`，页面不管理。改技能须 `shutdown`/`start`，并等本轮结束。

---

## 8. 三页

未配模型可进三页，仅发送不可用，可看历史；设置页可返回。数据库是否可写取决于文档服务是否可达。

| 情况 | 对话 | 数据库 |
|---|---|---|
| 未配模型，文档服务可用 | 不能发，可看历史 | 可查询、上传、删除 |
| 模型不通，文档服务可用 | 提示模型异常 | 照常 |
| 文档服务不可达 | 历史可看；检索失败用明确错误 | 禁止新的写入；已受理任务待恢复 |
| 正在生成 | 可看其他历史，不能再发，可停止本轮 | 可查询 |

欢迎区与能力示例对齐原型。能力页仅一张安全环保合规专家。单实例，再开只聚焦已有窗口。

---

## 9. 安装与更新

同一套程序。Windows 10/11 x64；macOS 12+，arm64 与 x64 分打。

| 平台 | 安装 | 更新 | 签名 |
|---|---|---|---|
| Windows x64 | NSIS `.exe` | `latest.yml` | 测试包可未签名；发行包按企业要求签名 |
| macOS arm64 / x64 | 各一份 `.dmg` | 同一签名应用打出的 zip + 对应 `latest-mac.yml` | 测试包只手装、不自动更新；发行包须签名并公证 |

未签名 Mac 包不启用自动更新。开发运行不检查更新。检查失败不挡进三页。有新版本才询问；下完后退出时安装，生成中途不装。升级保留历史和设置，失败不清库。卸载不自动删用户数据。单包 ≤ 500MB，不含文档服务运行时。

---

## 10. 目录

```
安装目录或 App 包 / resources/agent-kernel/
  DSH（与本包架构一致，保持解包）
  cordis.yml
  Skills/

用户数据（app.getPath('userData')）
  workspace/
  data/sessions.sqlite    仅内核读写
  settings/
```

Windows：`%APPDATA%\无隅 BizBuddy`。macOS：`~/Library/Application Support/无隅 BizBuddy`。密钥走系统安全存储，页面拿不到。

---

## 11. 验收

1. 未配模型可进三页，不能发送；测通后可问；回包无密钥。
2. 提问可见过程区、逐字、引用、结束；同会话未结束再发为忙；中断后可再问；半截不当成功。
3. 点引用能定位该文档；已删则提示且保留摘录。
4. 空文件、类型不符当场失败。READY 才算入库。删除受理后为删除中，成功才去掉行。
5. 历史可列出、打开、续问、删除；失败/中断重开仍正确；生成中切历史不串内容、不开第二轮。
6. 生成中不能保存模型；异常退出只自动拉起一轮。
7. 员工页无轨迹。本模块不把本机轨迹送到管理端。
8. Windows 包可装可开。Mac 测试包可手装；自动更新只验已签名发行包。升级后历史仍在。
