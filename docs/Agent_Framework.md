# BizBuddy Agent 与 Skill 框架架构文档

## 1. 概述

BizBuddy 的 Agent 框架支持两类 Agent：

- **Simple Agent**：单 Agent 直接调用一个检索/推理链路，适合单一领域问答。
- **Composite Agent**：由 Orchestrator（总控）、多个 Worker（执行者）、Reviewer（评审者）组成的 Agent 团队，按 Plan 协同完成任务。

Composite Agent 的核心能力：

1. **多 Skill 调用**：不同 Worker 可调用不同 Skill，获取不同领域证据。
2. **计划与执行分离**：Orchestrator 负责意图理解和计划生成，Worker 负责执行。
3. **评审与修订循环**：Reviewer 检查结果，发现缺陷时要求 Orchestrator 重新规划并执行。

---

## 2. 核心概念

### 2.1 Agent

Agent 是系统中的智能体单元，存储在 `agents` 表中。

| 字段 | 说明 |
|---|---|
| `id` | Agent 唯一 ID |
| `name` | 名称，如「政策解析专家」 |
| `agent_type` | `simple` / `composite` |
| `system_prompt` | 系统提示词 |
| `retrieval_mode` | Simple Agent 使用：`basic_rag` / `industry_knowledge` |
| `industry_skill_id` | Simple Agent 使用 industry_knowledge 时指向的 skill |
| `default_top_k` | 默认检索数量 |
| `config` | 额外配置 JSON |

### 2.2 Agent 角色（Composite Agent）

Composite Agent 通过 `agent_team_members` 表管理团队成员。

| 角色 | 职责 | 典型配置 |
|---|---|---|
| `orchestrator` | 意图判断、计划生成、修订计划 | 无特定 Skill |
| `worker` | 执行 Plan 中的某一步，调用 Skill 获取数据 | `step_template` 中指定 `action`（Skill 名）和参数 |
| `reviewer` | 评审整体结果，决定 `pass` 或 `revise` | 无特定 Skill |

### 2.3 Skill

Skill 是可被 Worker 调用的能力单元，统一实现 `Skill` 抽象接口。

```python
class Skill(ABC):
    name: str = ""

    @abstractmethod
    async def invoke(self, query: str, context: dict[str, Any]) -> SkillResult:
        ...
```

执行结果 `SkillResult`：

| 字段 | 说明 |
|---|---|
| `skill_name` | Skill 名称 |
| `success` | 是否成功 |
| `content` | 检索/执行结果文本 |
| `references` | 引用列表（每个引用包含 content/source/score/metadata） |
| `metadata` | 元数据 |
| `error` | 错误信息 |

### 2.4 Plan 与 Step

Composite Agent 执行时生成 `AgentPlan`，包含多个 `PlanStep`：

```python
class PlanStep:
    step_number: int
    role: str           # worker
    member_agent_id: int
    action: str         # Skill 名称，如 "policy_search"
    input: dict         # 执行参数，如 {"skill_id": "...", "top_k": 5}
    reason: str         # 为什么需要这一步
    result: SkillResult
    status: str         # pending / running / completed / failed
```

### 2.5 Review

Reviewer 输出 `ReviewResult`：

```python
class ReviewResult:
    verdict: str        # pass / revise
    feedback: str       # 评审意见
    defects: list[str]  # 缺陷列表
```

若 `verdict == "revise"`，Executor 会将 feedback 回传给 Orchestrator，重新生成 Plan 并执行，最多 `MAX_REVISIONS` 次（默认 2 次）。

---

## 3. 系统架构图

```text
用户提问
   │
   ▼
┌─────────────────────────────────────┐
│ Composite Agent                     │
│  ┌───────────────────────────────┐  │
│  │ Orchestrator                  │  │
│  │  - 意图判断                    │  │
│  │  - 生成 Plan（Step 列表）       │  │
│  └───────────────────────────────┘  │
│              │                      │
│              ▼                      │
│  ┌───────────────────────────────┐  │
│  │ Worker 1  ──▶ Skill A         │  │
│  │ Worker 2  ──▶ Skill B         │  │
│  │ Worker 3  ──▶ Skill C         │  │
│  └───────────────────────────────┘  │
│              │                      │
│              ▼                      │
│  ┌───────────────────────────────┐  │
│  │ Reviewer                      │  │
│  │  - pass：输出最终答案          │  │
│  │  - revise：反馈给 Orchestrator │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
```

---

## 4. 代码模块

### 4.1 框架核心

路径：`backend/src/bizbuddy_rag/services/agent_framework/`

| 文件 | 职责 |
|---|---|
| `__init__.py` | 对外导出核心类 |
| `models.py` | `AgentPlan`、`PlanStep`、`SkillResult`、`ReviewResult`、`ExecutionResult` |
| `skills.py` | `Skill` 抽象基类与内置 Skill 实现 |
| `skill_registry.py` | `SkillRegistry`，按名称解析 Skill |
| `agents.py` | `OrchestratorAgent`、`WorkerAgent`、`ReviewerAgent` |
| `executor.py` | `AgentExecutor`，编排 Plan → Worker → Reviewer → Revision 循环 |

### 4.2 数据层

| 文件/表 | 职责 |
|---|---|
| `backend/src/bizbuddy_rag/db/models.py` | `Agent` ORM 模型 |
| `backend/src/bizbuddy_rag/db/repository.py` | `AgentRepository`（含 team member CRUD） |
| `backend/src/bizbuddy_rag/db/execution_repository.py` | `ExecutionRepository`（执行记录持久化） |
| `agents` 表 | Agent 基础信息 |
| `agent_team_members` 表 | Composite Agent 团队成员关系 |
| `agent_executions` 表 | 一次用户请求的执行记录 |
| `agent_execution_steps` 表 | Plan 中每个 Step 的执行记录 |
| `agent_reviews` 表 | Reviewer 评审记录 |

### 4.3 API 层

路径：`backend/src/bizbuddy_rag/api/agent_routes.py`

| 接口 | 说明 |
|---|---|
| `GET /api/v1/agents` | Agent 列表 |
| `GET /api/v1/agents/{id}` | Agent 详情 |
| `POST /api/v1/agents/{id}/query` | Simple Agent 非流式问答 |
| `POST /api/v1/agents/{id}/query/stream` | Simple Agent 流式问答（SSE） |
| `POST /api/v1/agents/{id}/execute` | Composite Agent 非流式执行 |
| `POST /api/v1/agents/{id}/execute/stream` | Composite Agent 流式执行（SSE） |
| `GET /api/v1/agents/{id}/team` | 查看团队成员 |
| `POST /api/v1/agents/{id}/team` | 添加团队成员 |
| `DELETE /api/v1/agents/{id}/team/{member_id}` | 移除团队成员 |
| `GET /api/v1/agents/{id}/executions` | 执行历史 |
| `GET /api/v1/executions/{id}` | 执行详情 |

---

## 5. 内置 Skill 说明

### 5.1 `basic_rag`

- **实现类**：`BasicRAGSkill`
- **作用**：检索本地 `documents` 表，使用 OpenAI embedding 做向量相似度搜索。
- **输入参数**：`db`、`top_k`
- **输出**：`SkillResult`，包含文档片段和引用。

### 5.2 `industry_knowledge`

- **实现类**：`IndustryKnowledgeSkillAdapter`
- **作用**：检索独立向量库 `gufei_vec.chunks`，使用本地 bge-m3 模型生成向量。
- **输入参数**：`db`、`vector_db`、`skill_id`、`top_k`
- **输出**：`SkillResult`，包含行业知识片段和引用。

### 5.3 `policy_search`

- **实现类**：`PolicySearchSkill`
- **作用**：复用 `industry_knowledge` 能力，按 `policy_scope`（national/local/standard/case）区分政策维度。
- **输入参数**：`db`、`vector_db`、`skill_id`、`top_k`、`policy_scope`
- **输出**：`SkillResult`，`metadata` 中标注 `policy_scope`。

---

## 6. 执行流程详解

### 6.1 Simple Agent 执行流程

```text
用户提问
   │
   ▼
AgentRouter 根据 agent.retrieval_mode 选择链路
   │
   ├── basic_rag ──▶ RAGService.retrieve() ──▶ LLM 生成回答
   │
   └── industry_knowledge ──▶ IndustryKnowledgeQueryService.answer() ──▶ LLM 生成回答
```

### 6.2 Composite Agent 执行流程

```text
用户提问
   │
   ▼
AgentExecutor.run()
   │
   ├── 1. 加载 Composite Agent 和 Team 配置
   │
   ├── 2. OrchestratorAgent.create_plan()
   │      输出 AgentPlan（含多个 PlanStep）
   │
   ├── 3. 对每个 PlanStep：
   │      WorkerAgent.execute_step()
   │        → SkillRegistry.get(action) 获取 Skill
   │        → skill.invoke(query, context) 执行
   │        → 收集 SkillResult
   │
   ├── 4. 汇总所有 Worker 结果，调用 LLM 生成 draft_answer
   │
   ├── 5. ReviewerAgent.review()
   │      ├─ verdict == "pass" → 结束，返回最终答案
   │      └─ verdict == "revise" → revision_count += 1
   │            将 feedback 回传给 Orchestrator，回到步骤 2
   │
   └── 6. 保存执行记录到 agent_executions / steps / reviews
```

### 6.3 流式执行事件

`POST /api/v1/agents/{id}/execute/stream` 返回 SSE 事件：

| 事件名 | 说明 |
|---|---|
| `plan` | Orchestrator 生成的 Plan |
| `step_start` | 开始执行某 Step |
| `step_complete` | Step 执行完成 |
| `references` | 最终引用列表 |
| `delta` | 最终答案流式 token |
| `review` | Reviewer 评审结果 |
| `revision` | 进入修订轮次 |
| `done` | 执行完成 |
| `error` | 执行出错 |

---

## 7. 如何扩展新 Skill

### 7.1 实现 Skill 类

在 `backend/src/bizbuddy_rag/services/agent_framework/skills.py` 中新增：

```python
class LawSearchSkill(Skill):
    """法律法规检索 Skill."""

    name = "law_search"

    def __init__(self) -> None:
        self.adapter = IndustryKnowledgeSkillAdapter()

    async def invoke(
        self, query: str, context: dict[str, Any]
    ) -> SkillResult:
        result = await self.adapter.invoke(query, context)
        result.skill_name = self.name
        result.metadata["source_type"] = "law"
        return result
```

### 7.2 注册 Skill

在 `backend/src/bizbuddy_rag/services/agent_framework/skill_registry.py` 中注册：

```python
from bizbuddy_rag.services.agent_framework.skills import (
    ..., LawSearchSkill
)

class SkillRegistry:
    _skills: dict[str, type[Skill]] = {
        "basic_rag": BasicRAGSkill,
        "industry_knowledge": IndustryKnowledgeSkillAdapter,
        "policy_search": PolicySearchSkill,
        "law_search": LawSearchSkill,  # 新增
    }
```

### 7.3 让 Agent 使用新 Skill

#### Simple Agent

直接设置 `retrieval_mode`（若新 Skill 已映射到某个 mode）：

```sql
UPDATE agents
SET retrieval_mode = 'law_search'
WHERE id = 6;
```

> 注：当前 Simple Agent 只支持 `basic_rag` 和 `industry_knowledge`。若要支持更多，需修改 `agent_routes.py` 中的 `_stream_agent_answer` 和 `_agent_answer`。

#### Composite Agent（推荐）

创建 Worker Agent，并加入 Composite Agent 团队：

```sql
-- 1. 创建法律法规 Worker Agent
INSERT INTO agents (name, agent_type, icon, bg, color, "desc", skills, users, rating, featured, category, source, enabled, system_prompt, default_top_k, retrieval_mode, config)
VALUES (
  'law_worker', 'simple', '⚖️', '#F0F5FF', '#2F54EB',
  '法律法规检索 Worker', '["law_search"]', '0', 0.0, false, 'system', '系统组件', true,
  '你是法律法规检索 Worker', 5, 'basic_rag', '{}'
);

-- 2. 假设新 Agent id = 12，加入「政策解析专家」（id=1）团队
INSERT INTO agent_team_members (agent_id, member_agent_id, role, step_template, order_index)
VALUES (
  1, 12, 'worker',
  '{"action": "law_search", "skill_id": "06c6b6c7-1650-47a3-bb80-c1562f76f101", "top_k": 5}'::jsonb,
  6
);
```

`step_template` 中的 `action` 必须等于 `SkillRegistry` 中注册的 Skill 名称。

### 7.4 重启后端

```bash
cd /root/bizbuddy/backend
docker compose build
docker compose up -d
```

---

## 8. 如何创建新的 Composite Agent

以「环保合规专家」为例：

### 8.1 创建 Composite Agent

```sql
INSERT INTO agents (name, agent_type, icon, bg, color, "desc", skills, users, rating, featured, category, source, enabled, system_prompt, default_top_k, retrieval_mode, config)
VALUES (
  '环保合规专家', 'composite', '🌿', '#E6FFFB', '#13C2C2',
  '综合检索环保政策法规与行业标准，给出合规建议。',
  '["policy_search", "standard_search"]', '0', 0.0, false, '环保合规', '官方 Agent', true,
  '你是环保合规专家，基于多维度证据给出合规建议。', 5, 'basic_rag', '{}'
);
```

### 8.2 创建系统组件 Agent

```sql
INSERT INTO agents (name, agent_type, ..., system_prompt)
VALUES
  ('env_orchestrator', 'simple', ..., '你是环保合规总控 Agent，请制定执行计划。'),
  ('env_policy_worker', 'simple', ..., '你是环保政策检索 Worker。'),
  ('env_standard_worker', 'simple', ..., '你是环保标准检索 Worker。'),
  ('env_reviewer', 'simple', ..., '你是环保合规评审专家。');
```

### 8.3 绑定团队

```sql
INSERT INTO agent_team_members (agent_id, member_agent_id, role, step_template, order_index)
VALUES
  (6, 13, 'orchestrator', '{}'::jsonb, 0),
  (6, 14, 'worker', '{"action": "policy_search", "skill_id": "...", "policy_scope": "national"}'::jsonb, 1),
  (6, 15, 'worker', '{"action": "policy_search", "skill_id": "...", "policy_scope": "standard"}'::jsonb, 2),
  (6, 16, 'reviewer', '{}'::jsonb, 3);
```

---

## 9. 当前限制与未来优化

### 9.1 限制

1. **Skill 无独立配置表**：当前通过 `step_template` JSON 传参，缺少版本管理和可视化配置。
2. **Orchestrator 完全依赖 LLM**：Plan 生成不稳定，后续可增加规则模板 fallback。
3. **Reviewer 只能整体评审**：不能针对单个 Step 提出修改意见。
4. **Worker 串行执行**：当前 Plan Step 串行执行，后续可支持并行。
5. **Skill 类型有限**：目前只有检索类 Skill，缺少工具类 Skill（如 calculator、web_search、code_execution）。

### 9.2 未来优化方向

1. 增加 `skills` 配置表，支持 Skill 元数据、参数 Schema、版本管理。
2. 支持 Worker 并行执行，缩短 Composite Agent 响应时间。
3. 引入 Function Calling，让 Orchestrator 更稳定地生成 Plan。
4. 增加工具类 Skill（如 WebSearch、Calculator、CodeExecutor）。
5. 前端增加 Agent 团队可视化配置页面。

---

## 10. 相关文件速查

| 文件 | 说明 |
|---|---|
| `backend/src/bizbuddy_rag/services/agent_framework/skills.py` | Skill 实现 |
| `backend/src/bizbuddy_rag/services/agent_framework/skill_registry.py` | Skill 注册表 |
| `backend/src/bizbuddy_rag/services/agent_framework/agents.py` | Orchestrator/Worker/Reviewer |
| `backend/src/bizbuddy_rag/services/agent_framework/executor.py` | 执行引擎 |
| `backend/src/bizbuddy_rag/services/agent_framework/models.py` | 框架数据模型 |
| `backend/src/bizbuddy_rag/db/repository.py` | Agent 与 Team 数据操作 |
| `backend/src/bizbuddy_rag/db/execution_repository.py` | 执行记录持久化 |
| `backend/src/bizbuddy_rag/api/agent_routes.py` | Agent API |
| `backend/migrations/007_agent_framework.sql` | Agent Framework 表结构 |
| `backend/migrations/008_seed_policy_expert.sql` | 政策解析专家示例数据 |
| `frontend/src/stores/chat.js` | 前端对话状态与流式处理 |
| `frontend/src/components/chat/ChatMessage.vue` | 前端执行轨迹展示 |
