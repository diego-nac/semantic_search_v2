"""Tests for _pub_to_article — maps a scholarly pub dict to ScholarArticle."""
import pytest

from multi_scholar_search.sources.google_scholar import _pub_to_article


def _make_pub(**overrides) -> dict:
    base = {
        "bib": {
            "title": "Deep Learning for NLP",
            "author": ["Smith J", "Doe A"],
            "abstract": "We study deep learning methods...",
        },
        "num_citations": 142,
        "citedby_url": "https://scholar.google.com/cites?id=123",
        "pub_url": "https://example.com/paper",
        "eprint_url": "https://arxiv.org/pdf/1234.pdf",
        "doi": "10.1234/dlnlp",
    }
    base.update(overrides)
    return base


def test_title_extracted():
    article = _pub_to_article(_make_pub(), "nlp")
    assert article.title == "Deep Learning for NLP"


def test_authors_joined_from_list():
    article = _pub_to_article(_make_pub(), "nlp")
    assert article.authors == "Smith J, Doe A"


def test_authors_single_string():
    pub = _make_pub()
    pub["bib"]["author"] = "Only One"
    article = _pub_to_article(pub, "nlp")
    assert article.authors == "Only One"


def test_snippet_extracted():
    article = _pub_to_article(_make_pub(), "nlp")
    assert "deep learning" in article.snippet.lower()


def test_cited_by_count_formatted():
    article = _pub_to_article(_make_pub(), "nlp")
    assert article.cited_by_count == "Cited by 142"


def test_cited_by_none_when_zero_citations():
    pub = _make_pub()
    pub["num_citations"] = None
    article = _pub_to_article(pub, "nlp")
    assert article.cited_by_count is None


def test_cited_link_extracted():
    article = _pub_to_article(_make_pub(), "nlp")
    assert "cites" in article.cited_link


def test_doi_extracted():
    article = _pub_to_article(_make_pub(), "nlp")
    assert article.doi == "10.1234/dlnlp"


def test_pdf_link_from_eprint():
    article = _pub_to_article(_make_pub(), "nlp")
    assert article.pdf_link == "https://arxiv.org/pdf/1234.pdf"


def test_pdf_link_falls_back_to_pub_url():
    pub = _make_pub()
    pub.pop("eprint_url", None)
    article = _pub_to_article(pub, "nlp")
    assert article.pdf_link == "https://example.com/paper"


def test_title_link_is_pub_url():
    article = _pub_to_article(_make_pub(), "nlp")
    assert article.title_link == "https://example.com/paper"


def test_query_stored():
    article = _pub_to_article(_make_pub(), "forest recognition")
    assert article.query == "forest recognition"


def test_source_is_google_scholar():
    article = _pub_to_article(_make_pub(), "nlp")
    assert article.source == "google_scholar"


def test_scraped_at_is_set():
    article = _pub_to_article(_make_pub(), "nlp")
    assert article.scraped_at is not None


def test_returns_none_when_no_title():
    pub = _make_pub()
    pub["bib"] = {}
    result = _pub_to_article(pub, "nlp")
    assert result is None
