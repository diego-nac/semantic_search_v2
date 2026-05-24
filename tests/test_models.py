from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from multi_scholar_search.models.google_scholar import ScholarArticle


def test_minimal_valid_article():
    a = ScholarArticle(title="Test", query="q")
    assert a.title == "Test"
    assert a.source == "google_scholar"


def test_scraped_at_default_is_utc():
    a = ScholarArticle(title="Test", query="q")
    assert a.scraped_at.tzinfo is not None


def test_optional_fields_default_to_none():
    a = ScholarArticle(title="Test", query="q")
    for field in ("title_link", "article_id", "authors", "snippet", "cited_by_count", "cited_link", "versions_count", "versions_link"):
        assert getattr(a, field) is None


def test_title_required():
    with pytest.raises(ValidationError):
        ScholarArticle(query="q")


def test_query_required():
    with pytest.raises(ValidationError):
        ScholarArticle(title="Title")


def test_full_article():
    a = ScholarArticle(
        title="Attention Is All You Need",
        title_link="https://arxiv.org/abs/1706.03762",
        article_id="ABC123",
        authors="Vaswani et al.",
        snippet="Transformers changed NLP.",
        cited_by_count="Cited by 98432",
        cited_link="https://scholar.google.com/scholar?cites=789",
        versions_count="All 20 versions",
        versions_link="https://scholar.google.com/scholar?cluster=789",
        query="transformer attention",
    )
    assert a.article_id == "ABC123"
    assert a.cited_by_count == "Cited by 98432"
