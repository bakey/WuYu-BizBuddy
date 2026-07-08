"""Jinja2 prompt template loader for agent framework."""

import os
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape


_PROMPTS_DIR = os.path.join(os.path.dirname(__file__))

_jinja_env = Environment(
    loader=FileSystemLoader(_PROMPTS_DIR),
    autoescape=select_autoescape(default_for_string=False),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render(name: str, **context: Any) -> str:
    """Render a Jinja2 template from the prompts directory.

    Args:
        name: Template file name (e.g. "create_plan.jinja2").
        **context: Variables passed to the template.

    Returns:
        Rendered string.
    """
    template = _jinja_env.get_template(name)
    return template.render(**context)
