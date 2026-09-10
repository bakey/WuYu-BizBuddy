# MVP 模块 A/E：桌面壳与三页交互设计文档

---

## 1. 模块目标

员工在本机使用桌面应用，完成：安装打开、第一次配模型、提问与查看历史对话、看一段段出来的回答和引用、点引用找到对应文件、在数据库页上传或删除文件。已安装的应用启动时检查是否有新版本。

主程序（Electron 主进程）负责：只开一个窗口、把 API Key 加密存在本机、测模型能否连上、导入并调用 B 模块的 AgentKernel、把问答过程转给页面、读写对话历史、把员工选的文件交给文档服务、问答服务异常退出后按约定救一轮、关掉应用时结束后台、打 Windows 与 macOS 安装包并做更新检查。

本模块经手四类数据：

- **Query：** 员工的问题送到内核，答案一段段回到窗口。
- **轨迹：** 内核记下的步骤、耗时、可选 token，主程序读出来给管理端网页。
- **配置：** 引导里保存的模型地址和密钥，在启动内核时交给它。
- **Skill：** 启动时把安装包内固定技能目录告诉内核，由内核加载。

---

## 2. Electron 与 Kernel 如何一起工作

Electron 里有两层：页面和主程序。内核对外是 AgentKernel；DSH 是 B 内部的子进程。页面和主程序都不直接连 DSH，也不再单独启动一个 B.exe。

提问与上传并列：员工可以直接提问，不必先上传。配好模型后 `start` 一次（见下文「为何先 start」）；之后每问一次只走 `prompt`。同一 `sessionId` 的多轮由 B 记在会话库，员工可从历史里打开继续问。

```
页面：新对话 | 能力 | 数据库
         │ IPC
         ▼
      主程序
    ┌────┴────┐
    │         ▼
    │    上传/删除（可选）→ HTTP → C（文档服务）
    ▼
 start / prompt / abort / listSessions / loadSession / deleteSession / shutdown / onExit
    ▼
 AgentKernel
    └ DSH
         ├ 需要时 doc_search → C
         └ 需要时 ts_list / ts_query → D
              云端大模型
```

文字说明：

- 员工只点页面。页面把「提问、点引用、上传」交给主程序。
- 主程序 `import '@wuyu/bizbuddy-agent-kernel'`，在本进程内构造内核对象，只调下面第 3.2 节的方法。
- DSH 的启动、环境变量、通信、关闭由 B 负责。
- 安装包把 DSH 运行文件、`cordis.yml`、Skills 放在 `resources/agent-kernel`，可执行文件保持解包（见第 7 节）。

**为何先 `start` 一次：** `prompt` 只负责「这一问」。DSH、技能目录、会话库、模型地址是进程级资源，不能每问拉起一次。`start(config)` 做且只做这些：把 `KernelLaunchConfig` 交给 B；B 按 `configPath` 加载 DSH 配置，以 Node 模式拉起 DSH；注入模型、`skillsDir`、会话库路径、文档服务与采集地址。Promise 成功返回即就绪，可以提问。没有 `kernel_ready` 事件。之后每一问只调 `prompt`。员工改模型或密钥：先 `shutdown` 再 `start` 新配置。关掉应用：`shutdown`，由 B 关掉 DSH。

目标生命周期：

1. 已经配好模型 → 主程序调用 `start(config)`，完成上述拉起与注入。
2. `start()` 成功返回后才允许提问。
3. 主程序订阅 `onExit`。只对异常退出自动重启：`expected` 为 `false` 时，收到 `KERNEL_EXITED` 后执行一次 `shutdown` 再 `start`；再次失败则停止，页面黄条：「Agent 服务不可用，请重试或重启应用」。`expected` 为 `true`（主动 `shutdown`，例如改模型或退出应用）时不自动再拉。
4. 员工关掉应用 → 主程序调用 `shutdown`。

---

## 3. 通信接口

分两截，均见现行对接合同：

- **页面 ↔ 主程序：** IPC 名称和 JSON。
- **主程序 ↔ B：** AgentKernel 方法。主程序传入 `KernelLaunchConfig`；环境变量由 B 注入 DSH，不经过页面。

### 3.1 页面 → 主程序

员工点发送时，页面调用通道 `bizbuddy:prompt`。带上三个字段：

- `requestId`（本轮提问编号）：由页面生成（建议 UUID）。主程序原样传给 B，B 不重新生成。
- `sessionId`（会话编号）：这一段多轮对话共用。点侧栏「新对话」换新编号；点历史某一条则沿用该编号继续问。
- `text`：员工输入，去掉首尾空格后不能为空。

```
{
  "requestId": "req-001",
  "sessionId": "session-001",
  "text": "动火作业有什么要求？"
}
```

主程序立即告诉页面「这一问收没收到」，不等模型把答案想完。

收成功：

```
{
  "accepted": true,
  "requestId": "req-001",
  "sessionId": "session-001"
}
```

`accepted` 为 true 时：窗口出现问气泡，直到本轮结束（`done` 或 `error`，含中断）。

收失败：

```
{
  "accepted": false,
  "requestId": "req-001",
  "sessionId": "session-001",
  "code": "SESSION_BUSY",
  "message": "同一对话正在生成，请等待本轮结束"
}
```

`code`（原因码）还可以是 `KERNEL_NOT_READY`，包括：尚未 `start` 成功、正在改模型切换、正在救一轮。此时发送保持不可用，窗口可显示 `message`。

问答过程中，主程序用通道 `bizbuddy:event` 把每一段结果推给页面，不改字段，页面按下面 3.3 展示。

员工点引用卡时，页面调用 `bizbuddy:open-citation`：

```
{
  "documentId": "doc-fire-work-001",
  "page": 12,
  "chunkId": "chunk-1203"
}
```

- `documentId`（文档编号）：用来在数据库列表里高亮哪一行。
- `page`、`chunkId`：可以带上，本期窗口不按它们滚动。

窗口效果：切到「数据库」，对应文件那一行高亮。不打开 PDF，不打开浏览器。

本轮尚未结束时，页面可调用 `bizbuddy:abort`，带上这一问的 `requestId`、`sessionId`。主程序立刻回 `accepted: true`，再调 `abort(requestId)`。控件对齐原型。

对话历史（员工侧栏，数据在 B 的会话库）：

- `bizbuddy:list-sessions`：列出本地会话（编号、问题摘要、更新时间）。
- `bizbuddy:load-session`：打开一条，带回该 `sessionId` 下已有问答（含助手消息上的引用）。窗口画出历史气泡和引用卡后可继续 `prompt`。点卡仍只按 `documentId` 跳数据库。
- `bizbuddy:delete-session`：删一条历史。

断网时可列出、打开、浏览历史，不能新问（黄条）。主程序把上述通道转到 AgentKernel 的 `listSessions` / `loadSession` / `deleteSession`（内核设计已有；接口确认清单未改写此项，按内核设计接线）。

轨迹给管理端用，员工三页不点。通道保留：`bizbuddy:list-traces`、`bizbuddy:read-trace`。主程序再去调 AgentKernel 上对应方法。

### 3.2 主程序 → AgentKernel

包名 `@wuyu/bizbuddy-agent-kernel`，源码在团队仓 `agent-kernel/packages/agent-kernel`。主程序直接导入，不 spawn B.exe。

```ts
interface AgentKernel {
  start(config: KernelLaunchConfig): Promise<void>
  prompt(sessionId: string, text: string, requestId: string): AsyncIterable<BizBuddyEvent>
  abort(requestId: string): Promise<void>
  listSessions(): Promise<SessionSummary[]>
  loadSession(sessionId: string): Promise<SessionMessage[]>
  deleteSession(sessionId: string): Promise<void>
  listTraces(): Promise<TraceSummary[]>
  readTrace(sessionId: string, fromSeq?: number): Promise<TraceEvent[]>
  shutdown(): Promise<void>
  onExit(listener: (event: KernelExitEvent) => void): () => void
}

type SessionSummary = {
  sessionId: string
  question: string
  updatedAt: number
  messageCount: number
}

type SessionMessage = {
  role: 'user' | 'assistant'
  text: string
  requestId?: string
  createdAt: number
  citations?: Array<{
    citationId: string
    documentId: string
    documentName: string
    page?: number
    chunkId?: string
    content: string
    score?: number
  }>
}

type KernelExitEvent = {
  code: 'KERNEL_EXITED'
  message: string
  expected: boolean
}
```

| 方法 | 含义 |
|---|---|
| `start(config)` | 拉起 DSH 并注入配置（见第 2 节）。Promise 成功后才允许提问。 |
| `prompt(sessionId, text, requestId)` | 提问。第三参必填，由 A 传入页面生成的编号。B 不生成编号。同一 `sessionId` 尚未结束再问，B 拒绝；主程序映射为 `SESSION_BUSY`。同一编号的后续提问由 B 带上该会话已有上下文。 |
| `abort(requestId)` | 中断该问。进行中则停本轮并推 `error` / `USER_ABORTED`；已结束则成功返回、不推事件。不是 `shutdown`。 |
| `listSessions` / `loadSession` / `deleteSession` | 对话历史。列表含问题摘要与更新时间；打开后画出已有气泡和引用卡，可继续问。 |
| `listTraces` / `readTrace` | 读轨迹，给管理端。字段见 4.2。 |
| `shutdown` | 主动关闭 DSH。随后 `onExit` 的 `expected` 为 true。 |
| `onExit` | 生命周期通知。返回取消订阅函数。`expected: false` 时主程序只自动救一轮。 |

启动配置 `KernelLaunchConfig`（A 只传这一份对象；环境变量由 B 注入 DSH）：

| A 传入字段 | B 内部用途 |
|---|---|
| `configPath` | DSH 的 `cordis.yml` 路径 |
| `workspaceDir` | DSH 子进程工作目录 |
| `dataDir` | 生成 `${dataDir}/sessions.sqlite`，注入 `BIZBUDDY_SESSION_DB` |
| `skillsDir` | 注入 `BIZBUDDY_SKILLS_DIR` |
| `ragBaseUrl` | 注入 `BIZBUDDY_RAG_BASE_URL` |
| `collectorBaseUrl` | 注入 `BIZBUDDY_COLLECTOR_BASE_URL` |
| `model.baseUrl` | 注入 `BIZBUDDY_MODEL_BASE_URL` |
| `model.model` | 注入 `BIZBUDDY_MODEL_ID` |
| `model.apiKey` | 注入 `BIZBUDDY_MODEL_API_KEY` |
| `model.maxTokens` | 作为 DSH 初始化参数，可选 |
| `requestTimeoutMs` | B 到 DSH 的请求超时，可选 |

原协议中的 `BIZBUDDY_MODEL_NAME` 统一为 `BIZBUDDY_MODEL_ID`，`BIZBUDDY_DATA_DIR` 统一为 `BIZBUDDY_SESSION_DB`。这两项环境变量不经过页面 IPC。

加载与打包：

- 主程序：`import { … } from '@wuyu/bizbuddy-agent-kernel'`，然后 `start` / `prompt` / `abort` / `listSessions` / `loadSession` / `onExit` / `shutdown`。
- Windows 与 macOS 安装包均将 DSH 运行文件、`cordis.yml`、Skills 放到 `resources/agent-kernel`，可执行文件保持解包，且 DSH 架构与该包一致（见第 6、7 节）。
- `configPath`、`skillsDir` 指向该目录内的文件与 Skills 文件夹。

`onExit` 与 `prompt` 第三参必填已写入接口确认清单，主程序按此调用。

### 3.3 内核回到页面的事件

每段事件都带：`requestId`、`sessionId`、`seq`（该次请求内从 1 递增）。主程序原样转给页面，不改 `type`。页面按序号排序后展示。

正式合同五种类型。

**思考过程（不新增第六种事件）**

员工窗口的思考 / 计划不另开 `plan` 事件。本轮所有 `searching` 按 `seq` 收在答案上方一块「过程」区：

- 只显示 `message`（例如「正在检索相关制度」），不显示 `tool` 名。
- 生成中过程区可以开着；本轮 `done` 或 `error` 后默认收起，不挡正文。
- 过程不当成最终结论，不写入 `text_delta`。
- B 内部若有计划步骤，译成 `searching` 的 `message` 给窗口；计划原文、工具入参出参、耗时只进轨迹详情。

交互借鉴主流 Agent 的可收起过程区；内容是智能体步骤短句，不是模型思维链全文。

**正在检索 `searching`**

`tool` 可以是 `doc_search`、`ts_list`、`ts_query`。窗口按上一小节放入过程区。

```
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

**文字增量 `text_delta`**

同一问的多条 `text` 按 `seq` 拼成完整答案。窗口上就是答案一段段变长。

```
{
  "type": "text_delta",
  "requestId": "req-001",
  "sessionId": "session-001",
  "seq": 2,
  "text": "动火作业前应办理动火作业票，并确认现场可燃物已清理。"
}
```

**文档引用 `citation`**

窗口出引用卡。标题用 `documentName`，摘录用 `content`。点卡只用 `documentId` 去数据库高亮。不依赖网址字段。`citation` 只用于文档，不用来承载监测点位。

```
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

**本轮结束 `done`**

`reason` 为 `completed` 或 `max_tokens`（达到长度上限，窗口可提示可能被截断）。本轮结束。若全程没有正文也没有引用，窗口提示「未检索到可用内容」。

```
{
  "type": "done",
  "requestId": "req-001",
  "sessionId": "session-001",
  "seq": 4,
  "reason": "completed"
}
```

**本轮失败 `error`**

窗口显示 `message`。半截已画出的字不当作成功答案。

```
{
  "type": "error",
  "requestId": "req-001",
  "sessionId": "session-001",
  "seq": 5,
  "code": "MODEL_REQUEST_FAILED",
  "message": "模型请求失败",
  "retryable": true
}
```

`code`：`MODEL_NOT_CONFIGURED`、`MODEL_REQUEST_FAILED`、`RAG_UNAVAILABLE`、`RAG_TIMEOUT`、`DCS_UNAVAILABLE`、`DCS_TIMEOUT`、`POINT_NOT_FOUND`、`NO_DATA`、`KERNEL_EXITED`、`USER_ABORTED`。

`retryable` 给界面参考。`USER_ABORTED` 为 `false`。`done` 或 `error` 都算本轮结束，之后同一会话可再问。半截字不当作完整成功答案。

正式运行时文档服务不可用：B 返回 `RAG_UNAVAILABLE`，不用 mock 检索结果回答。mock 只留给 B 的开发与自动测试。

后续监测点位卡：B 将使用独立事件 `timeseries_result`，不扩展 `citation`。本期窗口不消费该事件；监测结论先写在 `searching` 提示和正文里。

### 3.4 主程序 → 文档服务 C

上传、列表、删除由主程序直接调 C 的 HTTP（本机 loopback），不经过 B。

- 基址：`http://127.0.0.1:{port}/api/v1`（端口由壳拉起 C 时确定，写入本机配置）。
- 上传：`POST /documents`，`multipart/form-data`。
- 列表 / 详情 / 删除：`GET /documents`、`GET /documents/{document_id}`、`DELETE /documents/{document_id}`。
- 窗口三态对人显示：解析中、已入知识库、失败及原因。
- 空文件、不支持的类型由主程序当场失败，不送 C。

提问时的检索仍是 B 的 `doc_search`，页面不自己搜。引用里的 `documentId` 与入库编号同一套。

---

## 4. 四类数据流向

### 4.1 Query

员工点发送之后：

1. 页面生成 `requestId`，连同 `sessionId`、`text` 交给主程序（见 3.1）。
2. 主程序立刻回「收到了」或「正忙 / 内核没好」。
3. 收到了则调用 `prompt(sessionId, text, requestId)`。
4. B 把问题交给内部的 DSH；需要时 DSH 再查文档服务 C 或采集 D。
5. B 把结果译成 3.3 的五种事件，每条带回同一 `requestId`；主程序推到页面展示。

**流程 1（制度问答）：** 先在数据库把文件传到「已入知识库」，再在新对话提问。引用卡上的 `documentId` 必须是刚入库的那份。C 未就绪时提问会收到 `RAG_UNAVAILABLE`，窗口显示失败说明，不拿演示检索冒充答案。

**流程 2（制度 + 监测）：** 直接在新对话提问（如排放口二氧化硫）。内核需要时先 `ts_list` 再 `ts_query`，并可同时 `doc_search`。窗口先出现查监测一类 `searching`，再出综合分析正文。文档依据仍用第 3.3 节引用卡。监测结论写在提示和正文中。点位卡等后续 `timeseries_result` 事件下发后再做。员工不在桌面配测点。

### 4.2 轨迹

B 把用户输入、模型请求与输出、工具调用与结果、错误、本轮结束记到 SQLite（路径为 `dataDir/sessions.sqlite`）。
主程序调用 `listTraces`、`readTrace`，给管理后台网页用。员工三页不展示轨迹。

```ts
type TraceSummary = {
  sessionId: string
  createdAt: number
  updatedAt: number
  question: string
  status: 'completed' | 'failed' | 'running'
  citationCount: number
  eventCount: number
  durationMs: number
  inputTokens?: number
  outputTokens?: number
  totalTokens?: number
}

type TraceEvent = {
  sessionId: string
  requestId?: string
  seq: number
  time: number
  type: string
  callId?: string
  durationMs?: number
  usage?: {
    inputTokens?: number
    outputTokens?: number
    totalTokens?: number
  }
  data: unknown
}
```

管理端轨迹列表按 PRD 6.6 展示：时间（`createdAt`）、问题（`question`，该会话首条用户输入摘要）、状态（`status`）、引用数（`citationCount`，该条轨迹中引用条目个数，按 `citations` 数组元素合计）、耗时（`durationMs`）。

`TraceEvent.type` 至少覆盖：用户输入、模型请求、模型输出、工具调用、工具结果、错误、本轮结束。计划步骤、工具入参出参与耗时只在轨迹详情，不进员工答案区。token 三个字段为可选，取决于模型是否返回 usage。主程序原样转给管理端，不在三页上画这些字段。

### 4.3 配置

员工在引导或「模型设置」里填写。主程序用 safeStorage 加密保存。给页面的回包里没有 `apiKey`。

调用 `start(config)` 时把模型信息放在 `KernelLaunchConfig.model` 里交给 B，B 再注入 DSH。测连接由主程序自己发 HTTPS，不经过 B。

员工改了地址或密钥：

1. 暂停接收新提问（再发送则 `KERNEL_NOT_READY`）。
2. `shutdown`，再 `start` 新配置。
3. 新的 `start` 成功后恢复提问。

切换期间 `onExit` 的 `expected` 为 true，不走异常救一轮。

### 4.4 Skill

技能是给 DSH 用的说明书文件。页面不提供技能管理。
本期使用安装包内固定目录：`resources/agent-kernel` 下的 Skills。`start(config)` 把该绝对路径作为 `skillsDir` 传入。运行中重新加载清单未提供，改技能文件后需 `shutdown` 再 `start`。

---

## 5. 用户输入到界面展示

员工在「新对话」输入发送，或点欢迎区示例，或在「能力」里点示例。都走同一条提问。界面控件对齐原型。

| 顺序 | 员工看见 | 对应什么 |
|---|---|---|
| 1 | 自己的问气泡出现 | 提问已被接收 `accepted: true` |
| 2 | 答案上方「过程」区：检索/查监测等短提示；出答案后默认收起 | 本轮全部 `searching` |
| 3 | 答案一段段变长 | `text_delta` |
| 4 | 引用卡，标题是文档名 | `citation` |
| 5 | 本轮结束，可再问 | `done` |
| 失败或中止 | 说明文字；半截字不当成功；可再问 | `error`（含 `USER_ABORTED`）或一开始就 `accepted: false` |

本轮结束 = `done` 或任意 `error`（含用户中断）。中断走 `bizbuddy:abort` → `abort(requestId)` → `error` / `USER_ABORTED`。半截文字、已出引用和过程区可以留着，过程不当完整成功回答。

点引用卡：跳到数据库并高亮该 `documentId`。
点侧栏「新对话」：聊天清空，换新的 `sessionId`；此前会话留在历史列表。
点历史某一条：`load-session` 画出该段已有问答和引用卡，沿用其 `sessionId` 继续问。
结束时既没有正文也没有引用：提示「未检索到可用内容」。
文档服务不可用：`RAG_UNAVAILABLE`，提示文档服务不可用。

制度类问题走流程 1：先入库再问，引用卡应能点回该文件。
监测类问题走流程 2：同一套发送；先出查监测提示，再出正文；文档引用仍可点；监测结论写在提示和正文中。点位卡等 `timeseries_result` 下发后再加。

---

## 6. 窗口与三页

**引导：** 还没配模型时全屏这一页，没有左侧三页。填模型地址、模型名、密钥，测试连接通过才能进入三页。以后改配置点侧栏「模型设置」，密钥可以不重填。

**新对话：** 欢迎区与生成中控件对齐原型。侧栏列出对话历史（问题摘要、时间）；点一条打开继续问，点「新对话」另开一段。改模型或救一轮期间不可提问。断网可浏览历史，不能发送。

**能力：** 一张「安全环保合规专家」。点示例等于到新对话自动发送。

**数据库：** 每一行有编号、文件名、状态。状态对人显示为：解析中、已入知识库、失败及原因。空文件、不支持的类型立刻失败。文档服务未接上时，合法文件会先解析中，再显示「失败：文档服务未连接」。接上之后，主程序按 3.4 把文件交给文档服务，并询问进度。员工提问时去知识库里搜的仍是内核的 `doc_search`。

**断网：** 对话上方黄条，发不出去；仍可浏览历史对话；数据库仍可上传、删除。

**管理后台：** 按管理端设计是内网网页。桌面若提供入口，则打开浏览器。三页里没有管理导航。管理员接 DCS 在网页完成；员工提问时内核自动查询已接入点位。轨迹由管理端经主程序读 4.2 的接口。

**安装包：** 同一套主程序、同一套 IPC 与内核接法，按平台分别出包。不为 Mac 另开业务分支。实现顺序可以先打 Windows，Mac 按本节直接打，不再改目录、协议或更新形态。再开只聚焦已有窗口。

系统范围：Windows 10 / 11（64 位）；macOS 12 及以上（Apple 芯片与 Intel）。

| 平台 | 包形态 | 架构 | 员工怎么装 |
|---|---|---|---|
| Windows | NSIS 安装程序（`.exe`） | 仅 x64，一份 | 可改安装目录；桌面与开始菜单有「无隅 BizBuddy」；卸载走系统「应用和功能」 |
| macOS | 磁盘映像（`.dmg`） | **分架构各一份**：Apple 芯片（arm64）、Intel（x64）。文件名带架构，不打混合包 | 拖入「应用程序」；程序坞与启动台可打开。卸载：把应用拖进废纸篓。用户数据不随卸载自动删除 |

两端包内均含第 7 节 `resources/agent-kernel`。其中 DSH 与壳拉起的 C/D 可执行文件必须与该包架构一致（Windows x64、macOS arm64、macOS x64 各备一份），`cordis.yml` 与 Skills 文本两端共用。页面、IPC、与内核的协议两端相同。

体积目标：单包不超过 500MB（与 PRD 一致）。

**自动更新：** 只规定员工怎么碰到升级，不把发布地址写进设计。

- 谁检查：仅已安装的应用，启动时主程序在后台检查。开发启动不检查。
- 三页没有「检查更新」按钮，也没有更新专用的 IPC JSON。
- 清单：Windows 用 `latest.yml`；macOS Apple 芯片与 Intel 各用对应的 `latest-mac.yml`（或带架构后缀的清单），只升级到同一架构。传输用 HTTPS。
- 地址：由发布配置注入（可按平台、架构各一条）。未配置、无新版本、检查失败：不弹窗，照常进三页。
- 有更高版本：系统对话框提示版本号，可选稍后或下载；下完后提示将在退出时安装。不强制升级。

改发布地址只改配置，不改三页、不改与内核的协议。

**代码签名：** Windows 有公司代码签名证书时写入安装包，无证书仍可出包（系统可能提示未知发布者）。macOS 有 Apple 开发者证书时对应用与 dmg 签名并公证；无证书仍可出包，员工打开时可能需在系统设置中允许。签名有无只影响系统提示，不改变包内目录与协议。

---

## 7. 目录结构

设计落点（Windows 安装目录与 macOS `.app` 包内结构相同；DSH 等可执行文件按该包架构放置，不混放）：

```
安装目录（Windows）或 无隅 BizBuddy.app/Contents（macOS）
├── 主程序（Electron Main）
├── 页面（Vue 三页）
└── resources/agent-kernel/          ← 可执行文件保持解包，架构与本包一致
    ├── DSH 运行文件                 ← win-x64 / darwin-arm64 / darwin-x64 三选一
    ├── cordis.yml                   ← start(config).configPath
    └── Skills/                      ← start(config).skillsDir

用户数据目录（逻辑相同，路径按系统）
├── workspace/                       ← workspaceDir，DSH 工作目录
├── data/                            ← dataDir，其下 sessions.sqlite（对话历史与轨迹）
└── 模型配置（主程序 safeStorage，页面拿不到 Key）
```

用户数据路径（主程序用系统用户数据目录，不写死盘符）：

| 平台 | 目录 |
|---|---|
| Windows | `%APPDATA%\无隅 BizBuddy` |
| macOS | `~/Library/Application Support/无隅 BizBuddy` |

密钥：Windows 走 DPAPI，macOS 走钥匙串，均经 safeStorage，页面拿不到 Key。

主程序依赖 npm 包 `@wuyu/bizbuddy-agent-kernel`。
文档服务 C、采集 D 由壳按任务拆解拉起本机可执行文件（与安装包同一架构），只把 `ragBaseUrl` / `collectorBaseUrl` 传给 B。

---

## 8. 验收

1. 未配置时进入引导；测通后进入三页；页面回包中看不到密钥。
2. 提问能看到检索提示、逐字、引用卡、结束；本轮未结束时同一会话再问为 `SESSION_BUSY`；中断后收到 `USER_ABORTED`，可再问。侧栏能列出历史、打开后继续问（含引用卡）；断网可浏览历史、不能发送。
3. 点引用跳到数据库并高亮对应文档编号。
4. 空文件、不支持的类型立即失败。
5. 提问走 `prompt(sessionId, text, requestId)`，事件上的 `requestId` 与发出的相同，形状与第 3.3 节一致。
6. 上传至「已入知识库」后提问，引用指向该文档编号。C 不可用时提问得到 `RAG_UNAVAILABLE`，不是 mock 答案。
7. 管理端能通过主程序读取第 4.2 节形状的轨迹（列表含时间、问题、状态、引用数、耗时）；员工三页不展示轨迹。
8. 安装包：Windows x64 NSIS 能安装打开；macOS 按本节打 arm64、x64 两份 dmg，包内 `resources/agent-kernel` 架构与本包一致、可被 `start` 找到。无证书时允许未签名。已安装应用在已配置更新地址时可检查新版本（只升同一架构）；未配置或失败不弹窗、不打断使用。实现顺序允许先交 Windows 包，Mac 包不改本节规定。
9. 流程 1：文件至「已入知识库」后提问，引用指向该文档编号。
10. 流程 2：提问可出现查监测提示与综合正文；文档引用仍可点；点位卡等 `timeseries_result` 下发后再验。
11. 异常退出只自动 `shutdown`+`start` 一次；再失败黄条「Agent 服务不可用，请重试或重启应用」。改模型期间发不出新问题。
12. 本轮 `searching` 出现在答案上方过程区，只显示 `message`；`done` 或 `error` 后默认收起。过程不写入答案正文。
