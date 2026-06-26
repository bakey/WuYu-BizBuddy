"""Tests for industry knowledge API models."""

from uuid import uuid4

import pytest

from bizbuddy_rag.industry_models import (
    IndustryKnowledgeFeedbackRequest,
    IndustryKnowledgeReference,
    IndustryKnowledgeRetrieveRequest,
    IndustryKnowledgeRetrieveResponse,
)


def test_retrieve_request_accepts_skill_query_and_top_k() -> None:
    """Retrieve requests require a skill ID and a non-empty query."""
    skill_id = uuid4()
    payload = IndustryKnowledgeRetrieveRequest(
        skill_id=skill_id,
        query="生活垃圾焚烧设施需要建立哪些台账？",
        top_k=3,
    )
    assert payload.skill_id == skill_id
    assert payload.top_k == 3


def test_retrieve_request_rejects_empty_query() -> None:
    """Empty query text is invalid."""
    with pytest.raises(ValueError):
        IndustryKnowledgeRetrieveRequest(skill_id=uuid4(), query="")


def test_retrieve_response_wraps_references_and_debug() -> None:
    """Retrieve responses carry evidence chunks and debug metadata."""
    reference = IndustryKnowledgeReference(
        segment_id=str(uuid4()),
        document_id=uuid4(),
        dataset_id=uuid4(),
        chunk_index=1,
        content="生活垃圾焚烧设施运行单位应当建立运行台账。",
        score=0.37,
        metadata={"source": "mock.md"},
    )
    response = IndustryKnowledgeRetrieveResponse(
        items=[reference],
        debug={"retrieval_mode": "fulltext", "retrieved_count": 1},
    )
    assert response.items[0].score == 0.37
    assert response.debug["retrieval_mode"] == "fulltext"


def test_reference_accepts_vector_source_without_uuid_ids() -> None:
    """Vector-mode references use a text segment_id and have no uuid doc/dataset."""
    reference = IndustryKnowledgeReference(
        segment_id="d41d8cd98f00b204e9800998ecf8427e",
        chunk_index=2,
        content="生活垃圾焚烧设施运行单位应当建立运行台账。",
        score=0.82,
        source="/data/html_md/xxx.md",
        subdir="html_md",
        metadata={"n_chunks": 10},
    )
    assert reference.document_id is None
    assert reference.dataset_id is None
    assert reference.subdir == "html_md"


def test_feedback_rating_range() -> None:
    """Feedback ratings are constrained to one through five."""
    with pytest.raises(ValueError):
        IndustryKnowledgeFeedbackRequest(query_log_id=uuid4(), rating=6)
