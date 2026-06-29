-- 创建聊天任务历史表
CREATE TABLE IF NOT EXISTS chat_tasks (
    id SERIAL PRIMARY KEY,
    title VARCHAR(512) NOT NULL,
    meta VARCHAR(255),
    pin VARCHAR(50) DEFAULT '',
    pinned BOOLEAN DEFAULT false,
    active BOOLEAN DEFAULT false,
    agent_name VARCHAR(255),
    agent_icon VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_tasks_active ON chat_tasks(active);
CREATE INDEX IF NOT EXISTS idx_chat_tasks_pinned ON chat_tasks(pinned);
CREATE INDEX IF NOT EXISTS idx_chat_tasks_updated_at ON chat_tasks(updated_at DESC);
