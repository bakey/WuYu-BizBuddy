-- 迁移目的：让行业知识 skill 查询支持向量检索（gufei_vec.chunks）。
-- 背景：向量库是独立库，chunk 主键是 text(md5)，且没有 document_id/dataset_id 概念，
-- 因此原表里指向 public.datasets_segments 的 uuid 外键无法适用，需要放宽。

-- 1) skills 表：向量检索不绑定 public.datasets，dataset_id 改为可空。
ALTER TABLE wuyu_industry.industry_knowledge_skills
  ALTER COLUMN dataset_id DROP NOT NULL;

-- 2) skills 表：新增向量检索绑定的 subdir（如 html_md），用于限定范围并大幅加速。
ALTER TABLE wuyu_industry.industry_knowledge_skills
  ADD COLUMN IF NOT EXISTS vector_subdir text;

-- 3) skills 表：新增 IVFFlat probes 配置；为空时由应用使用系统默认值。
ALTER TABLE wuyu_industry.industry_knowledge_skills
  ADD COLUMN IF NOT EXISTS ivfflat_probes integer;

-- 4) references 表：去掉指向 public.datasets_segments 的外键。
-- 向量库 chunk 在另一个数据库，外键既无法约束、也会阻止写入 text 主键。
ALTER TABLE wuyu_industry.industry_knowledge_query_references
  DROP CONSTRAINT IF EXISTS industry_knowledge_query_references_segment_id_fkey;

-- 5) references 表：segment_id 由 uuid 改为 text，以容纳向量库的 md5 主键。
-- 全文模式写入的 uuid 也能安全转成 text，历史数据不丢。
ALTER TABLE wuyu_industry.industry_knowledge_query_references
  ALTER COLUMN segment_id TYPE text USING segment_id::text;

-- 6) skills 表：按 retrieval_mode + subdir 查询向量 skill 时加速（可选）。
CREATE INDEX IF NOT EXISTS idx_industry_knowledge_skills_vector_subdir
  ON wuyu_industry.industry_knowledge_skills(vector_subdir);
