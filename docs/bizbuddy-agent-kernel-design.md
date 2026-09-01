# BizBuddy B 模块 Agent 内核设计

## 模块职责

B 模块负责 BizBuddy 的 Agent 内核。桌面端提交问题后，B 模块调用大模型判断处理方式，按需查询企业文档或 DCS 数据，再把查询状态、回答文字和文档引用传回桌面端。

页面展示由 A/E 模块负责，文档入库和检索服务由 C 模块负责，DCS 数据采集与查询服务由 D 模块负责。B 模块连接这些服务，控制 Agent 的处理过程，并保证回答来自实际文档或测点数据。

主要工作包括以下几项。

- 管理 DSH 子进程
- 配置模型、安环 Persona 和 Skills
- 注册文档检索与 DCS 查询工具
- 把 DSH 事件转换成 BizBuddy 事件
- 保存会话和工具调用记录
- 向管理端提供轨迹读取接口

## DSH 复用范围

项目固定使用 DSH `0.1.1-rc.2`，通过 npm 依赖引入，DSH 源码保持原样。

DSH 提供 Agent 循环、模型调用、工具调用、流式输出、Skills 加载和 SQLite 持久化。B 模块在外层增加 BizBuddy 所需的进程管理、安环规则、业务工具、事件转换和轨迹读取。

## 整体架构

```text
Electron 主进程与 Vue 页面
  │
  │  启动  提问  读取轨迹  关闭
  ▼
BizBuddyAgentKernel
  ├─ Process Manager     管理 DSH 子进程
  ├─ JSON-RPC Client     发送请求并接收事件
  ├─ Event Mapper        转换流式事件和引用
  └─ Trace Adapter       读取会话轨迹
        │
        │ stdio JSON-RPC
        ▼
DSH Runtime
  ├─ Agent Loop
  ├─ OpenAI 兼容模型
  ├─ 安环 Persona 与 Skills
  ├─ doc_search
  ├─ ts_list
  ├─ ts_query
  └─ SQLite
        │
        ├─ C 模块文档检索接口
        └─ D 模块 DCS 数据接口
```

DSH 运行在独立 Node 子进程中。`BizBuddyAgentKernel` 负责启动、通信和关闭，桌面端统一调用稳定的外层接口，DSH 内部调整由 B 模块消化。

```ts
interface AgentKernel {
  start(config: KernelLaunchConfig): Promise<void>
  prompt(sessionId: string, text: string): AsyncIterable<BizBuddyEvent>
  listTraces(): Promise<TraceSummary[]>
  readTrace(sessionId: string, fromSeq?: number): Promise<TraceEvent[]>
  shutdown(): Promise<void>
}
```

## Agent 处理流程

```text
桌面端提交问题
  ↓
B 模块转交 DSH
  ↓
模型判断是否需要查询资料
  ↓
调用文档检索或 DCS 工具
  ↓
模型根据工具结果生成回答
  ↓
B 模块返回状态、文字、引用和完成事件
```

安环 Persona 规定了基本处理规则。制度、规范和操作要求先查企业文档。设备状态和历史趋势先找测点，再查时间范围内的数据。工具失败或结果为空时返回明确错误，回答内容以实际查询结果为准。

## 业务工具

### 文档检索 `doc_search`

`doc_search` 接收查询内容和返回数量，调用 C 模块的文档检索接口。结果包含原文片段、文档名称、页码、引用编号和片段编号。B 模块把结构化引用单独传给页面，用于跳转数据库页面并高亮对应文件。

MVP 阶段通过 `documentId` 跳转数据库页面并高亮对应文件。文档检索暂时使用相同数据格式的 mock 服务。

### 测点查找 `ts_list`

`ts_list` 根据设备或指标名称查找 DCS 测点，返回测点编号、名称、单位和说明。自然语言中的设备名称经过测点确认后才能进入数据查询。

### 历史数据查询 `ts_query`

`ts_query` 根据测点编号和时间范围查询历史采样值。时间统一使用带时区的 ISO 8601，回答中的数值以接口结果为准。

## 对外事件

| 事件 | 用途 |
|---|---|
| `searching` | 表示正在查询文档或 DCS 数据 |
| `text_delta` | 逐段返回回答文字 |
| `citation` | 返回可定位的文档引用 |
| `done` | 表示本轮处理完成 |
| `error` | 返回模型、工具或进程错误 |

A/E 与 B 模块协议文档记录具体字段和一次完整调用示例，本设计保留事件职责和架构关系。

## 已跑通的流程

文档问答已经跑通。DSH 能够自动调用 `doc_search`，返回文档片段、回答文字和完整引用。

DCS 问答已经跑通。DSH 能够先调用 `ts_list` 确认测点，再调用 `ts_query` 查询历史数据，最后根据采样值生成说明。

两条流程当前使用真实 DSH 子进程和 mock 业务接口。SQLite 会保存用户输入、模型输出、工具调用和工具结果。现有 5 项自动测试全部通过。

## 当前进度与后续工作

DSH 子进程、AgentKernel 首版、三个业务工具、流式事件、文档引用、安环规则和 SQLite 写入已经完成。

后续工作集中在四项内容。

1. 补完会话列表和详情读取。
2. 替换 C、D 模块的真实接口。
3. 增加模型失败、工具超时和空结果测试。
4. 完成桌面端联调和真实模型演示。

## 产品介绍摘要

B 模块以 DSH 为运行基础，负责 BizBuddy 的 Agent 处理过程。文档问答和 DCS 问答已经通过 mock 服务跑通，下一阶段接入真实业务接口并补完会话轨迹读取。
