"""Tests for Connected Papers source — parser and fetch logic."""
import pytest

from multi_scholar_search.sources.connected_papers import (
    _parse_search_result,
    _parse_paper_detail,
    _fetch_page_sync,
    _PAGE_SIZE,
    _MAX_LIMIT,
)


def _make_search_result(**overrides) -> dict:
    base = {
        "id": "bff058d480e315a613b234b3ec19eeddd66ea12b",
        "year": {"text": "1996"},
        "title": {"text": "Combination of SVD and GLCM in forest image recognition"},
        "venue": {"text": "Other Conferences"},
        "authors": [
            [{"name": "D. Xia"}],
            [{"name": "Hua Li"}],
            [{"name": "Yong Qiu"}],
        ],
        "doiInfo": {
            "doi": "10.1117/12.262873",
            "doiUrl": "https://doi.org/10.1117/12.262873",
        },
        "corpusid": 122341331,
        "citationStats": {"numCitations": 2, "numReferences": 0},
        "paperAbstract": {"text": "S2 TL;DR: By using both SVD and GLCM..."},
    }
    base.update(overrides)
    return base


def _make_paper_detail(**overrides) -> dict:
    base = {
        "id": "bff058d480e315a613b234b3ec19eeddd66ea12b",
        "corpusid": 122341331,
        "authors": [{"ids": ["2172868"], "name": "D. Xia"}],
        "title": "Combination of SVD and GLCM in forest image recognition",
        "year": 1996,
        "paperAbstract": "We study forest image recognition.",
        "s2Url": "https://www.semanticscholar.org/paper/bff058d480e315a613b234b3ec19eeddd66ea12b",
        "fieldsOfStudy": ["Computer Science", "Environmental Science"],
        "pdfUrls": ["https://example.com/paper.pdf"],
        "venue": "Other Conferences",
        "doi": "10.1117/12.262873",
        "doiUrl": "https://doi.org/10.1117/12.262873",
        "citationCount": 2,
        "referenceCount": 0,
        "isOpenAccess": False,
        "publicationDate": "1996-12-18",
        "tldr": {"text": "A brief summary of the paper."},
    }
    base.update(overrides)
    return base


# ── _parse_search_result ─────────────────────────────────────────────────────

def test_parse_search_result_title():
    a = _parse_search_result(_make_search_result(), "query")
    assert a.title == "Combination of SVD and GLCM in forest image recognition"


def test_parse_search_result_year():
    a = _parse_search_result(_make_search_result(), "query")
    assert a.year == 1996


def test_parse_search_result_authors():
    a = _parse_search_result(_make_search_result(), "query")
    assert a.authors == "D. Xia, Hua Li, Yong Qiu"


def test_parse_search_result_doi():
    a = _parse_search_result(_make_search_result(), "query")
    assert a.doi == "10.1117/12.262873"


def test_parse_search_result_citation_count():
    a = _parse_search_result(_make_search_result(), "query")
    assert a.citation_count == 2
    assert a.cited_by_count == "Cited by 2"


def test_parse_search_result_snippet():
    a = _parse_search_result(_make_search_result(), "query")
    assert "SVD" in a.snippet


def test_parse_search_result_s2_url():
    a = _parse_search_result(_make_search_result(), "query")
    assert "bff058d480e315a613b234b3ec19eeddd66ea12b" in a.title_link


def test_parse_search_result_paper_id():
    a = _parse_search_result(_make_search_result(), "query")
    assert a.paper_id == "bff058d480e315a613b234b3ec19eeddd66ea12b"


def test_parse_search_result_source():
    a = _parse_search_result(_make_search_result(), "query")
    assert a.source == "connected_papers"


def test_parse_search_result_query_stored():
    a = _parse_search_result(_make_search_result(), "my query")
    assert a.query == "my query"


def test_parse_search_result_returns_none_when_no_title():
    raw = _make_search_result(title={"text": ""})
    assert _parse_search_result(raw, "q") is None


def test_parse_search_result_handles_missing_doi():
    raw = _make_search_result(doiInfo=None)
    a = _parse_search_result(raw, "q")
    assert a.doi is None


def test_parse_search_result_handles_zero_citations():
    raw = _make_search_result(citationStats={"numCitations": 0, "numReferences": 0})
    a = _parse_search_result(raw, "q")
    assert a.cited_by_count == "Cited by 0"


def test_parse_search_result_handles_missing_abstract():
    raw = _make_search_result(paperAbstract=None)
    a = _parse_search_result(raw, "q")
    assert a.snippet is None


# ── _parse_paper_detail ──────────────────────────────────────────────────────

def test_parse_paper_detail_title():
    a = _parse_paper_detail(_make_paper_detail(), "query")
    assert a.title == "Combination of SVD and GLCM in forest image recognition"


def test_parse_paper_detail_abstract():
    a = _parse_paper_detail(_make_paper_detail(), "query")
    assert "forest" in a.abstract.lower()


def test_parse_paper_detail_pdf_link():
    a = _parse_paper_detail(_make_paper_detail(), "query")
    assert a.pdf_link == "https://example.com/paper.pdf"


def test_parse_paper_detail_pdf_link_none_when_empty():
    raw = _make_paper_detail(pdfUrls=None)
    a = _parse_paper_detail(raw, "query")
    assert a.pdf_link is None


def test_parse_paper_detail_fields_of_study():
    a = _parse_paper_detail(_make_paper_detail(), "query")
    assert "Computer Science" in a.fields_of_study


def test_parse_paper_detail_tldr():
    a = _parse_paper_detail(_make_paper_detail(), "query")
    assert a.tldr == "A brief summary of the paper."


def test_parse_paper_detail_tldr_none_when_missing():
    raw = _make_paper_detail(tldr=None)
    a = _parse_paper_detail(raw, "query")
    assert a.tldr is None


# ── constants ────────────────────────────────────────────────────────────────

def test_page_size_is_10():
    assert _PAGE_SIZE == 10


def test_max_limit_reasonable():
    assert _MAX_LIMIT >= 100


# ── _fetch_page_sync with mock ───────────────────────────────────────────────

def test_fetch_page_returns_articles(monkeypatch):
    raw = _make_search_result()
    search_body = {"results": [raw, raw], "totalResults": 393111, "totalPages": 39311, "source": "Search"}

    class FakeResp:
        status_code = 200
        def json(self):
            return search_body

    monkeypatch.setattr("httpx.get", lambda *a, **kw: FakeResp())
    articles = _fetch_page_sync("forest", page=1, cookies={})
    assert len(articles) == 2
    assert articles[0].title == raw["title"]["text"]


def test_fetch_page_returns_empty_on_404(monkeypatch):
    class FakeResp:
        status_code = 404
        def json(self):
            return {}

    monkeypatch.setattr("httpx.get", lambda *a, **kw: FakeResp())
    articles = _fetch_page_sync("forest", page=1, cookies={})
    assert articles == []


def test_fetch_page_returns_empty_on_empty_results(monkeypatch):
    class FakeResp:
        status_code = 200
        def json(self):
            return {"results": [], "totalResults": 0}

    monkeypatch.setattr("httpx.get", lambda *a, **kw: FakeResp())
    articles = _fetch_page_sync("forest", page=1, cookies={})
    assert articles == []


def test_fetch_page_retries_on_429(monkeypatch):
    calls = []

    class FakeRespOK:
        status_code = 200
        def json(self):
            return {"results": [_make_search_result()], "totalResults": 1}

    class FakeResp429:
        status_code = 429

    def fake_get(*a, **kw):
        calls.append(1)
        return FakeResp429() if len(calls) < 2 else FakeRespOK()

    monkeypatch.setattr("httpx.get", fake_get)
    monkeypatch.setattr("time.sleep", lambda s: None)
    articles = _fetch_page_sync("forest", page=1, cookies={})
    assert len(articles) == 1
    assert len(calls) == 2
