# Agent 与 Skill 实现说明

> 文档生成时间：2026-07-03
> 适用范围：WuYu-BizBuddy backend Agent / Skill 框架

---

## 1. 总体架构

当前 Agent 框架采用 **Composite Agent = Orchestrator + Workers + Reviewer** 的分层设计：

```
用户请求
  │
  ▼
AgentExecutor.run() / execute_stream()
  │
  ├── OrchestratorAgent.create_plan_with_tools()  ──► 生成 AgentPlan
  │
  ├── WorkerAgent.execute_step() × N              ──► 调用 Skill 检索证据
  │       │
  │       └── SkillRegistry.get(action)           ──► BasicRAGSkill / PolicySearchSkill
  │
  ├── LLM 生成草稿回答
  │
  └── ReviewerAgent.review()                      ──► 评审并决定是否修订
```

---

## 2. 复合 Agent：政策解析专家

数据库里的复合 Agent 配置如下（表 `agents.agent_type = 'composite'`）：

| 字段 | 值 |
|---|---|
| `id` | 1 |
| `name` | 政策解析专家 |
| `system_prompt` | 你是政策解析专家，能够综合国家/地方政策、行业标准与典型案例，给出结构化、带引用的政策解读。 |

### 2.1 Team 成员（表 `agent_team_members`）

| role | member_agent_id | name | 功能说明 |
|---|---|---|---|
| orchestrator | 6 | policy_orchestrator | 分析用户问题，判断检索维度，输出 JSON 计划 |
| worker | 7 | policy_national_worker | 国家/中央层面政策检索 |
| worker | 8 | policy_local_worker | 地方/省级政策检索 |
| worker | 9 | policy_standard_worker | 行业标准、技术规范检索 |
| worker | 10 | policy_case_worker | 本地典型案例检索 |
| reviewer | 11 | policy_reviewer | 检查回答是否覆盖四维度，决定是否需要修订 |

### 2.2 Worker 的 step_template

每个 worker 在 `agent_team_members.step_template` 里写死了要调用的 skill 和参数：

```json
// policy_national_worker / policy_local_worker / policy_standard_worker
{
  "action": "policy_search",
  "skill_id": "06c6b6c7-1650-47a3-bb80-c1562f76f101",
  "policy_scope": "national"  // 或 local / standard
}

// policy_case_worker
{
  "action": "basic_rag",
  "policy_scope": "case"
}
```

---

## 3. Agent 代码实现

### 3.1 基类与角色定义

- **文件**：`src/bizbuddy_rag/services/agent_framework/agents.py`
- **核心类**：
  - `BaseAgent`：封装 `name`、`system_prompt`、LLM 调用入口 `_chat()`
  - `OrchestratorAgent`：生成执行计划，支持普通 JSON 模式和 OpenAI function calling 模式
  - `WorkerAgent`：执行 `PlanStep`，通过 `SkillRegistry` 查找并调用 Skill
  - `ReviewerAgent`：评审 Worker 输出和草稿回答

### 3.2 Orchestrator 计划生成

当前线上使用 **OpenAI function calling 模式**（`create_plan_with_tools`）：

1. 读取所有 worker 的 `step_template`，建立 `(action, policy_scope) → member_agent_id` 映射
2. 把可用的 tools（来自 `SkillRegistry.as_openai_tools()`）传给 LLM
3. LLM 输出多个 `tool_calls`，每个代表一个执行步骤
4. 根据 `policy_scope` 映射到对应 worker，生成 `PlanStep`
5. 如果配置了 reviewer，自动在末尾追加一个 `role="reviewer"` 的步骤

### 3.3 Worker 执行步骤

`WorkerAgent.execute_step()` 逻辑：

```python
skill = SkillRegistry.get(step.action)
merged_context = {**context, **step.input, "worker_name": self.name}
result = await skill.invoke(query, merged_context)
```

其中 `context` 来自 executor，包含 `db`、`vector_db`、`top_k`；`step.input` 来自 plan。

---

## 4. Skill 注册与查找

### 4.1 SkillRegistry

- **文件**：`src/bizbuddy_rag/services/agent_framework/skill_registry.py`
- **功能**：
  - 注册原生 Python Skill 类（硬编码在 `_skills` 字典）
  - 从数据库 `skills` 表加载 OpenAI function 格式的 skill
  - 生成 OpenAI tools 定义供 Orchestrator 使用

### 4.2 已注册的原生 Skill

| name | 实现类 | 文件 | 说明 |
|---|---|---|---|
| `basic_rag` | `BasicRAGSkill` | `skills.py` | 检索本地 `documents` 表 |
| `industry_knowledge` | `IndustryKnowledgeSkillAdapter` | `skills.py` | 检索 `gufei_vec` 行业知识库 |
| `policy_search` | `PolicySearchSkill` | `skills.py` | 按政策范围检索，底层复用 `industry_knowledge` |

### 4.3 Adapter 层

- **文件**：`src/bizbuddy_rag/services/agent_framework/adapters/`
- `NativeSkillAdapter`：把内部 Python Skill 类包装为统一实例，延迟实例化
- `OpenAIFunctionSkillAdapter`：把数据库里 `skills` 表的 OpenAI function 配置映射为可执行 Skill；支持 `target_skill` 映射到内部 skill，或 `endpoint` 走 HTTP 调用

---

## 5. 各 Skill 具体实现

### 5.1 BasicRAGSkill

- **文件**：`src/bizbuddy_rag/services/agent_framework/skills.py`
- **底层服务**：`src/bizbuddy_rag/services/rag.py` 中的 `RAGService`
- **流程**：
  1. `RAGService.retrieve()` 用 `EmbeddingService` 对 query 做 embedding
  2. `DocumentRepository.search_similar()` 在业务库 `documents` 表做向量相似度检索
  3. 返回 `content`（拼接后的引用文本）和 `references`

### 5.2 IndustryKnowledgeSkillAdapter

- **文件**：`src/bizbuddy_rag/services/agent_framework/skills.py`
- **底层服务**：`src/bizbuddy_rag/services/industry_knowledge.py` 中的 `IndustryKnowledgeQueryService`
- **特点**：
  - 只调用 `retrieve()`，**不调用 LLM 生成中间回答**，避免时延和噪音
  - 支持复用外部预计算的 `query_vector`（`_query_vector`）
- **流程**：
  1. 通过 `skill_id` 从 `wuyu_industry.industry_knowledge_skills` 读取配置
  2. 按 `retrieval_mode` 执行检索：
     - `fulltext`：在 `public.datasets_segments` 做 PostgreSQL 全文检索
     - `vector`：在 `gufei_vec.chunks` 做 bge-m3 + IVFFlat 余弦相似度检索
  3. 可选重排（bge-reranker）、去重、来源截断
  4. 返回引用片段

### 5.3 PolicySearchSkill

- **文件**：`src/bizbuddy_rag/services/agent_framework/skills.py`
- **实现**：内部持有 `IndustryKnowledgeSkillAdapter` 实例
- **流程**：
  1. 读取 `context["policy_scope"]`，默认 `national`
  2. 透传参数调用 `IndustryKnowledgeSkillAdapter.invoke()`
  3. 把结果的 `skill_name` 改回 `policy_search`，并在 `metadata` 中标注 `policy_scope`

---

## 6. 执行引擎

- **文件**：`src/bizbuddy_rag/services/agent_framework/executor.py`
- **核心类**：`AgentExecutor`
- **非流式入口**：`run()`
- **流式入口**：`execute_stream()`（供前端 SSE 使用）

### 6.1 execute_stream 流程

1. 加载 composite agent 和 team members
2. 调用 `OrchestratorAgent.create_plan_with_tools()` → `yield "plan"`
3. 遍历 plan.steps：
   - worker 步骤：
     - `yield "step_start"`
     - `WorkerAgent.execute_step()` 调用 skill
     - `yield "step_complete"`
   - reviewer 步骤：
     - `yield "step_start"`
     - `ReviewerAgent.review()`
     - `yield "review"`
     - `yield "step_complete"`
     - 如需修订，追加 `revise` 步骤并进入下一轮
4. 生成草稿回答：`yield "delta"`
5. `yield "done"`

---

## 7. Prompt 模板

- **目录**：`src/bizbuddy_rag/services/agent_framework/prompts/`
- 所有 agent prompt 已迁移到 Jinja2 模板：
  - `create_plan.jinja2`
  - `create_plan_with_tools_system.jinja2`
  - `create_plan_with_tools.jinja2`
  - `review.jinja2`
  - `final_answer.jinja2`
  - `format_report_system.jinja2`
  - `format_report.jinja2`
- 通过 `prompts/__init__.py` 中的 `render(name, **context)` 调用

---

## 8. 关键数据流

```
用户输入
  │
  ▼
Orchestrator 生成 Plan（包含 action + input + member_agent_id）
  │
  ▼
AgentExecutor 按 Plan 执行每个 step
  │
  ├── WorkerAgent.execute_step(step)
  │       │
  │       ▼
  │   SkillRegistry.get(step.action)
  │       │
  │       ├── basic_rag ──► RAGService.retrieve() ──► documents 表
  │       └── policy_search ──► IndustryKnowledgeSkillAdapter.retrieve()
  │                                   │
  │                                   ▼
  │                           gufei_vec.chunks（按 subdir/scope 过滤）
  │
  ▼
汇总 Worker 输出 → LLM 生成草稿回答
  │
  ▼
ReviewerAgent.review() → pass / revise
```

---

## 9. 相关文件索引

| 文件 | 说明 |
|---|---|
| `src/bizbuddy_rag/services/agent_framework/agents.py` | Orchestrator / Worker / Reviewer 实现 |
| `src/bizbuddy_rag/services/agent_framework/executor.py` | Agent 执行引擎 |
| `src/bizbuddy_rag/services/agent_framework/skills.py` | Skill 抽象与内置 Skill 实现 |
| `src/bizbuddy_rag/services/agent_framework/skill_registry.py` | Skill 注册表与 OpenAI tools 生成 |
| `src/bizbuddy_rag/services/agent_framework/adapters/native_skill.py` | 原生 Skill adapter |
| `src/bizbuddy_rag/services/agent_framework/adapters/openai_function.py` | OpenAI function Skill adapter |
| `src/bizbuddy_rag/services/agent_framework/models.py` | PlanStep / AgentPlan / SkillResult 等模型 |
| `src/bizbuddy_rag/services/agent_framework/prompts/` | Jinja2 prompt 模板 |
| `src/bizbuddy_rag/services/rag.py` | BasicRAG 底层检索服务 |
| `src/bizbuddy_rag/services/industry_knowledge.py` | 行业知识检索服务 |
| `src/bizbuddy_rag/db/industry_knowledge_repository.py` | 行业知识数据库访问层 |
