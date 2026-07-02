-- 新增「报告美化专家」Agent
INSERT INTO agents (
  agent_type, name, icon, bg, color, "desc", skills, users, rating, featured, category,
  tag_label, tag_cls, source, enabled, system_prompt, default_top_k, retrieval_mode, config
) VALUES (
  'simple',
  '报告美化专家',
  '🎨',
  '#F9F0FF',
  '#722ED1',
  '把 Markdown/纯文本回答转换成格式美观、结构清晰的 HTML 报告。',
  '["format", "markdown", "html"]',
  '0',
  '0.0',
  false,
  '工具',
  '工具',
  'tag-tool',
  '官方 Agent',
  true,
  '你是报告格式美化专家。请将用户提供的 Markdown/纯文本内容转换成格式美观、结构清晰的 HTML。只输出 HTML 片段，不要输出额外说明。保留原文核心信息，使用语义化标签。',
  0,
  'formatter',
  '{}'
)
ON CONFLICT (name) DO UPDATE SET
  agent_type = EXCLUDED.agent_type,
  icon = EXCLUDED.icon,
  bg = EXCLUDED.bg,
  color = EXCLUDED.color,
  "desc" = EXCLUDED."desc",
  skills = EXCLUDED.skills,
  source = EXCLUDED.source,
  enabled = EXCLUDED.enabled,
  system_prompt = EXCLUDED.system_prompt,
  default_top_k = EXCLUDED.default_top_k,
  retrieval_mode = EXCLUDED.retrieval_mode,
  config = EXCLUDED.config;
