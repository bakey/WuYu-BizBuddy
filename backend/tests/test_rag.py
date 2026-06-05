"""RAG 服务单元测试."""

import pytest

from bizbuddy_rag.models import DocumentCreate


def test_document_create_model() -> None:
    """测试文档创建模型."""
    doc = DocumentCreate(content="hello world", source="test")
    assert doc.content == "hello world"
    assert doc.source == "test"
    assert doc.metadata is None


def test_document_create_requires_content() -> None:
    """测试文档内容必填."""
    with pytest.raises(ValueError):
        DocumentCreate(content="")
