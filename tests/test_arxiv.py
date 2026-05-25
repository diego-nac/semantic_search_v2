"""Tests for arXiv source — parser and fetch logic."""
import pytest
from datetime import datetime, timezone

from multi_scholar_search.sources.arxiv import (
    _parse_result,
    _PAGE_SIZE,
    _MAX_LIMIT,
)


def _make_raw(**overrides):
    """Simulate an arxiv.Result object as a namespace."""
    from types import SimpleNamespace
    author = SimpleNamespace(name="Alice Smith")
    author2 = SimpleNamespace(name="Bob Jones")
    raw = SimpleNamespace(
        entry_id="https://arxiv.org/abs/2401.00001",
        title="Deep Learning for Forest Recognition: A Survey",
        summary="We survey deep learning methods for forest image recognition.",
        published=datetime(2024, 1, 15, tzinfo=timezone.utc),
        authors=[author, author2],
        doi="10.1234/arxiv.2401",
        pdf_url="https://arxiv.org/pdf/2401.00001",
        primary_category=SimpleNamespace(term="cs.CV"),
    )
    for k, v in overrides.items():
        setattr(raw, k, v)
    return raw


# ── _parse_result ────────────────────────────────────────────────────────────

def test_parse_title():
    a = _parse_result(_make_raw(), "query")
    assert a.title == "Deep Learning for Forest Recognition: A Survey"


def test_parse_authors():
    a = _parse_result(_make_raw(), "query")
    assert a.authors == "Alice Smith, Bob Jones"


def test_parse_year():
    a = _parse_result(_make_raw(), "query")
    assert a.year == 2024


def test_parse_doi():
    a = _parse_result(_make_raw(), "query")
    assert a.doi == "10.1234/arxiv.2401"


def test_parse_doi_none_when_missing():
    a = _parse_result(_make_raw(doi=None), "query")
    assert a.doi is None


def test_parse_pdf_link():
    a = _parse_result(_make_raw(), "query")
    assert a.pdf_link == "https://arxiv.org/pdf/2401.00001"


def test_parse_title_link():
    a = _parse_result(_make_raw(), "query")
    assert a.title_link == "https://arxiv.org/abs/2401.00001"


def test_parse_abstract():
    a = _parse_result(_make_raw(), "query")
    assert "forest" in a.abstract.lower()


def test_parse_category():
    a = _parse_result(_make_raw(), "query")
    assert a.category == "cs.CV"


def test_parse_source():
    a = _parse_result(_make_raw(), "query")
    assert a.source == "arxiv"


def test_parse_query_stored():
    a = _parse_result(_make_raw(), "my query")
    assert a.query == "my query"


def test_parse_returns_none_when_no_title():
    a = _parse_result(_make_raw(title="  "), "q")
    assert a is None


def test_parse_no_authors_returns_none_authors():
    a = _parse_result(_make_raw(authors=[]), "q")
    assert a.authors is None


# ── constants ────────────────────────────────────────────────────────────────

def test_page_size_positive():
    assert _PAGE_SIZE > 0


def test_max_limit_reasonable():
    assert _MAX_LIMIT >= 50
