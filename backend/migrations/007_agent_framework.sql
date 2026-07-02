-- Agent 框架扩展：支持 Composite Agent、Orchestrator、Worker、Reviewer

-- 1. Agent 类型
ALTER TABLE agents
  ADD COLUMN IF NOT EXISTS agent_type VARCHAR(20) NOT NULL DEFAULT 'simple';

CREATE INDEX IF NOT EXISTS idx_agents_type ON agents(agent_type);

-- 2. 复合 Agent 团队成员
CREATE TABLE IF NOT EXISTS agent_team_members (
  id SERIAL PRIMARY KEY,
  agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  member_agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  role VARCHAR(20) NOT NULL CHECK (role IN ('orchestrator', 'worker', 'reviewer')),
  step_template JSONB NOT NULL DEFAULT '{}'::jsonb,
  order_index INTEGER NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(agent_id, member_agent_id, role)
);

CREATE INDEX IF NOT EXISTS idx_agent_team_members_agent ON agent_team_members(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_team_members_member ON agent_team_members(member_agent_id);

-- 3. Agent 执行记录
CREATE TABLE IF NOT EXISTS agent_executions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id INTEGER NOT NULL REFERENCES agents(id),
  user_query TEXT NOT NULL,
  status VARCHAR(50) NOT NULL DEFAULT 'running',
  final_answer TEXT,
  plan_json JSONB,
  revision_count INTEGER NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_executions_agent_created ON agent_executions(agent_id, created_at DESC);

-- 4. 执行步骤
CREATE TABLE IF NOT EXISTS agent_execution_steps (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  execution_id UUID NOT NULL REFERENCES agent_executions(id) ON DELETE CASCADE,
  step_number INTEGER NOT NULL,
  role VARCHAR(20) NOT NULL,
  member_agent_id INTEGER REFERENCES agents(id),
  action VARCHAR(100) NOT NULL,
  input_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  output_json JSONB,
  status VARCHAR(50) NOT NULL DEFAULT 'pending',
  review_feedback TEXT,
  started_at timestamptz,
  completed_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_agent_execution_steps_execution ON agent_execution_steps(execution_id, step_number);

-- 5. 评审记录
CREATE TABLE IF NOT EXISTS agent_reviews (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  execution_id UUID NOT NULL REFERENCES agent_executions(id) ON DELETE CASCADE,
  reviewer_agent_id INTEGER REFERENCES agents(id),
  verdict VARCHAR(20) NOT NULL CHECK (verdict IN ('pass', 'revise')),
  feedback TEXT,
  defects JSONB,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_reviews_execution ON agent_reviews(execution_id);
