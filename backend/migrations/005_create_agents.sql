-- Agent 表：存储系统中可用的 Agent
CREATE TABLE IF NOT EXISTS agents (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    icon VARCHAR(50) NOT NULL,
    bg VARCHAR(100) NOT NULL,
    color VARCHAR(100) NOT NULL,
    "desc" TEXT NOT NULL,
    skills JSONB NOT NULL DEFAULT '[]'::jsonb,
    users VARCHAR(50) NOT NULL DEFAULT '0',
    rating NUMERIC(2, 1) NOT NULL DEFAULT 0.0,
    featured BOOLEAN NOT NULL DEFAULT false,
    category VARCHAR(100) NOT NULL,
    tag_label VARCHAR(50),
    tag_cls VARCHAR(50),
    source VARCHAR(50) NOT NULL DEFAULT '官方 Agent',
    enabled BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agents_category ON agents(category);
CREATE INDEX IF NOT EXISTS idx_agents_featured ON agents(featured);
CREATE INDEX IF NOT EXISTS idx_agents_enabled ON agents(enabled);

-- 插入前端 mock 数据
INSERT INTO agents (
    name, icon, bg, color, "desc", skills, users, rating, featured, category, tag_label, tag_cls, source
) VALUES
(
    '政策解析专家', '📜', 'var(--primary-light)', 'var(--primary)',
    '解读国/省/市三级固废政策，输出风险点、合规清单与执行要求。',
    '["政策检索", "条文比对", "影响评估", "合规清单"]'::jsonb,
    '1.2k', 4.9, true, '政策解析', '推荐', 'tag-green', '官方 Agent'
),
(
    '工艺指导专家', '🏭', '#FEF3C7', 'var(--warn)',
    '提供焚烧、填埋、资源化等核心工艺参数、排放预测与故障诊断建议。',
    '["工艺参数", "排放预测", "故障诊断", "能耗分析", "+1"]'::jsonb,
    '846', 4.7, false, '工艺技术', NULL, NULL, '官方 Agent'
),
(
    '企业对标分析师', '📊', 'var(--purple-light)', 'var(--purple)',
    '对比目标企业的经营、技术与专利布局，输出竞争情报与差距分析。',
    '["企业画像", "技术对比", "专利矩阵", "行业排名"]'::jsonb,
    '612', 4.6, false, '企业研究', NULL, NULL, '官方 Agent'
),
(
    '图谱探索员', '🕸️', 'var(--info-light)', 'var(--info)',
    '通过实体-关系路径探索行业知识网络与隐藏关联，自动生成图谱可视化。',
    '["实体检索", "路径推理", "图谱可视化"]'::jsonb,
    '418', 4.5, false, '图谱与关系', NULL, NULL, '官方 Agent'
),
(
    'DeepResearch', '🔬', 'var(--danger-light)', 'var(--danger)',
    '多步推理 · 多源交叉验证 · 输出含引用链的研究报告，适合复杂选题。',
    '["问题拆解", "多源检索", "交叉验证", "+3"]'::jsonb,
    '928', 4.8, false, '深度研究', '深度', 'tag-purple', '官方 Agent'
)
ON CONFLICT (name) DO UPDATE SET
    icon = EXCLUDED.icon,
    bg = EXCLUDED.bg,
    color = EXCLUDED.color,
    "desc" = EXCLUDED."desc",
    skills = EXCLUDED.skills,
    users = EXCLUDED.users,
    rating = EXCLUDED.rating,
    featured = EXCLUDED.featured,
    category = EXCLUDED.category,
    tag_label = EXCLUDED.tag_label,
    tag_cls = EXCLUDED.tag_cls,
    source = EXCLUDED.source,
    updated_at = NOW();
