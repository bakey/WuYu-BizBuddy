-- 扩展 agents 表，增加执行配置
ALTER TABLE agents
    ADD COLUMN IF NOT EXISTS system_prompt TEXT,
    ADD COLUMN IF NOT EXISTS default_top_k INTEGER NOT NULL DEFAULT 5,
    ADD COLUMN IF NOT EXISTS retrieval_mode VARCHAR(50) NOT NULL DEFAULT 'basic_rag',
    ADD COLUMN IF NOT EXISTS industry_skill_id UUID,
    ADD COLUMN IF NOT EXISTS config JSONB NOT NULL DEFAULT '{}'::jsonb;

-- 扩展 chat_tasks 表，记录当前使用的 agent
ALTER TABLE chat_tasks
    ADD COLUMN IF NOT EXISTS agent_id INTEGER REFERENCES agents(id);

-- 为现有 Agent 补充 system_prompt 和 retrieval_mode
UPDATE agents SET
    system_prompt = '你是一个有帮助的助手。请严格根据以下参考资料回答用户问题，如果参考资料不足以回答问题，请明确告知。',
    retrieval_mode = 'basic_rag',
    default_top_k = 5
WHERE name = '政策解析专家';

UPDATE agents SET
    system_prompt = '你是工艺指导专家。请根据行业技术资料，回答焚烧、填埋、资源化等工艺参数、排放预测与故障诊断相关问题。',
    retrieval_mode = 'basic_rag',
    default_top_k = 5
WHERE name = '工艺指导专家';

UPDATE agents SET
    system_prompt = '你是企业对标分析师。请根据企业资料，对比分析目标企业的经营、技术与专利布局。',
    retrieval_mode = 'basic_rag',
    default_top_k = 5
WHERE name = '企业对标分析师';

UPDATE agents SET
    system_prompt = '你是图谱探索员。请基于知识图谱关系，探索行业实体之间的关联路径。',
    retrieval_mode = 'basic_rag',
    default_top_k = 5
WHERE name = '图谱探索员';

UPDATE agents SET
    system_prompt = '你是 DeepResearch 研究员。请进行多步推理、多源交叉验证，输出含引用链的深入研究回答。',
    retrieval_mode = 'basic_rag',
    default_top_k = 8
WHERE name = 'DeepResearch';
