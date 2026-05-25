"""Tests for IEEE Xplore source — parser logic."""
import pytest

from multi_scholar_search.sources.ieee import (
    _parse_result,
    _PAGE_SIZE,
    _MAX_LIMIT,
)


def _make_raw(**overrides) -> dict:
    base = {
        "articleNumber": "9999999",
        "title": "Deep Learning for Remote Sensing Image Classification",
        "authors": {"authors": [{"full_name": "Alice Smith"}, {"full_name": "Bob Jones"}]},
        "publicationYear": "2022",
        "citationCount": 45,
        "doi": "10.1109/TGRS.2022.9999999",
        "abstractText": "We propose a deep learning method for remote sensing.",
        "publicationTitle": "IEEE Transactions on Geoscience and Remote Sensing",
        "pdfPath": "/stamp/stamp.jsp?tp=&arnumber=9999999",
        "documentLink": "/document/9999999/",
    }
    base.update(overrides)
    return base


# ── _parse_result ────────────────────────────────────────────────────────────

def test_parse_title():
    a = _parse_result(_make_raw(), "query")
    assert a.title == "Deep Learning for Remote Sensing Image Classification"


def test_parse_authors():
    a = _parse_result(_make_raw(), "query")
    assert a.authors == "Alice Smith, Bob Jones"


def test_parse_year():
    a = _parse_result(_make_raw(), "query")
    assert a.year == 2022


def test_parse_doi():
    a = _parse_result(_make_raw(), "query")
    assert a.doi == "10.1109/TGRS.2022.9999999"


def test_parse_citation_count():
    a = _parse_result(_make_raw(), "query")
    assert a.citation_count == 45
    assert a.cited_by_count == "Cited by 45"


def test_parse_abstract():
    a = _parse_result(_make_raw(), "query")
    assert "deep learning" in a.abstract.lower()


def test_parse_title_link():
    a = _parse_result(_make_raw(), "query")
    assert "9999999" in a.title_link


def test_parse_venue():
    a = _parse_result(_make_raw(), "query")
    assert "IEEE" in a.venue


def test_parse_source():
    a = _parse_result(_make_raw(), "query")
    assert a.source == "ieee"


def test_parse_query_stored():
    a = _parse_result(_make_raw(), "my query")
    assert a.query == "my query"


def test_parse_returns_none_when_no_title():
    a = _parse_result(_make_raw(title=""), "q")
    assert a is None


def test_parse_zero_citations():
    a = _parse_result(_make_raw(citationCount=0), "q")
    assert a.cited_by_count == "Cited by 0"


def test_parse_missing_doi():
    a = _parse_result(_make_raw(doi=None), "q")
    assert a.doi is None


# ── constants ────────────────────────────────────────────────────────────────

def test_page_size_positive():
    assert _PAGE_SIZE > 0


def test_max_limit_reasonable():
    assert _MAX_LIMIT >= 50
