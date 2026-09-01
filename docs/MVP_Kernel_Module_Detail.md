# MVP 模块 B：Agent 内核（dsh 集成）详细工作说明

> 上游文档：`docs/MVP_Task_Breakdown.md`（分工总览）、`docs/MVP_Client_Tech_Design.md`（架构）
> 负责角色：2 号（Node/TS 能力最强）；工作量 5 周（W1 spike + W2-W5 开发）
> 技术基线：DeepSeek Harness（developer preview，Node/TS，Cordis 插件内核，MIT）

---

## 1. 模块目标与边界

**目标**：把 dsh 嵌入 Electron，作为统一的 Agent 运行时。对用户问题完成「规划 → 调用工具（文档检索/时序查询）→ 流式生成带引用的回答」，并把全过程写成可查询的轨迹日志。

**做**：适配层、五个插件、专家 Agent 声明式定义、对话流式协议、轨迹读取接口。

**不做**：RAG 检索本身（模块 C 的 sidecar）、时序采集（模块 D）、模型配置的 UI 与 Key 保管（模块 G/A，本模块只消费配置）、多专家路由（V1.1，本期只保留声明式配置的扩展位）。

---

## 2. W1 Spike（go/no-go 关口）

用一周时间写一个最小验证工程，回答三个问题：

| # | 验证项 | 通过标准 |
|---|--------|----------|
| 1 | dsh 能否以**库形式**嵌入 Electron utility process（而不是 `dsh web` 独立服务） | 在主进程里 `import` dsh 内核、创建 agent、完成一次真实 LLM 对话 |
| 2 | 自定义 **tool / skill 插件**的开发体验 | 注册一个假的 `doc_search` 工具（返回固定字符串），LLM 能正确发起调用并拿到结果 |
| 3 | **会话日志**能否支撑轨迹观测 | 一次对话后，能从日志中还原出：用户输入、模型调用（token 数）、工具调用（入参/出参/耗时）、最终回答 |

交付物：spike 代码（可丢弃）+ 一页结论报告（每个验证项过/不过 + 坑清单）。

**回退方案**（spike 不通过时）：不引 dsh，把现有后端自研的 plan-execute-review executor 用 TS 重写到适配层后面。接口不变，其他模块无感；代价 +1~2 周，损失 dsh 的会话日志/插件生态。W1 周五前必须出结论并同步全组。

---

## 3. AgentKernel 适配层

**为什么要做**：dsh 是 developer preview，官方声明会有 breaking changes。所有对 dsh 的调用收敛到这一层，UI（模块 E）和主进程（模块 A）只依赖适配层接口，dsh 升级或替换内核时不影响外部。

**接口草案**（`client/kernel/AgentKernel.ts`，W2 冻结）：

```ts
interface AgentKernel {
  // 对话
  send(input: { sessionId: string; text: string }): Promise<void>;
  cancel(sessionId: string): Promise<void>;
  onEvent(cb: (e: KernelEvent) => void): void;   // 流式事件，见第 6 节

  // 会话
  listSessions(): Promise<SessionMeta[]>;
  loadSession(id: string): Promise<Message[]>;
  deleteSession(id: string): Promise<void>;

  // 轨迹（供管理后台）
  listTraces(q?: TraceQuery): Promise<TraceMeta[]>;
  getTrace(id: string): Promise<TraceDetail>;    // 含模型/工具调用、引用、token、耗时

  // 配置
  setModel(cfg: ModelConfig): Promise<void>;      // 由 G 模块注入
  testModel(cfg: ModelConfig): Promise<TestResult>;

  // 技能
  reloadSkills(): Promise<SkillMeta[]>;           // 扫 skills/ 目录
}
```

---

## 4. 插件设计（五个）

### 4.1 Model 插件

- 实现 OpenAI 兼容 provider：`baseURL` / `apiKey` / `model` 来自 G 模块的配置，**Key 由主进程注入，不落地、不进日志**
- 流式：SSE 解析，逐 token 透传给适配层
- 健壮性：超时（默认 60s 可配）、一次重试、错误分类（网络/鉴权/限流/服务端），错误以标准 `KernelEvent` 上报

### 4.2 Tool 插件（三个，均为 HTTP 调 sidecar）

| 工具 | 入参 | 出参 | 说明 |
|------|------|------|------|
| `doc_search` | `{ query: string, topK?: number }` | `{ chunks: [{ docId, title, snippet, score }] }` | 检索本地 RAG 知识库 |
| `ts_list` | `{}` | `{ tags: [{ tag, displayName, unit, desc }] }` | 列出已接入时序点位，供模型决定查什么 |
| `ts_query` | `{ tags: string[], range: string, agg?: string }` | `{ series: [{ tag, summary stats, trend }] }` | 返回统计摘要而非原始点（控制 token） |

约定：工具错误（sidecar 不可用、无数据）返回结构化错误对象而不是抛异常，让模型能向用户解释「知识库没有相关内容」。

### 4.3 Skill 插件

- 启动时扫 `skills/` 目录（含 `.zip`），解析 SKILL.md（名称、描述、正文），注册为 dsh skill
- 逻辑移植自现有 `backend/.../skill_package.py` 与 `skill_registry.py` 的加载语义，TS 重写
- MVP 只加载、不提供 UI；后续接第三方 SKILL.md 压缩包零改动

### 4.4 Session 插件（轨迹观测的数据源）

- 使用 dsh 原生 append-only 会话日志；**不另起一套**
- 开发 `listTraces` / `getTrace` 两个读取适配：把 JSONL 投影成管理后台需要的结构（计划步骤、工具调用、引用、token、耗时）
- 设计约束（官方文档明确要求）：插件不得把状态藏在内存里不写日志，否则 fork/compaction/replay 会不一致

### 4.5 Storage 插件

- 适配到本地 SQLite（会话元数据、配置），替代 dsh 默认存储
- 与 sidecar 的 SQLite 分开部署、各自演化

### 4.6 关闭项

- dsh 面向 coding agent，自带代码执行/沙箱类工具——**全部禁用**，缩小攻击面；sandbox 插件不加载

---

## 5. 专家 Agent 声明式定义

专家 = 一份配置，不是一坨代码。为 V1.1 多专家 + 路由留好扩展位：

```yaml
# agents/safety_compliance.yaml
id: safety_compliance
name: 安全环保合规专家
prompt_template: prompts/safety_compliance.jinja2   # 沿用 jinja2 管理
tools: [doc_search, ts_list, ts_query]
skills: [policy_scope_classifier]                    # 从 skills/ 引用
limits: { max_steps: 8, timeout_s: 120 }
```

- prompt 模板变量：当前时间、已接入点位摘要、知识库概况
- 内置「回答必须带引用」「无证据不下结论」的输出规约
- MVP 只注册这一个专家；内核启动时读 `agents/*.yaml` 目录，V1.1 加专家 = 加文件 + 路由插件

---

## 6. 对话流式协议（与 E 模块的契约，W2 冻结）

```ts
type KernelEvent =
  | { type: 'plan';       steps: string[] }            // 执行计划（先输出 plan）
  | { type: 'tool_start'; tool: string; args: unknown }
  | { type: 'tool_end';   tool: string; ok: boolean; ms: number }
  | { type: 'delta';      text: string }               // 正文流式分片
  | { type: 'citations';  items: Citation[] }          // 引用卡片
  | { type: 'done';       traceId: string; usage: TokenUsage }
  | { type: 'error';      code: string; message: string };
```

对应 UI：「正在检索…」提示 = `tool_start`；引用卡片 = `citations`；轨迹页数据源 = `done.traceId`。

---

## 7. 目录结构

```
client/kernel/
├── AgentKernel.ts          # 适配层接口
├── dsh/
│   ├── DshKernel.ts        # 适配层实现（唯一 import dsh 的地方）
│   └── plugins/
│       ├── model.ts        # 4.1
│       ├── tools.ts        # 4.2
│       ├── skills.ts       # 4.3
│       ├── session.ts      # 4.4
│       └── storage.ts      # 4.5
├── agents/
│   └── safety_compliance.yaml
└── prompts/
    └── safety_compliance.jinja2
```

## 8. 排期

| 周 | 内容 | 产出 |
|----|------|------|
| W1 | spike 三项验证；接口契约评审 | spike 报告（go/no-go） |
| W2 | 适配层骨架 + Model 插件 + 流式协议打通 | 能完成一次无工具的流式对话 |
| W3 | Tool 插件 ×3（先对 sidecar mock） | 对话能调 doc_search 并引用 |
| W4 | Skill 插件 + 专家 YAML + prompt 模板 | 完整专家链路跑通 |
| W5 | Session/Storage 插件、轨迹读取接口、联调与加固 | 管理后台可查轨迹；移交流程 1/2 端到端联调 |

## 9. 验收标准

1. 提问「磨机检修周期」→ 自动调 `doc_search` → 流式回答带 `[1][2]` 引用（流程 1）
2. 提问「SO₂ 是否超标」→ 先 `ts_list` 再 `ts_query` + `doc_search` → 综合回答带双来源引用（流程 2）
3. 轨迹页能看到本次执行的计划、每次工具调用的入参/耗时、token 消耗
4. sidecar 宕机时回答优雅降级为「暂时无法检索知识库」而非报错崩溃
5. 全程 Key 不出现在渲染进程、日志、轨迹中

## 10. 风险

| 风险 | 应对 |
|------|------|
| dsh API breaking change | 适配层隔离 + pnpm 锁版本 + 必要时 fork |
| spike 不通过 | W1 末回退自研 executor（+1~2 周，需提前同步管理层） |
| 会话日志结构与轨迹页需求不匹配 | W1 spike 第 3 项提前验证；不匹配则在 session.ts 里做投影层 |
| 工具调用不稳定（模型不按预期调工具） | prompt 规约 + few-shot；兜底：连续 2 次未调工具时由代码强制注入一次 doc_search |
