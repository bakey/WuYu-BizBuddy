-- 为 skills 表增加外部生态 skill 唯一标识 skill_id
ALTER TABLE skills
    ADD COLUMN IF NOT EXISTS skill_id VARCHAR(255) UNIQUE,
    ADD COLUMN IF NOT EXISTS source VARCHAR(50) DEFAULT 'internal';

CREATE INDEX IF NOT EXISTS idx_skills_skill_id ON skills(skill_id);
CREATE INDEX IF NOT EXISTS idx_skills_source ON skills(source);
