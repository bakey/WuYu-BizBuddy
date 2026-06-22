CREATE SCHEMA IF NOT EXISTS wuyu_industry;

CREATE TABLE IF NOT EXISTS wuyu_industry.industry_knowledge_skills (
  id uuid PRIMARY KEY DEFAULT public.uuid_generate_v4(),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  skill_name varchar(100) NOT NULL,
  description text,
  industry_domain varchar(100),
  policy_scope varchar(100),
  dataset_id uuid NOT NULL REFERENCES public.datasets(id),
  retrieval_mode varchar(50) NOT NULL DEFAULT 'fulltext',
  top_k integer NOT NULL DEFAULT 5,
  score_threshold double precision,
  max_context_chars integer NOT NULL DEFAULT 6000,
  chat_model_id uuid,
  embedding_model_id varchar(100),
  system_prompt text,
  enabled boolean NOT NULL DEFAULT true,
  created_by uuid
);

CREATE TABLE IF NOT EXISTS wuyu_industry.industry_knowledge_query_logs (
  id uuid PRIMARY KEY DEFAULT public.uuid_generate_v4(),
  created_at timestamptz NOT NULL DEFAULT now(),
  skill_id uuid REFERENCES wuyu_industry.industry_knowledge_skills(id)
    ON DELETE SET NULL,
  dataset_id uuid REFERENCES public.datasets(id) ON DELETE SET NULL,
  user_id uuid,
  query_text text NOT NULL,
  answer_text text,
  retrieval_mode varchar(50) NOT NULL DEFAULT 'fulltext',
  top_k integer NOT NULL DEFAULT 5,
  retrieved_count integer NOT NULL DEFAULT 0,
  prompt_tokens integer,
  completion_tokens integer,
  total_tokens integer,
  latency_ms integer,
  model_id varchar(100),
  status varchar(50) NOT NULL DEFAULT 'success',
  error text,
  debug jsonb
);

CREATE TABLE IF NOT EXISTS wuyu_industry.industry_knowledge_query_references (
  id uuid PRIMARY KEY DEFAULT public.uuid_generate_v4(),
  created_at timestamptz NOT NULL DEFAULT now(),
  query_log_id uuid NOT NULL REFERENCES
    wuyu_industry.industry_knowledge_query_logs(id) ON DELETE CASCADE,
  segment_id uuid NOT NULL REFERENCES public.datasets_segments(id)
    ON DELETE CASCADE,
  document_id uuid REFERENCES public.datasets_documents(id) ON DELETE SET NULL,
  dataset_id uuid REFERENCES public.datasets(id) ON DELETE SET NULL,
  reference_rank integer NOT NULL,
  score double precision,
  content_snapshot text,
  metadata_snapshot jsonb
);

CREATE TABLE IF NOT EXISTS wuyu_industry.industry_knowledge_feedback (
  id uuid PRIMARY KEY DEFAULT public.uuid_generate_v4(),
  created_at timestamptz NOT NULL DEFAULT now(),
  query_log_id uuid NOT NULL REFERENCES
    wuyu_industry.industry_knowledge_query_logs(id) ON DELETE CASCADE,
  user_id uuid,
  rating integer,
  is_helpful boolean,
  comment text,
  tags jsonb
);

CREATE INDEX IF NOT EXISTS idx_industry_knowledge_skills_dataset_id
  ON wuyu_industry.industry_knowledge_skills(dataset_id);

CREATE INDEX IF NOT EXISTS idx_industry_knowledge_skills_enabled
  ON wuyu_industry.industry_knowledge_skills(enabled);

CREATE INDEX IF NOT EXISTS idx_industry_knowledge_query_logs_skill_created_at
  ON wuyu_industry.industry_knowledge_query_logs(skill_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_industry_knowledge_query_logs_dataset_created_at
  ON wuyu_industry.industry_knowledge_query_logs(dataset_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_industry_knowledge_query_references_log_id
  ON wuyu_industry.industry_knowledge_query_references(query_log_id);

CREATE INDEX IF NOT EXISTS idx_industry_knowledge_query_references_segment_id
  ON wuyu_industry.industry_knowledge_query_references(segment_id);

CREATE INDEX IF NOT EXISTS idx_industry_knowledge_feedback_log_id
  ON wuyu_industry.industry_knowledge_feedback(query_log_id);
