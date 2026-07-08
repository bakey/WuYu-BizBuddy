-- 将已有的"政策解析专家"升级为 composite Agent，并配置 Orchestrator + Worker + Reviewer 团队

-- 1. 把政策解析专家改为 composite
UPDATE agents
SET agent_type = 'composite',
    system_prompt = '你是政策解析专家，能够综合国家/地方政策、行业标准与典型案例，给出结构化、带引用的政策解读。'
WHERE name = '政策解析专家';

-- 2. 创建 Orchestrator Agent
INSERT INTO agents (
  name, agent_type, icon, bg, color, "desc", skills, users, rating, featured, category, source, enabled,
  system_prompt, default_top_k, retrieval_mode, config
) VALUES (
  'policy_orchestrator', 'simple', '📋', '#E6F7FF', '#1890FF',
  '政策解析总控 Agent，负责理解用户意图并制定执行计划。',
  '["planning", "intent_analysis"]', '0', '0.0', false, 'system', '系统组件', true,
  '你是政策解析总控 Agent。请分析用户问题，判断需要检索哪些政策维度（国家/地方/标准/案例），并为每个维度指定对应的 Worker 和 Skill。输出 JSON 计划。',
  5, 'basic_rag', '{}'::jsonb
) ON CONFLICT (name) DO UPDATE SET agent_type = EXCLUDED.agent_type;

-- 3. 创建 Worker Agents
INSERT INTO agents (
  name, agent_type, icon, bg, color, "desc", skills, users, rating, featured, category, source, enabled,
  system_prompt, default_top_k, retrieval_mode, config
) VALUES (
  'policy_national_worker', 'simple', '🏛️', '#FFF7E6', '#FA8C16',
  '国家政策检索 Worker。',
  '["policy_search"]', '0', '0.0', false, 'system', '系统组件', true,
  '你是国家政策检索 Worker，调用 policy_search skill 检索中央/国家层面政策法规。',
  5, 'basic_rag', '{"policy_scope": "national"}'::jsonb
) ON CONFLICT (name) DO UPDATE SET agent_type = EXCLUDED.agent_type;

INSERT INTO agents (
  name, agent_type, icon, bg, color, "desc", skills, users, rating, featured, category, source, enabled,
  system_prompt, default_top_k, retrieval_mode, config
) VALUES (
  'policy_local_worker', 'simple', '🏙️', '#F6FFED', '#52C41A',
  '地方政策检索 Worker。',
  '["policy_search"]', '0', '0.0', false, 'system', '系统组件', true,
  '你是地方政策检索 Worker，调用 policy_search skill 检索地方/省级政策法规。',
  5, 'basic_rag', '{"policy_scope": "local"}'::jsonb
) ON CONFLICT (name) DO UPDATE SET agent_type = EXCLUDED.agent_type;

INSERT INTO agents (
  name, agent_type, icon, bg, color, "desc", skills, users, rating, featured, category, source, enabled,
  system_prompt, default_top_k, retrieval_mode, config
) VALUES (
  'policy_standard_worker', 'simple', '📏', '#F9F0FF', '#722ED1',
  '行业标准检索 Worker。',
  '["policy_search"]', '0', '0.0', false, 'system', '系统组件', true,
  '你是行业标准检索 Worker，调用 policy_search skill 检索行业标准、技术规范。',
  5, 'basic_rag', '{"policy_scope": "standard"}'::jsonb
) ON CONFLICT (name) DO UPDATE SET agent_type = EXCLUDED.agent_type;

INSERT INTO agents (
  name, agent_type, icon, bg, color, "desc", skills, users, rating, featured, category, source, enabled,
  system_prompt, default_top_k, retrieval_mode, config
) VALUES (
  'policy_case_worker', 'simple', '💼', '#FFF0F6', '#EB2F96',
  '典型案例检索 Worker。',
  '["basic_rag"]', '0', '0.0', false, 'system', '系统组件', true,
  '你是典型案例检索 Worker，调用 basic_rag skill 检索本地案例文档。',
  5, 'basic_rag', '{"policy_scope": "case"}'::jsonb
) ON CONFLICT (name) DO UPDATE SET agent_type = EXCLUDED.agent_type;

-- 4. 创建 Reviewer Agent
INSERT INTO agents (
  name, agent_type, icon, bg, color, "desc", skills, users, rating, featured, category, source, enabled,
  system_prompt, default_top_k, retrieval_mode, config
) VALUES (
  'policy_reviewer', 'simple', '🔍', '#FFF2E8', '#FA541C',
  '政策解析评审 Agent。',
  '["review"]', '0', '0.0', false, 'system', '系统组件', true,
  '你是政策解析评审专家。请检查回答是否覆盖了国家政策、地方政策、行业标准、典型案例四个维度，证据是否充分，引用是否准确。如有缺陷请明确指出并要求修订。',
  5, 'basic_rag', '{}'::jsonb
) ON CONFLICT (name) DO UPDATE SET agent_type = EXCLUDED.agent_type;

-- 5. 绑定团队关系
WITH composite AS (
  SELECT id FROM agents WHERE name = '政策解析专家'
),
orch AS (SELECT id FROM agents WHERE name = 'policy_orchestrator'),
national AS (SELECT id FROM agents WHERE name = 'policy_national_worker'),
local AS (SELECT id FROM agents WHERE name = 'policy_local_worker'),
standard AS (SELECT id FROM agents WHERE name = 'policy_standard_worker'),
case_worker AS (SELECT id FROM agents WHERE name = 'policy_case_worker'),
rev AS (SELECT id FROM agents WHERE name = 'policy_reviewer')
INSERT INTO agent_team_members (agent_id, member_agent_id, role, step_template, order_index)
SELECT c.id, o.id, 'orchestrator', '{}'::jsonb, 0 FROM composite c, orch o
UNION ALL
SELECT c.id, n.id, 'worker', '{"action": "policy_search", "policy_scope": "national"}'::jsonb, 1 FROM composite c, national n
UNION ALL
SELECT c.id, l.id, 'worker', '{"action": "policy_search", "policy_scope": "local"}'::jsonb, 2 FROM composite c, local l
UNION ALL
SELECT c.id, s.id, 'worker', '{"action": "policy_search", "policy_scope": "standard"}'::jsonb, 3 FROM composite c, standard s
UNION ALL
SELECT c.id, cw.id, 'worker', '{"action": "basic_rag", "policy_scope": "case"}'::jsonb, 4 FROM composite c, case_worker cw
UNION ALL
SELECT c.id, r.id, 'reviewer', '{}'::jsonb, 5 FROM composite c, rev r
ON CONFLICT DO NOTHING;
