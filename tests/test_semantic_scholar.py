"""Tests for Semantic Scholar source — parser and pagination logic."""
import pytest

from multi_scholar_search.sources.semantic_scholar import (
    _parse_paper,
    _fetch_page_sync,
    _PAGE_SIZE,
    _MAX_LIMIT,
)


def _make_raw(**overrides) -> dict:
    base = {
        "paperId": "abc123",
        "title": "Forest Image Recognition with Deep Learning",
        "authors": [{"authorId": "1", "name": "Alice"}, {"authorId": "2", "name": "Bob"}],
        "year": 2022,
        "citationCount": 42,
        "referenceCount": 30,
        "externalIds": {"DOI": "10.1234/forest"},
        "openAccessPdf": {"url": "https://example.com/paper.pdf", "status": "GOLD"},
        "abstract": "We study forest image recognition.",
        "venue": "Remote Sensing",
        "isOpenAccess": True,
    }
    base.update(overrides)
    return base


# --- _parse_paper ---

def test_parse_title():
    a = _parse_paper(_make_raw(), "query")
    assert a.title == "Forest Image Recognition with Deep Learning"


def test_parse_authors_joined():
    a = _parse_paper(_make_raw(), "query")
    assert a.authors == "Alice, Bob"


def test_parse_year():
    a = _parse_paper(_make_raw(), "query")
    assert a.year == 2022


def test_parse_doi_from_external_ids():
    a = _parse_paper(_make_raw(), "query")
    assert a.doi == "10.1234/forest"


def test_parse_pdf_link():
    a = _parse_paper(_make_raw(), "query")
    assert a.pdf_link == "https://example.com/paper.pdf"


def test_parse_pdf_link_empty_string_becomes_none():
    raw = _make_raw(openAccessPdf={"url": "", "status": "CLOSED"})
    a = _parse_paper(raw, "query")
    assert a.pdf_link is None


def test_parse_citation_count():
    a = _parse_paper(_make_raw(), "query")
    assert a.citation_count == 42
    assert a.cited_by_count == "Cited by 42"


def test_parse_citation_count_zero():
    a = _parse_paper(_make_raw(citationCount=0), "query")
    assert a.cited_by_count == "Cited by 0"


def test_parse_abstract():
    a = _parse_paper(_make_raw(), "query")
    assert "forest" in a.abstract.lower()


def test_parse_venue():
    a = _parse_paper(_make_raw(), "query")
    assert a.venue == "Remote Sensing"


def test_parse_is_open_access():
    a = _parse_paper(_make_raw(), "query")
    assert a.is_open_access is True


def test_parse_source_field():
    a = _parse_paper(_make_raw(), "query")
    assert a.source == "semantic_scholar"


def test_parse_query_stored():
    a = _parse_paper(_make_raw(), "my query")
    assert a.query == "my query"


def test_parse_returns_none_when_no_title():
    assert _parse_paper({"title": "", "authors": []}, "q") is None


def test_parse_returns_none_on_missing_title_key():
    assert _parse_paper({}, "q") is None


# --- constants ---

def test_page_size_is_50():
    assert _PAGE_SIZE == 50


def test_max_limit_is_50():
    assert _MAX_LIMIT == 50


# --- _fetch_page_sync with mock ---

def test_fetch_page_returns_articles(monkeypatch):
    raw = _make_raw()

    class FakeResp:
        status_code = 200
        def json(self):
            return {"data": [raw, raw]}

    monkeypatch.setattr("httpx.get", lambda *a, **kw: FakeResp())
    articles = _fetch_page_sync("forest", offset=0, limit=10)
    assert len(articles) == 2
    assert articles[0].title == raw["title"]


def test_fetch_page_returns_empty_on_500(monkeypatch):
    class FakeResp:
        status_code = 500
        def json(self):
            return {}

    monkeypatch.setattr("httpx.get", lambda *a, **kw: FakeResp())
    articles = _fetch_page_sync("forest", offset=0, limit=10)
    assert articles == []


def test_fetch_page_retries_on_429(monkeypatch):
    calls = []

    class FakeRespOK:
        status_code = 200
        def json(self):
            return {"data": [_make_raw()]}

    class FakeResp429:
        status_code = 429

    def fake_get(*a, **kw):
        calls.append(1)
        if len(calls) < 2:
            return FakeResp429()
        return FakeRespOK()

    monkeypatch.setattr("httpx.get", fake_get)
    monkeypatch.setattr("time.sleep", lambda s: None)
    articles = _fetch_page_sync("forest", offset=0, limit=10)
    assert len(articles) == 1
    assert len(calls) == 2
