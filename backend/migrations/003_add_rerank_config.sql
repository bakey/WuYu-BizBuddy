-- 迁移目的：为向量检索 skill 增加重排（rerank）相关配置。
-- 重排流程：向量先多召回 rerank_over_fetch_k 条候选，再用 bge-reranker 精排取 top_k。

-- 是否对该 skill 启用重排；为空时由应用使用系统默认值 industry_rerank_enabled。
ALTER TABLE wuyu_industry.industry_knowledge_skills
  ADD COLUMN IF NOT EXISTS rerank_enabled boolean;

-- 重排前向量多召回的候选数量；为空时使用系统默认值 industry_rerank_over_fetch_k。
ALTER TABLE wuyu_industry.industry_knowledge_skills
  ADD COLUMN IF NOT EXISTS rerank_over_fetch_k integer;
