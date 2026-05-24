import pytest

from multi_scholar_search.models.base import BaseArticle
from multi_scholar_search.utils.doi_enricher import (
    _fetch_bibtex,
    _fetch_pdf_link,
    _lookup_doi,
    _enrich_one,
)


def _make_article(**kwargs) -> BaseArticle:
    defaults = dict(title="Test Article", source="test", query="test query")
    defaults.update(kwargs)
    return BaseArticle(**defaults)


# --- _lookup_doi ---

def test_lookup_doi_returns_none_on_empty_title(monkeypatch):
    def fake_works(**kwargs):
        return {"message": {"items": []}}
    monkeypatch.setattr("multi_scholar_search.utils.doi_enricher._cr.works", fake_works)
    assert _lookup_doi("nonexistent article nobody wrote") is None


def test_lookup_doi_returns_doi_string(monkeypatch):
    def fake_works(**kwargs):
        return {"message": {"items": [{"DOI": "10.1234/test", "title": ["some matching title"]}]}}
    monkeypatch.setattr("multi_scholar_search.utils.doi_enricher._cr.works", fake_works)
    assert _lookup_doi("some title") == "10.1234/test"


def test_lookup_doi_returns_none_on_exception(monkeypatch):
    def fake_works(**kwargs):
        raise ConnectionError("network down")
    monkeypatch.setattr("multi_scholar_search.utils.doi_enricher._cr.works", fake_works)
    assert _lookup_doi("any title") is None


# --- _fetch_bibtex ---

def test_fetch_bibtex_returns_bibtex_string(monkeypatch):
    monkeypatch.setattr(
        "multi_scholar_search.utils.doi_enricher._doi2bib_get_bib",
        lambda doi: (True, "@article{test, title={Test}}")
    )
    result = _fetch_bibtex("10.1234/test")
    assert result is not None
    assert result.startswith("@")


def test_fetch_bibtex_returns_none_if_not_bibtex(monkeypatch):
    monkeypatch.setattr(
        "multi_scholar_search.utils.doi_enricher._doi2bib_get_bib",
        lambda doi: (True, "Not found")
    )
    assert _fetch_bibtex("10.1234/test") is None


def test_fetch_bibtex_returns_none_on_exception(monkeypatch):
    def _raise(doi):
        raise ConnectionError("network down")
    monkeypatch.setattr("multi_scholar_search.utils.doi_enricher._doi2bib_get_bib", _raise)
    assert _fetch_bibtex("10.1234/test") is None


# --- _fetch_pdf_link ---

def test_fetch_pdf_link_returns_url(monkeypatch):
    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"best_oa_location": {"url_for_pdf": "https://example.com/paper.pdf"}}

    monkeypatch.setattr("httpx.get", lambda *a, **kw: FakeResp())
    assert _fetch_pdf_link("10.1234/test") == "https://example.com/paper.pdf"


def test_fetch_pdf_link_returns_none_on_404(monkeypatch):
    class FakeResp:
        status_code = 404
        def raise_for_status(self): pass

    monkeypatch.setattr("httpx.get", lambda *a, **kw: FakeResp())
    assert _fetch_pdf_link("10.1234/test") is None


def test_fetch_pdf_link_falls_back_to_url(monkeypatch):
    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"best_oa_location": {"url_for_pdf": None, "url": "https://example.com/landing"}}

    monkeypatch.setattr("httpx.get", lambda *a, **kw: FakeResp())
    assert _fetch_pdf_link("10.1234/test") == "https://example.com/landing"


def test_fetch_pdf_link_returns_none_when_no_location(monkeypatch):
    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"best_oa_location": None}

    monkeypatch.setattr("httpx.get", lambda *a, **kw: FakeResp())
    assert _fetch_pdf_link("10.1234/test") is None


# --- _enrich_one ---

def test_enrich_one_fills_all_fields(monkeypatch):
    monkeypatch.setattr("multi_scholar_search.utils.doi_enricher._lookup_doi", lambda t: "10.1234/test")
    monkeypatch.setattr("multi_scholar_search.utils.doi_enricher._fetch_bibtex", lambda d: "@article{x}")
    monkeypatch.setattr("multi_scholar_search.utils.doi_enricher._fetch_pdf_link", lambda d: "https://pdf.example.com")

    article = _make_article()
    _enrich_one(article)

    assert article.doi == "10.1234/test"
    assert article.bibtex == "@article{x}"
    assert article.pdf_link == "https://pdf.example.com"


def test_enrich_one_skips_when_no_doi(monkeypatch):
    monkeypatch.setattr("multi_scholar_search.utils.doi_enricher._lookup_doi", lambda t: None)
    article = _make_article()
    _enrich_one(article)
    assert article.doi is None
    assert article.bibtex is None
    assert article.pdf_link is None


def test_enrich_one_uses_existing_doi(monkeypatch):
    called_with = []
    monkeypatch.setattr("multi_scholar_search.utils.doi_enricher._lookup_doi", lambda t: called_with.append(t) or None)
    monkeypatch.setattr("multi_scholar_search.utils.doi_enricher._fetch_bibtex", lambda d: "@article{x}")
    monkeypatch.setattr("multi_scholar_search.utils.doi_enricher._fetch_pdf_link", lambda d: None)

    article = _make_article(doi="10.9999/already")
    _enrich_one(article)

    assert not called_with  # _lookup_doi was NOT called
    assert article.doi == "10.9999/already"
    assert article.bibtex == "@article{x}"
