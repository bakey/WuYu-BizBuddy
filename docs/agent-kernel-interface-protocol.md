# BizBuddy A/E ↔ B 对接协议 v1

## 总体设计

```Plain Text
Vue Renderer
  ↕ Electron IPC
Electron Main
  ↕ 子进程 / JSON
B Agent Kernel
  ↕
DSH、模型、文档服务、DCS 服务
```

## Electron 启动 B 的协议

### Electron → B

Electron 启动 B 子进程时传入：

```Plain Text
type KernelLaunchConfig = {
  workspaceDir: string
  dataDir: string
  skillsDir: string
  ragBaseUrl: string
  collectorBaseUrl: string

  // 仅 Electron 主进程通过环境变量注入，不经过 Vue IPC
  model: {
    baseURL: string
    model: string
    apiKey: string
  }
}
```

约定的环境变量：

```Plain Text
BIZBUDDY_MODEL_BASE_URL
BIZBUDDY_MODEL_NAME
BIZBUDDY_MODEL_API_KEY
BIZBUDDY_DATA_DIR
BIZBUDDY_RAG_BASE_URL
BIZBUDDY_COLLECTOR_BASE_URL
```

### B → Electron

B 启动成功：

```Plain Text
{
  "type": "kernel_ready",
  "version": "1.0"
}
```

B 异常退出：

```Plain Text
{
  "type": "kernel_exit",
  "code": "KERNEL_EXITED",
  "message": "Agent 内核进程已退出"
}
```

约定：

- Electron 负责启动、守护、关闭 B。

- Electron 发现 B 退出后，通知 Vue，并自动重启一次。

- B 启动失败或重启失败，Vue 显示“Agent 服务不可用，请重试或重启应用”。

- API Key 不得出现在 stdout、错误对象、SQLite、Vue 状态或 IPC 回包中。

## Vue 发送问题的协议

Vue 调用 Electron：

```Plain Text
ipcRenderer.invoke("bizbuddy:prompt", {
  requestId: string
  sessionId: string
  text: string
})
```

字段约定：

```Plain Text
type PromptRequest = {
  requestId: string  // 本次提问唯一 ID，建议 UUID
  sessionId: string  // 同一段多轮对话保持不变
  text: string       // 用户输入，去掉首尾空格后不能为空
}
```

Electron 立即返回“是否接收成功”，不等待模型回答：

```Plain Text
type PromptAccepted =
  | {
      accepted: true
      requestId: string
      sessionId: string
    }
  | {
      accepted: false
      requestId: string
      sessionId: string
      code: "KERNEL_NOT_READY" | "SESSION_BUSY"
      message: string
    }
```

## B 流式返回给 Vue 的协议

Electron 收到 B 事件后，原样转发给 Vue：

```Plain Text
webContents.send("bizbuddy:event", event)
```

每个事件带：

```Plain Text
type EventBase = {
  requestId: string
  sessionId: string
  seq: number // 本次 request 内从 1 开始递增，Vue 按它排序
}
```

完整事件定义：

```Plain Text
type BizBuddyEvent =
  | SearchingEvent
  | TextDeltaEvent
  | CitationEvent
  | DoneEvent
  | ErrorEvent
```

### 正在调用工具

```Plain Text
type SearchingEvent = EventBase & {
  type: "searching"
  callId: string
  tool: "doc_search" | "ts_list" | "ts_query"
  message: string
}
```

例如：

```Plain Text
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

### 流式回答文字

```Plain Text
type TextDeltaEvent = EventBase & {
  type: "text_delta"
  text: string
}
```

例如：

```Plain Text
{
  "type": "text_delta",
  "requestId": "req-001",
  "sessionId": "session-001",
  "seq": 2,
  "text": "动火作业前应办理动火作业票，"
}
```

Vue 将同一 `requestId` 的 `text` 按 `seq` 拼接为完整答案。

### 文档引用

```Plain Text
type Citation = {
  citationId: string
  documentId: string
  documentName: string
  page?: number
  chunkId: string
  content: string
  score?: number
}

type CitationEvent = EventBase & {
  type: "citation"
  citations: Citation[]
}
```

### 本轮结束

```Plain Text
type DoneEvent = EventBase & {
  type: "done"
  reason: "completed" | "max_tokens"
}
```

### 本轮失败

```Plain Text
type ErrorEvent = EventBase & {
  type: "error"
  code:
    | "MODEL_NOT_CONFIGURED"
    | "MODEL_REQUEST_FAILED"
    | "RAG_UNAVAILABLE"
    | "RAG_TIMEOUT"
    | "DCS_UNAVAILABLE"
    | "DCS_TIMEOUT"
    | "POINT_NOT_FOUND"
    | "NO_DATA"
    | "KERNEL_EXITED"
  message: string
  retryable: boolean
}
```

## 引用点击协议

Vue 接到 `citation` 后显示引用卡片或引用标记。

用户点击引用时，Vue 直接跳转到“数据库”页，并使用 `documentId` 高亮对应文件。

```Plain Text
router.push({
  name: "database",
  query: { documentId: citation.documentId }
})
```

MVP 不做内置 PDF 预览，也不要求文档提供稳定 HTTP 地址。`page` 和 `chunkId` 保留为引用展示与后续定位预留字段，但首版跳转只依赖 `documentId`。

B 仅把引用字段返回；页面跳转和文件高亮由 A/E 负责。

## 轨迹读取协议

给“能力/数据库”管理页面使用：

```Plain Text
ipcRenderer.invoke("bizbuddy:list-traces")
ipcRenderer.invoke("bizbuddy:read-trace", {
  sessionId: string,
  fromSeq?: number
})
```

Electron 调用 B：

```Plain Text
listTraces(): Promise<TraceSummary[]>
readTrace(sessionId: string, fromSeq?: number): Promise<TraceEvent[]>
```

Vue 不直接读取 SQLite。

## 完整调用示例

用户在 Vue 输入：

> 动火作业有什么要求？
> 
> 

### 第一步：Vue → Electron

```Plain Text
{
  "requestId": "req-001",
  "sessionId": "session-001",
  "text": "动火作业有什么要求？"
}
```

Electron 返回：

```Plain Text
{
  "accepted": true,
  "requestId": "req-001",
  "sessionId": "session-001"
}
```

### 第二步：B → Vue，开始检索

```Plain Text
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

### 第三步：B → Vue，流式文字

```Plain Text
{
  "type": "text_delta",
  "requestId": "req-001",
  "sessionId": "session-001",
  "seq": 2,
  "text": "动火作业前应办理动火作业票，并确认现场可燃物已清理。"
}
```

### 第四步：B → Vue，返回引用

```Plain Text
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

### 第五步：B → Vue，完成

```Plain Text
{
  "type": "done",
  "requestId": "req-001",
  "sessionId": "session-001",
  "seq": 4,
  "reason": "completed"
}
```


