# BizBuddy A/E ↔ B 对接协议 v1

与桌面施工图 `docs/MVP_Desktop_AE_Module_Detail.md` 同一套合同。页面 IPC 回包、历史方法、轨迹上报以施工图为准；本文件记录内核对外接口与流式事件。

## 总体设计

```
Vue 页面
  ↕ Electron IPC
主程序
  ↕ 本进程 import
AgentKernel
  ↕
DSH、企业模型入口、文档服务、采集
```

主程序导入 `@wuyu/bizbuddy-agent-kernel`，不启动独立 B.exe，不直连 DSH。

## 启动

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
```

A 只传配置对象。`model.baseUrl` 为企业模型入口，不是供应商地址。不传供应商 `apiKey`，不注入 `BIZBUDDY_MODEL_API_KEY`。`model.model` 可空，空则使用企业当前默认；管理员改默认后，新的 `prompt` 走新默认，不必 `shutdown`。`clientToken` 由主程序注入请求头，页面拿不到。

环境变量由 B 注入 DSH：`BIZBUDDY_MODEL_BASE_URL`、`BIZBUDDY_MODEL_ID`（可空）、`BIZBUDDY_SESSION_DB`、`BIZBUDDY_RAG_BASE_URL`、`BIZBUDDY_COLLECTOR_BASE_URL`、`BIZBUDDY_SKILLS_DIR`。不用 `BIZBUDDY_MODEL_NAME`、`BIZBUDDY_DATA_DIR`。

`ragBaseUrl` 与文档、客户端、轨迹上报为同一企业入口。`collectorBaseUrl` 可与该入口同一基址；空则测点工具返回 `DCS_UNAVAILABLE`。

`start(config)` 成功即就绪。删除 `kernel_ready`。供应商 Key 不进页面、IPC 回包、轨迹和日志。更换安装包内 Skills 仍须本轮结束后 `shutdown` / `start`。

## 内核对外接口

```ts
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

`prompt` 第三参必填，由 A 传入，B 不生成。`searching` 仅真实工具步骤，必须有 `callId` 和 `tool`（`doc_search` / `ts_list` / `ts_query`）。无工具的计划不发 `searching`。

`abort` 命中进行中的一轮后，再推 `error` 且 `code` 为 `USER_ABORTED`，`retryable` 为 false。主动 `shutdown` 时 `onExit.expected` 为 true；异常退出为 false。A 只对异常退出自动 `shutdown` 再 `start` 一次。

会话库只在 B 包内。历史类型见施工图第 6 节。本机轨迹摘要：

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

`question`、`citationCount` 不是 B 必填。主程序从本轮事件计算后，按管理端 `GET /api/admin/traces` 的字段交给企业入口。员工三页不展示轨迹。

## 页面提问

页面 `invoke("bizbuddy:prompt", { requestId, sessionId, text })`。`requestId` 与 `sessionId` 由页面生成。主程序立刻返回，不等模型：

```json
{ "ok": true, "data": { "requestId": "req-001", "sessionId": "session-001" } }
```

或

```json
{ "ok": false, "error": { "code": "SESSION_BUSY", "message": "同一对话正在生成，请等待本轮结束" } }
```

`ok: true` 只表示收下。本轮结束只认 `done` / `error`。全部 invoke 使用 `{ok,data}` / `{ok,error}`。通道与历史/文档 IPC 见施工图第 2 节。

## 流式事件

主程序原样转发 `bizbuddy:event`。每条带 `requestId`、`sessionId`、`seq`（该请求内从 1 递增）。

五种类型：`searching` / `text_delta` / `citation` / `done` / `error`。

### searching

```json
{
  "type": "searching",
  "requestId": "req-001",
  "sessionId": "session-001",
  "seq": 1,
  "callId": "tool-001",
  "tool": "doc_search",
  "message": "正在检索相关制度"
}
```

### text_delta

```json
{
  "type": "text_delta",
  "requestId": "req-001",
  "sessionId": "session-001",
  "seq": 2,
  "text": "动火作业前应办理动火作业票，并确认现场可燃物已清理。"
}
```

### citation

```json
{
  "type": "citation",
  "requestId": "req-001",
  "sessionId": "session-001",
  "seq": 3,
  "citations": [
    {
      "citationId": "citation-001",
      "documentId": "doc-fire-work-001",
      "documentName": "动火作业安全管理制度",
      "page": 12,
      "chunkId": "chunk-1203",
      "content": "动火作业前应办理动火作业票……",
      "score": 0.92
    }
  ]
}
```

点击引用只用 `documentId` 跳转数据库并高亮。不做内置 PDF 预览。

### done

```json
{
  "type": "done",
  "requestId": "req-001",
  "sessionId": "session-001",
  "seq": 4,
  "reason": "completed"
}
```

### error

`code` 含：`MODEL_REQUEST_FAILED`、`RAG_UNAVAILABLE`、`RAG_TIMEOUT`、`DCS_UNAVAILABLE`、`DCS_TIMEOUT`、`POINT_NOT_FOUND`、`NO_DATA`、`KERNEL_EXITED`、`USER_ABORTED`。

正式运行文档服务不可用时返回 `RAG_UNAVAILABLE`，不用 mock 检索冒充答案。

## 完整调用示例

员工输入：动火作业有什么要求？

页面 → 主程序：

```json
{ "requestId": "req-001", "sessionId": "session-001", "text": "动火作业有什么要求？" }
```

主程序立刻：

```json
{ "ok": true, "data": { "requestId": "req-001", "sessionId": "session-001" } }
```

随后主程序调用 `prompt("session-001", "动火作业有什么要求？", "req-001")`，事件顺序为 `searching` → `text_delta` → `citation` → `done`，字段同上。
