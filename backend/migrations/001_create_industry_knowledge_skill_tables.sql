-- 创建行业知识查询模块专用 schema，用来隔离 skill、日志、引用和反馈表。
-- 本版本为「自包含」设计：不依赖任何业务库表（public.datasets 等），
-- 知识数据来自独立向量库 gufei_vec.chunks，这里只存 skill 配置和查询记账数据。
-- 主键用 PostgreSQL 13+ 内置的 gen_random_uuid()，无需任何扩展。
CREATE SCHEMA IF NOT EXISTS wuyu_industry;

-- 表作用：配置一个可查询的行业知识 skill。
CREATE TABLE IF NOT EXISTS wuyu_industry.industry_knowledge_skills (
  -- skill 主键。
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  -- skill 创建时间。
  created_at timestamptz NOT NULL DEFAULT now(),
  -- skill 更新时间。
  updated_at timestamptz NOT NULL DEFAULT now(),
  -- skill 名称，用于后台管理或前端展示。
  skill_name varchar(100) NOT NULL,
  -- skill 描述，说明这个知识技能覆盖什么内容。
  description text,
  -- 行业领域，例如固废处理、污水处理、环保合规等。
  industry_domain varchar(100),
  -- 知识范围，例如政策法规、行业标准、技术规范等。
  policy_scope varchar(100),
  -- 全文检索模式下绑定的数据集 ID；向量检索模式可为空，且不设外键。
  dataset_id uuid,
  -- 检索模式：vector（向量，默认）/ fulltext（全文）/ 后续可扩展 hybrid。
  retrieval_mode varchar(50) NOT NULL DEFAULT 'vector',
  -- 向量检索绑定的 gufei_vec subdir，例如 html_md；限定范围并大幅加速。
  vector_subdir text,
  -- 默认召回 chunk 数量。
  top_k integer NOT NULL DEFAULT 5,
  -- 召回分数阈值；向量模式下为 cosine 相似度阈值。
  score_threshold double precision,
  -- 向量检索的 IVFFlat probes；为空时由应用使用系统默认值。
  ivfflat_probes integer,
  -- 是否启用重排；为空时由应用使用系统默认值。
  rerank_enabled boolean,
  -- 重排前向量多召回的候选数量；为空时使用系统默认值。
  rerank_over_fetch_k integer,
  -- 拼接给 LLM 的最大上下文字符数。
  max_context_chars integer NOT NULL DEFAULT 6000,
  -- 问答模型配置 ID；预留。
  chat_model_id uuid,
  -- embedding 模型 ID；预留。
  embedding_model_id varchar(100),
  -- skill 专属系统提示词，service 调用 LLM 时会传入。
  system_prompt text,
  -- 是否启用；repository.get_enabled_skill 只读取 enabled=true 的 skill。
  enabled boolean NOT NULL DEFAULT true,
  -- 创建人 ID；预留。
  created_by uuid
);

-- 表作用：记录每一次行业知识 query/answer 的执行日志。
CREATE TABLE IF NOT EXISTS wuyu_industry.industry_knowledge_query_logs (
  -- 查询日志主键。
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  -- 查询发生时间。
  created_at timestamptz NOT NULL DEFAULT now(),
  -- 本次查询使用的 skill；skill 删除后置空，保留历史日志。
  skill_id uuid REFERENCES wuyu_industry.industry_knowledge_skills(id)
    ON DELETE SET NULL,
  -- 本次查询使用的数据集 ID；不设外键，向量模式可为空。
  dataset_id uuid,
  -- 用户 ID；预留。
  user_id uuid,
  -- 用户原始问题。
  query_text text NOT NULL,
  -- 系统最终回答；可能是 LLM 回答，也可能是无上下文兜底回答。
  answer_text text,
  -- 本次实际使用的检索模式。
  retrieval_mode varchar(50) NOT NULL DEFAULT 'vector',
  -- 本次实际使用的 top_k。
  top_k integer NOT NULL DEFAULT 5,
  -- 实际召回的 chunk 数量。
  retrieved_count integer NOT NULL DEFAULT 0,
  -- prompt token 数；预留。
  prompt_tokens integer,
  -- completion token 数；预留。
  completion_tokens integer,
  -- 总 token 数；预留。
  total_tokens integer,
  -- 端到端耗时，单位毫秒。
  latency_ms integer,
  -- 本次调用的大模型标识。
  model_id varchar(100),
  -- 本次查询状态，例如 success、failed、no_context。
  status varchar(50) NOT NULL DEFAULT 'success',
  -- 错误信息；成功流程通常为空。
  error text,
  -- 调试信息，例如 top_k、retrieved_count、subdir、probes、分数等。
  debug jsonb
);

-- 表作用：记录一次回答引用了哪些向量库 chunk。
-- segment_id 用 text，对应 gufei_vec.chunks.id（md5）；不设跨库外键。
CREATE TABLE IF NOT EXISTS wuyu_industry.industry_knowledge_query_references (
  -- 引用记录主键。
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  -- 引用记录创建时间。
  created_at timestamptz NOT NULL DEFAULT now(),
  -- 所属查询日志 ID；日志删除时引用同步删除。
  query_log_id uuid NOT NULL REFERENCES
    wuyu_industry.industry_knowledge_query_logs(id) ON DELETE CASCADE,
  -- 被引用的 chunk ID（向量库 md5 文本主键）；不设外键。
  segment_id text NOT NULL,
  -- 被引用 chunk 所属文档；向量库无此概念，可为空。
  document_id uuid,
  -- 被引用 chunk 所属数据集；向量库无此概念，可为空。
  dataset_id uuid,
  -- 引用顺序，从 1 开始，对应召回排序。
  reference_rank integer NOT NULL,
  -- 检索相关性分数（向量模式为重排分或 cosine）。
  score double precision,
  -- 引用内容快照，避免后续 chunk 内容变化后无法复盘历史回答。
  content_snapshot text,
  -- 引用 metadata 快照，保存 source、subdir、chunk_idx、分数等扩展信息。
  metadata_snapshot jsonb
);

-- 表作用：记录用户对某次行业知识回答的反馈。
CREATE TABLE IF NOT EXISTS wuyu_industry.industry_knowledge_feedback (
  -- 反馈记录主键。
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  -- 反馈创建时间。
  created_at timestamptz NOT NULL DEFAULT now(),
  -- 被反馈的查询日志 ID。
  query_log_id uuid NOT NULL REFERENCES
    wuyu_industry.industry_knowledge_query_logs(id) ON DELETE CASCADE,
  -- 反馈用户 ID；预留。
  user_id uuid,
  -- 用户评分，例如 1 到 5。
  rating integer,
  -- 用户是否认为回答有帮助。
  is_helpful boolean,
  -- 用户文字评论。
  comment text,
  -- 用户反馈标签，例如召回错误、答案不完整、依据不足等。
  tags jsonb
);

-- 索引：按 dataset_id 查找绑定了某个数据集的 skill。
CREATE INDEX IF NOT EXISTS idx_industry_knowledge_skills_dataset_id
  ON wuyu_industry.industry_knowledge_skills(dataset_id);

-- 索引：加速查询已启用 skill，配合 get_enabled_skill 的 enabled=true 条件。
CREATE INDEX IF NOT EXISTS idx_industry_knowledge_skills_enabled
  ON wuyu_industry.industry_knowledge_skills(enabled);

-- 索引：按 retrieval_mode + subdir 查询向量 skill。
CREATE INDEX IF NOT EXISTS idx_industry_knowledge_skills_vector_subdir
  ON wuyu_industry.industry_knowledge_skills(vector_subdir);

-- 索引：按 skill 查询历史日志，并按时间倒序展示。
CREATE INDEX IF NOT EXISTS idx_industry_knowledge_query_logs_skill_created_at
  ON wuyu_industry.industry_knowledge_query_logs(skill_id, created_at DESC);

-- 索引：按 dataset 查询历史日志，并按时间倒序展示。
CREATE INDEX IF NOT EXISTS idx_industry_knowledge_query_logs_dataset_created_at
  ON wuyu_industry.industry_knowledge_query_logs(dataset_id, created_at DESC);

-- 索引：根据 query_log_id 快速查出一次回答引用了哪些 chunks。
CREATE INDEX IF NOT EXISTS idx_industry_knowledge_query_references_log_id
  ON wuyu_industry.industry_knowledge_query_references(query_log_id);

-- 索引：根据 segment_id 反查某个 chunk 被哪些回答引用过。
CREATE INDEX IF NOT EXISTS idx_industry_knowledge_query_references_segment_id
  ON wuyu_industry.industry_knowledge_query_references(segment_id);

-- 索引：根据 query_log_id 快速查出某次回答收到的用户反馈。
CREATE INDEX IF NOT EXISTS idx_industry_knowledge_feedback_log_id
  ON wuyu_industry.industry_knowledge_feedback(query_log_id);
