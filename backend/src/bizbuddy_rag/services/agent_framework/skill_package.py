"""SKILL.md 技能包解析器。

支持从目录或 .zip 压缩包加载符合 open skill 约定的技能包：

    skill-name/
    ├── SKILL.md          # 必需：YAML frontmatter + Markdown 说明
    └── ...               # 可选资源

SKILL.md frontmatter 示例：

    ---
    name: policy_analyzer
    skill_id: skill-policy-analyzer-v1
    description: 解析用户问题中的政策范围并收集证据。
    format: prompt
    parameters:
      type: object
      properties:
        query:
          type: string
      required: [query]
    ---

    # 执行说明
    1. 从 query 中提取政策关键词...
"""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class SkillPackage:
    """解析后的 SKILL.md 技能包。"""

    name: str
    skill_id: str
    description: str
    format: str
    parameters_schema: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    instructions: str = ""
    source_dir: Path | None = None


class SkillPackageLoader:
    """SKILL.md 技能包加载器。"""

    @classmethod
    def load_from_directory(cls, directory: str | Path) -> SkillPackage:
        """从目录加载 SKILL.md。"""
        skill_dir = Path(directory)
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            raise FileNotFoundError(f"SKILL.md not found in {skill_dir}")

        raw = skill_md.read_text(encoding="utf-8")
        return cls._parse(raw, source_dir=skill_dir)

    @classmethod
    def load_from_zip(cls, zip_path: str | Path) -> SkillPackage:
        """从 .zip 压缩包加载 SKILL.md。

        解压到临时目录后解析，解析后保留临时目录引用便于后续读取资源。
        """
        zip_path = Path(zip_path)
        if not zip_path.exists():
            raise FileNotFoundError(f"zip file not found: {zip_path}")

        temp_dir = Path(tempfile.mkdtemp(prefix="skill_"))
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(temp_dir)
        except zipfile.BadZipFile as exc:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise ValueError(f"invalid zip file: {zip_path}") from exc

        # 若压缩包内只有一层目录，则进入该目录
        entries = [e for e in temp_dir.iterdir() if not e.name.startswith(".")]
        if len(entries) == 1 and entries[0].is_dir():
            skill_dir = entries[0]
        else:
            skill_dir = temp_dir

        if not (skill_dir / "SKILL.md").exists():
            raise FileNotFoundError(f"SKILL.md not found in extracted {zip_path}")

        return cls.load_from_directory(skill_dir)

    @classmethod
    def _parse(cls, raw: str, source_dir: Path | None = None) -> SkillPackage:
        """解析 SKILL.md 文本。"""
        raw = raw.strip()
        if not raw.startswith("---"):
            raise ValueError("SKILL.md must start with YAML frontmatter '---'")

        # 找到第二个 --- 分隔 frontmatter 和 body
        parts = raw.split("---", 2)
        if len(parts) < 3:
            raise ValueError("SKILL.md must contain YAML frontmatter and Markdown body")

        frontmatter_text = parts[1].strip()
        instructions = parts[2].strip()

        try:
            meta = yaml.safe_load(frontmatter_text) or {}
        except yaml.YAMLError as exc:
            raise ValueError(f"invalid YAML frontmatter: {exc}") from exc

        if not isinstance(meta, dict):
            raise ValueError("SKILL.md frontmatter must be a YAML mapping")

        name = meta.get("name") or ""
        skill_id = meta.get("skill_id") or meta.get("id") or ""
        description = meta.get("description") or ""
        if not name or not description:
            raise ValueError("SKILL.md frontmatter must contain 'name' and 'description'")

        format_ = meta.get("format") or "prompt"
        parameters_schema = meta.get("parameters") or {}
        config = meta.get("config") or {}

        return SkillPackage(
            name=name,
            skill_id=skill_id,
            description=description,
            format=format_,
            parameters_schema=parameters_schema,
            config=config,
            instructions=instructions,
            source_dir=source_dir,
        )
