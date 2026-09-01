# 无隅文档与工业知识检索架构及历史资产复用设计

RAG Knowledge Architecture and Legacy Reuse

| 项 | 内容 |
|---|---|
| Status | Draft v1（待 Review） |
| Owner | 徐简（模块 C 成员：任伟 @徐简 @王俊仡） |
| Reviewers | 任伟、潘云泓、王俊仡、yth152（agent-kernel） |
| Related Documents | `docs/RAG_Sidecar_API_协议_v1.0.md`（任伟，branch `complement-backend-apis`）；`docs/agent-kernel-interface-protocol.md`、`docs/bizbuddy-agent-kernel-design.md`（yth152，branch `docs/agent-kernel-interface-protocol`）；`docs/MVP_Client_Tech_Design.md`、`docs/MVP_Task_Breakdown.md`；legacy `docs/RAG_Design.md`（徐简，2026-06-23）；`docs/RAG_Retrieval_Quality_and_Acceptance.md`（本文档姊妹篇） |

---

## 1. Scope（范围）

本文档回答一个任伟的 Sidecar API 协议（v1.0）刻意没有回答、当前也无人回答的问题：

> **无隅 BizBuddy 的"知识"从哪里来、有几类、分别活在哪里、Agent 如何区分使用、一期工程（68.8M 向量库 + 知识图谱）的历史资产在 MVP/V1/V2 中各自如何复用。**

具体包含：

- 双知识源架构：Local Private RAG 与 Industrial Knowledge RAG 的边界与协作
- 部署 Profile A（桌面本地）/ Profile B（企业私服）与存储抽象
- 知识边界（knowledge scope）与数据安全原则
- 跨知识源统一 provenance（引用）最小模型
- 历史资产（BGE-M3、68.8M pgvector、MMR、聚类路由、GraphRAG-Lite、/hybrid_search 等）复用矩阵
- 知识图谱（KG）的明确决策
- Embedding / Reranker 选型依据

## 2. Non-goals（非目标）

- **不定义 Sidecar HTTP API**——路径、字段、状态机、错误码以 `RAG_Sidecar_API_协议_v1.0.md` 为唯一权威，本文档只引用。
- **不定义 `doc_search` 工具契约**——以 `agent-kernel-interface-protocol.md` 与 `bizbuddy-agent-kernel-design.md` 为准。
- **不定义质量指标与验收方法**——见姊妹篇 `RAG_Retrieval_Quality_and_Acceptance.md`。
- **不涉及 DCS 时序数据链路**（模块 D）与前端展示（模块 E/F）。
- 本文档是设计文档，不附带任何实现代码。

## 3. Background（背景）

### 3.1 一期遗产（服务器侧，2026-06 至 2026-08）

一期"工业智能体服务产品"在服务器（地址见运维文档）上沉淀了：

| 资产 | 规模/状态 |
|---|---|
| `chunks` 表（pgvector + 175GB ivfflat，BGE-M3 1024d） | 68,804,002 条，五个来源（html_md / pt_md / arxiv / MDS / chemrxiv） |
| 向量检索链路（`rag/` 模块：probes 调优使查询 3–12s → 0.2–0.4s、MMR、MiniBatchKMeans 聚类路由、FastAPI） | 已 push 旧仓库，设计记录于 legacy `docs/RAG_Design.md` |
| Industrial GraphRAG-Lite（`kg_lite` schema） | 双语版 `kg_bilingual_v3_20260722_144843`：9,448 实体 / 60.8M mentions / 29,982 边 / 348 中英别名 |
| `/hybrid_search` API（:8011，tmux `kg-api`） | 向量 + KG 实体链接 + 图扩展 + RRF（KG 权重 2.0）+ MMR + vector-only fallback；2026-09-01 实测存活 |
| `industrial_knowledge_search` Skill adapter | 服务器 `/data/gufei_vec/skills/`，待 review |

### 3.2 二期现状（MVP，2026-08-31 起）

MVP 转向桌面端产品（`MVP_PRD.md`）：企业**私有文档**的本地 RAG（Sidecar，SQLite + LanceDB，loopback）+ 云端 LLM。模块 C 分工为任伟 @徐简 @王俊仡三人；任伟已完成 Sidecar API 协议 v1.0（879 行，覆盖全部本地文档链路）。

**缺口**：任伟的协议定义了"本地私有文档 RAG 如何工作"，但以下问题在全部现有材料（main、complement、kernel 三个分支 + 本地 Doc/ + 0901 飞书）中均无人覆盖：

1. 私有文档知识和公共工业知识是不是同一个服务？Agent 怎么区分？
2. 一期 68.8M 知识库和 KG 在新产品里放在哪、用不用、什么时候用？
3. 桌面（SQLite/LanceDB）与企业部署（PostgreSQL/pgvector、容器化，0831 review 意见）如何共存？
4. 客户私有文档如何保证不与公共知识混库？

## 4. Problem Statement（问题陈述）

> Agent 内核（模块 B）目前只定义了 `doc_search` 一个知识工具，指向 Sidecar 的本地私有知识库。产品的一期价值（68.8M 工业文献 + KG）在新架构中没有位置；同时 0831 review 提出的 PostgreSQL/容器化部署意见与 MVP 的 SQLite/LanceDB 桌面形态存在张力。缺少一份**知识层面**（而非 API 层面）的架构决策，模块 C 三个人会在"Sidecar 要不要顺便接工业知识库"、"要不要抽象存储"这类问题上各自发挥，最终产生两套不兼容的实现。

## 5. Architecture（总体架构）

### 5.1 双知识源模型

```
                        Agent Kernel (B)
                             │
                ┌────────────┴──────────────┐
                │                           │
          doc_search              industrial_knowledge_search
          （已有契约）                （新增 Tool，V1 启用）
                │                           │
                ▼                           ▼
     Private Document RAG        Industrial Knowledge Service
     （客户自己的文档）           （公共/企业共享工业知识）
                │                           │
     Profile A: 桌面本地          服务器侧服务（复用一期资产）
       SQLite + LanceDB          PostgreSQL/pgvector (68.8M)
       loopback，随安装包分发       + kg_lite 知识图谱
     Profile B: 企业私服          + /hybrid_search API
       PostgreSQL + pgvector
```

**核心决策 D1——两个服务，两个工具，不合并：**

| 维度 | Private Document RAG（doc_search） | Industrial Knowledge RAG（industrial_knowledge_search） |
|---|---|---|
| 数据主权 | 客户私有，永不出企业/本机 | 平台侧公共知识，或企业采购的共享知识包 |
| 数据内容 | 制度、规程、许可证、台账——小（百级文档）、高频更新 | 文献、政策、标准——大（千万级 chunk）、低频更新 |
| 部署 | Profile A 桌面本地 / Profile B 企业私服 | 中心服务器（现有一期服务器，或后续企业版部署） |
| 检索 | 纯向量 + rerank（任伟协议 v1.0） | 向量 + KG 混合（复用 /hybrid_search） |
| Agent 判断依据 | 制度/流程/许可证/台账类问题 | 行业技术、工艺机理、政策标准类问题；本企业文档查不到时 |

**理由**：数据主权边界不同（见 §9）、规模差 5 个数量级（千级 chunk vs 68.8M）、更新节奏不同、检索算法不同（KG 只对公共知识有意义——客户私有文档量级支撑不了图构建）。合并成一个服务会在安全、性能、算法三方面同时变差。

**Agent 如何区分**：内核 Persona（模块 B 的安环专家 prompt）已有"先查企业文档"的规则；V1 增加 `industrial_knowledge_search` 工具后，prompt 约定补一条："企业文档无相关内容，或问题属于行业技术/政策标准类时，调用工业知识检索"。工具选择是模型行为，**不需要**新路由模块。

### 5.2 DeepSeek Harness（dsh）的边界

明确技术事实，防止把 RAG 塞进内核：

```
User → Electron/UI → Agent Kernel(B) → dsh/Adapter → Tool calls
                                                ├─ doc_search        → Sidecar (C)
                                                ├─ ts_query/ts_list  → Collector (D)
                                                └─ industrial_…      → 远端知识服务 (V1)
```

**RAG 是 Agent Kernel 通过 Tool 调用的能力**。embedding、向量库、KG、rerank 全部住在 Tool 背后的服务里（Sidecar / 远端知识服务），不进 dsh 插件层，也不进内核适配层。内核只做：发起调用、透传流式事件、传递 Citation。这与 yth152 已实现的架构一致，本文档予以确认而非更改。

## 6. 阶段演进（MVP / V1 / V2）

| 阶段 | Private RAG | Industrial Knowledge | 依据 |
|---|---|---|---|
| **MVP**（12 周窗口） | Sidecar（任伟协议 v1.0），Profile A | **不接入产品**；一期服务继续在服务器上作为团队内部实验/演示（:8011） | MVP 验收只含私有文档问答（PRD 流程 1/2）；远端服务引入网络依赖、可用性与安全评审，全部超出 MVP 范围 |
| **V1**（对应 PRD 的 V1.1–V1.3 窗口） | 增加 Profile B（企业私服形态） | 新增 `industrial_knowledge_search` Tool，调用 /hybrid_search 的收敛建议版；评估"知识包"离线分发 | 内部试用反馈驱动；工业知识是产品差异化卖点，一期资产的回报点；KG 随本阶段进入（PRD V1.3 规划"引入知识图谱"） |
| **V2** | Profile A/B 并存，统一运维 | KG 能力面向前端可视化（实体/关系/社区摘要）；企业版可将自有知识并入图谱 | 深化企业版差异 |

> MVP 不接入 ≠ 废弃。一期资产在 MVP 期间照常运行维护，作为 V1 的现成后端（见 §8 复用矩阵）。

## 7. 部署 Profile 与存储抽象

### 7.1 两个 Profile

0831 review（PostgreSQL/pgvector/容器化/K8s）与 MVP 客户端设计（SQLite/LanceDB/loopback）**都成立，对应不同交付形态**：

| | Profile A：Desktop Local | Profile B：Enterprise Private Server |
|---|---|---|
| 场景 | 单机单用户，离线/私密优先 | 多客户端共享，IT 统一管控 |
| 形态 | Electron + PyInstaller sidecar（任伟协议 §14） | 容器化 backend 服务，K8s 兼容（0831 方向） |
| 元数据 | SQLite（WAL） | PostgreSQL |
| 向量 | LanceDB / sqlite-vec | pgvector + ivfflat（一期同款） |
| 网络 | 仅 loopback | 内网服务发现 + 持久卷 |
| 鉴权 | X-Sidecar-Token（一次性） | 企业账号/OIDC（复用 backend 现有 auth 线） |

### 7.2 存储抽象——做接口，不做过度设计

为避免 Sidecar 代码写死 LanceDB 后无法迁移到 Profile B：

```
上层（不感知存储）：parser / chunker / embedding / retrieval / rerank / citation
下层（接口）：MetadataStore   VectorStore   DocumentStore   JobStore
MVP 实现：     SQLite          LanceDB        本地文件        SQLite
Profile B 实现：PostgreSQL      pgvector       对象存储/S3     PostgreSQL
```

**明确约束，防止过度设计**：

1. MVP **只实现** Profile A 一套 adapter；Profile B 只保留接口兼容性（不写第二套实现）。
2. 接口定义放在 Python `Protocol`/ABC 层级，方法集对齐任伟协议的对外能力（documents/chunks/jobs/indexes 四域），**不暴露** LanceDB/SQL 方言。
3. 违反信号（出现即回退）：接口方法超过 ~20 个、上层出现 `if profile ==` 分支、为了抽象引入第二套 ORM。
4. Profile B 实现是 V1.1+ 的工作项，届时另出实施 PR，本文档只锁定接口位置与命名。

## 8. 历史资产复用矩阵

| Legacy Asset | 当前状态 | MVP 复用？ | 如何复用 | 是否改造 | Later |
|---|---|---|---|---|---|
| BGE-M3 embedding | 服务器生产 + Sidecar 协议指定 | ✅ | Sidecar `[embedding].model = BAAI/bge-m3`（任伟协议 §13） | 否（模型不动，重嵌入成本极高是一期已确认的约束） | 多语言更新版评估 |
| 68.8M pgvector 库 | 服务器 `pg-gufei-vec`，只读红线 | ❌ 不进 MVP | 作为 Industrial Knowledge Service 的数据底座，V1 经 `/hybrid_search` 供数 | 增量更新管线（任伟数据线） | 知识包子集离线分发 |
| ivfflat + probes 调优经验 | 服务器，P95 3–12s→0.4s | 间接 | Profile B 部署手册直接引用调优参数 | 否 | HNSW 对比 |
| MMR 多样性重排 | 服务器 hybrid 链路 + 旧 `rag/` 模块 | ✅ | Sidecar rerank 之上的可选多样性层（接口位保留，配置默认关） | 改造为纯 numpy 无 PG 依赖 | V1 打开 |
| 聚类路由（MiniBatchKMeans） | 服务器 `rag/clusterer.py` | ❌ | 桌面知识库规模（千级 chunk）不需要 | — | Profile B 大库可复用 |
| GraphRAG-Lite（实体/mention/边/社区） | 服务器 `kg_lite`，双语 v3 | ❌ 不进 MVP | V1 作为 Industrial Knowledge 的增强检索层 | 见 §8.1 KG 决策 | 企业自有知识入图 |
| entity linker（词典+别名+最长匹配） | 服务器 kg/retrieval | ❌（随 KG） | V1 随 `/hybrid_search` 复用 | 抽象为独立包 | 前端实体高亮复用 |
| KG evidence retrieval | 服务器 kg/retrieval | ❌（随 KG） | 同上 | 同上 | citation 增加图谱路径来源 |
| RRF Hybrid 融合（KG 权重 2.0） | 服务器 hybrid_api | ❌ | V1 `industrial_knowledge_search` 的核心算法 | 权重网格化重校（2.0 为手动经验值） | — |
| `/hybrid_search` API（:8011） | 服务器 tmux 运行中 | ❌ | V1 的远端服务原型，直接在其上收敛 API 面 | 加鉴权/限流/稳定字段；密码清理后开源 | 企业版部署 |
| `industrial_knowledge_search` Skill adapter | 服务器 skills/ | ❌ | V1 演进为内核 Tool 插件（对齐 yth152 的 tool 协议） | SKILL.md → dsh tool 注册 | — |
| 80 条评测集与报告 | 服务器 reports/ | ❌ | 种子素材，按姊妹篇质量规范重建为固定回归基准 | 结构化为 jsonl + gold | 持续扩充 |

> 图谱相关资产"不进 MVP"不是放弃：`MVP_PRD.md` V1.3 明确规划 KG；本矩阵给每个资产标注了后续入口，避免"没人认领"的漂移。

### 8.1 KG 决策（明确回答）

**MVP 暂不启用，定位为"远端公共工业知识服务的检索增强 + 独立 Tool"，不作为 `doc_search` 的内部实现。**

理由：

1. **数据匹配度**：一期 KG 从公共文献构建，语义上属于 Industrial Knowledge，不属于任何客户的私有文档；把它塞进 doc_search 会模糊 §9 的知识边界。
2. **部署匹配度**：KG 住在服务器的 PostgreSQL（`kg_lite`），MVP 的 Sidecar 是本地单机进程；强行下沉意味着把 60.8M mentions 级数据搬进安装包，不可行。
3. **质量现状**：图密度 0.06% 导致社区检索关闭、RRF KG 权重 2.0 为手动经验值、KG Useful Rate 在 80 条评测中未形成稳定优势结论——在质量规范（姊妹篇）给出回归证据前，不进入产品主链路。
4. **正确的挂载点**：V1 的 `industrial_knowledge_search` Tool 内部做 vector+KG 混合（复用 /hybrid_search），对 Agent 和前端只暴露统一的 citation——KG 是实现细节，不是产品概念。

## 9. 数据安全与知识边界

### 9.1 Knowledge Scope 分级

| Scope | 定义 | 存储 | 谁可写 |
|---|---|---|---|
| `private` | 单客户本机私有文档 | Profile A 本地 | 该用户 |
| `tenant-private` | 企业内共享文档 | Profile B 企业私服 | 企业管理员 |
| `organization` | 集团/行业共享知识包 | 企业私服或平台分发 | 平台运营 |
| `public-industrial` | 平台公共工业知识 | 中心服务器（68.8M + KG） | 平台数据线（任伟） |

### 9.2 强制规则

1. **客户私有文档默认不得自动上传**到 `organization`/`public-industrial` 任何一级。上传需显式企业级配置且逐文档确认，MVP 不提供该功能。
2. **不同 scope 不混库**：Private RAG 与 Industrial Knowledge 是两个服务（§5.1 D1），物理隔离先行；Profile B 内部多租户隔离是 V1.1 设计项。
3. **查询不串扰**：`doc_search` 只查 private/tenant-private；`industrial_knowledge_search` 只查 organization/public-industrial。工具结果携带 `knowledge_scope` 字段（见 §10），前端可据此区分"你的制度"与"行业资料"。
4. 私有文档内容不出现在远端服务的日志/遥测中；远端知识服务只接收查询文本，不接收本地文档内容。

## 10. 跨知识源统一 Provenance（引用最小模型）

**不改动**任伟协议的 Sidecar citation（document/page/sheet/section/cell_range/chunk_index）与 yth152 的内核 Citation 类型（citationId/documentId/documentName/page?/chunkId/content/score?）。在其上定义跨源扩展字段：

```
Provenance（统一引用最小模型）
├─ knowledge_source     # "local_rag" | "industrial_kg" | "industrial_vector" | "dcs"
├─ knowledge_scope      # §9.1 四级
├─ document_id / chunk_id / source_type / title
├─ page / sheet / section          # 沿用 Sidecar 定位字段
├─ retrieval_channel    # "vector" | "kg_evidence" | "hybrid"
└─ graph_path?          # 仅 KG 来源：实体关系路径（如 dioxin —CONTROLLED_BY→ 活性炭喷射）
```

兼容性：Sidecar 的 citation 增加 `knowledge_source="local_rag"`、`knowledge_scope` 两个可选字段即满足（v1 内新增可选字段是兼容变更，任伟协议 §19）；内核 Citation 的 `content`/`score` 不变。目标：**Local RAG、远端向量、KG Evidence、（未来）DCS 的引用在同一张引用卡片里统一渲染**，前端按 `knowledge_source` 决定图标与跳转。

## 11. Embedding / Reranker 选型依据（补 0831 review 要求）

| 组件 | 选择 | 依据 | 备选与否决理由 |
|---|---|---|---|
| Embedding | BAAI/bge-m3（1024d） | ①一期 68.8M chunks 已用其嵌入，复用即兼容（重嵌入成本一期已论证不可接受）；②中英双语，匹配安环场景中文制度+英文文献混合；③MTEB/中文 C-MTEB 长期靠前，社区部署成熟；④Sidecar 与远端知识服务同模型，未来跨源语义对齐零成本 | OpenAI text-embedding：联网依赖+私有文档外发违规；bge-large-zh：英文弱，与一期不兼容 |
| Reranker | BAAI/bge-reranker-v2-m3 | ①cross-encoder 精度显著优于纯向量分（一期评测 rerank gain 见质量文档基线）；②同双语同家族，部署心智一致；③CPU 可推理（桌面无 GPU 前提）；④一期服务器已验证 | ColBERT：内存/索引复杂度高；无 rerank：A/B 有明确 gain 损失 |

选型变更流程：任何更换 → 触发 `index_generation` 重建（任伟协议 §19 已约束）→ 跑姊妹篇的回归基准 → 达标才切换。

## 12. Failure Handling / Security / Observability

| 维度 | 约定 | 归属 |
|---|---|---|
| 失败处理 | doc_search 失败 → 内核 `RAG_UNAVAILABLE` 事件 + 结构化错误（yth152 已定义）；V1 远端知识工具失败 → 降级为仅私有文档回答并明示"行业知识暂不可用" | 本文档定义降级语义；机制归内核协议 |
| 安全 | Sidecar 全套（loopback/token/路径净化）归任伟协议 §5；本文档追加 §9 数据边界规则；远端知识服务 V1 必须加鉴权+HTTPS+限流后才可被产品调用 | 分层 |
| 可观测 | 复用任伟协议 §15 日志字段；追加 `knowledge_source` 维度，使质量看板（姊妹篇）可分源统计 | 消费方 |

## 13. Versioning / Compatibility

- 本文档为架构决策记录（ADR 性质），变更走 PR + Reviewers 评审。
- 对任伟协议的影响：仅建议新增两个可选 citation 字段（§10），不破坏 v1 兼容性。
- 对内核协议的影响：V1 新增一个 Tool（`industrial_knowledge_search`），走 yth152 现有 tool 注册机制，无协议破坏。
- 历史资产的服务器版本（:8011）在 V1 收敛 API 前保持原样，不承诺向后兼容实验期调用方。

## 14. Trade-offs / Alternatives

| 决策 | 备选 | 取舍 |
|---|---|---|
| 双服务双工具（D1） | 单一"统一知识服务"内部分区 | 单服务看似简单，实则把数据主权、规模、算法、部署四个维度的差异压进一个进程；安全评审（客户文档与公共知识同库）几乎不可过 |
| MVP 不接远端知识 | MVP 就接入 | 早演示差异化，但引入网络/安全/SLA 三类 MVP 外风险，且质量证据不足（§8.1） |
| 存储抽象只做接口 | 直接写死 LanceDB | 写死使 Profile B 需要重写；全抽象则 MVP 过度设计——取"接口存在、单实现" |
| KG 不进 doc_search | doc_search 内部静默融合 KG | 静默融合让引用来源不可解释，违背"无证据不下结论"的产品原则 |

## 15. Acceptance Criteria（本文档的验收）

1. Reviewers 确认双知识源模型与 MVP/V1/V2 划分无异议。
2. 任伟确认：存储抽象接口不与 Sidecar 协议冲突；citation 可选字段方案可接受。
3. yth152/潘云泓确认：V1 `industrial_knowledge_search` Tool 挂载点与降级语义可接受。
4. 复用矩阵中每个 legacy 资产都有明确去向（复用/暂缓/废弃），无"漂移资产"。
5. KG 决策（§8.1）获得张一（领域 Skill）与潘云泓（内核）认可。

## 16. Open Questions

1. `complement-backend-apis` 与 `main` 的合并顺序（影响本文档对 Sidecar 文档的引用路径）。
2. **字段映射冻结（W2 契约冻结事项）**：内核侧 `doc_search` 出参（`docId/title/snippet/score`，见 MVP_Kernel_Module_Detail §4.2）与 Sidecar `/query` 响应（`chunk_id/document_id/document_name/text`，见任伟协议 §8.4）命名不一致，需要一张正式映射表并冻结；本文档不单方面定义该映射。
3. 远端知识服务 V1 是否需要支持"知识包"离线分发（无外网企业）——影响 68.8M 的裁剪策略。
4. Profile B 的多租户隔离粒度（库级/行级）留待 V1.1 设计。
5. 服务器 legacy 代码（`d339aa3`，含密码待清理）是否作为参考实现贡献入 repo。

## 17. Implementation Plan after Approval

| 步骤 | 内容 | 前置 |
|---|---|---|
| 1 | Sidecar 内落地存储抽象接口（纯重构，无行为变化，任伟/王俊仡协商分工） | 本文档合入 |
| 2 | citation 增加 `knowledge_source`/`knowledge_scope` 可选字段 | 步骤 1 |
| 3 | 服务器侧：清理 d339aa3 密码 → push feature 分支 → 按姊妹篇规范建回归基准 | 独立可先行 |
| 4 | V1：`industrial_knowledge_search` Tool（内核注册 + /hybrid_search API 收敛 + 鉴权） | 步骤 3 + 内核 V1 排期 |
| 5 | 质量看板分源统计（消费 `knowledge_source`） | 姊妹篇基准就绪 |
