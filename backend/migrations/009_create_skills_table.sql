-- Skill 定义表：支持内部原生 Skill 和 OpenAI function calling 格式
CREATE TABLE IF NOT EXISTS skills (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    alias VARCHAR(100),
    format VARCHAR(50) NOT NULL DEFAULT 'native',
    description TEXT NOT NULL,
    parameters_schema JSONB NOT NULL DEFAULT '{}',
    config JSONB NOT NULL DEFAULT '{}',
    handler_module VARCHAR(255),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_skills_name ON skills(name);
CREATE INDEX IF NOT EXISTS idx_skills_format ON skills(format);
CREATE INDEX IF NOT EXISTS idx_skills_enabled ON skills(enabled);

-- 内置原生 Skill
INSERT INTO skills (name, format, description, parameters_schema, config, handler_module, enabled, created_at, updated_at)
VALUES (
    'basic_rag',
    'native',
    '基于本地 documents 表的向量检索与 RAG 回答。',
    '{"type": "object", "properties": {"query": {"type": "string", "description": "检索关键词"}, "top_k": {"type": "integer", "description": "返回数量"}}, "required": ["query"]}'::jsonb,
    '{}'::jsonb,
    'bizbuddy_rag.services.agent_framework.skills.BasicRAGSkill',
    TRUE,
    now(),
    now()
)
ON CONFLICT (name) DO UPDATE SET
    description = EXCLUDED.description,
    parameters_schema = EXCLUDED.parameters_schema,
    handler_module = EXCLUDED.handler_module;

INSERT INTO skills (name, format, description, parameters_schema, config, handler_module, enabled, created_at, updated_at)
VALUES (
    'industry_knowledge',
    'native',
    '基于 gufei_vec 行业知识库的向量检索与回答。',
    '{"type": "object", "properties": {"query": {"type": "string", "description": "检索关键词"}, "skill_id": {"type": "string", "description": "行业知识 skill UUID"}, "top_k": {"type": "integer", "description": "返回数量"}}, "required": ["query", "skill_id"]}'::jsonb,
    '{}'::jsonb,
    'bizbuddy_rag.services.agent_framework.skills.IndustryKnowledgeSkillAdapter',
    TRUE,
    now(),
    now()
)
ON CONFLICT (name) DO UPDATE SET
    description = EXCLUDED.description,
    parameters_schema = EXCLUDED.parameters_schema,
    handler_module = EXCLUDED.handler_module;

INSERT INTO skills (name, format, description, parameters_schema, config, handler_module, enabled, created_at, updated_at)
VALUES (
    'policy_search',
    'native',
    '按政策维度（国家/地方/标准/案例）检索环保政策。',
    '{"type": "object", "properties": {"query": {"type": "string", "description": "检索关键词"}, "skill_id": {"type": "string", "description": "政策知识 skill UUID"}, "policy_scope": {"type": "string", "enum": ["national", "local", "standard", "case"], "description": "政策范围"}, "top_k": {"type": "integer", "description": "返回数量"}}, "required": ["query", "skill_id"]}'::jsonb,
    '{}'::jsonb,
    'bizbuddy_rag.services.agent_framework.skills.PolicySearchSkill',
    TRUE,
    now(),
    now()
)
ON CONFLICT (name) DO UPDATE SET
    description = EXCLUDED.description,
    parameters_schema = EXCLUDED.parameters_schema,
    handler_module = EXCLUDED.handler_module;

-- OpenAI function calling 格式示例：危险废物识别
INSERT INTO skills (name, alias, format, description, parameters_schema, config, enabled, created_at, updated_at)
VALUES (
    'hazardous_waste_identify',
    'identify_hazardous_waste',
    'openai_function',
    '根据废物描述，判断其是否属于危险废物，并返回废物类别和代码。',
    '{
        "type": "object",
        "properties": {
            "waste_description": {"type": "string", "description": "废物描述"},
            "industry": {"type": "string", "description": "所属行业"}
        },
        "required": ["waste_description"]
    }'::jsonb,
    '{"target_skill": "industry_knowledge"}'::jsonb,
    TRUE,
    now(),
    now()
)
ON CONFLICT (name) DO UPDATE SET
    alias = EXCLUDED.alias,
    format = EXCLUDED.format,
    description = EXCLUDED.description,
    parameters_schema = EXCLUDED.parameters_schema,
    config = EXCLUDED.config;

-- OpenAI function calling 格式示例：外部法规查询（演示 HTTP 模式）
INSERT INTO skills (name, alias, format, description, parameters_schema, config, enabled, created_at, updated_at)
VALUES (
    'external_law_query',
    'query_external_law',
    'openai_function',
    '调用外部法律法规查询服务。',
    '{
        "type": "object",
        "properties": {
            "law_name": {"type": "string", "description": "法律法规名称或关键词"},
            "article": {"type": "string", "description": "条款编号，可选"}
        },
        "required": ["law_name"]
    }'::jsonb,
    '{"endpoint": "https://example.com/api/law/query", "method": "POST"}'::jsonb,
    FALSE,
    now(),
    now()
)
ON CONFLICT (name) DO UPDATE SET
    alias = EXCLUDED.alias,
    format = EXCLUDED.format,
    description = EXCLUDED.description,
    parameters_schema = EXCLUDED.parameters_schema,
    config = EXCLUDED.config;
