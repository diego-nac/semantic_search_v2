"""Tests for Springer source — parser logic."""
import pytest
from bs4 import BeautifulSoup

from multi_scholar_search.sources.springer import (
    _parse_result,
    _PAGE_SIZE,
    _MAX_LIMIT,
)


def _make_html(
    title="Machine Learning for Climate Analysis",
    link="/article/10.1007/s00382-024-07123-4",
    abstract="We apply machine learning to climate data.",
    authors="Alice Smith, Bob Jones",
    year="2024",
    doi="10.1007/s00382-024-07123-4",
):
    return BeautifulSoup(f"""
    <li class="search-result">
      <h2 class="title"><a href="{link}">{title}</a></h2>
      <p class="authors">{authors}</p>
      <p class="abstract">{abstract}</p>
      <span class="year">{year}</span>
      <span class="doi">{doi}</span>
    </li>
    """, "html.parser").find("li")


# ── _parse_result ────────────────────────────────────────────────────────────

def test_parse_title():
    a = _parse_result(_make_html(), "query")
    assert a.title == "Machine Learning for Climate Analysis"


def test_parse_title_link():
    a = _parse_result(_make_html(), "query")
    assert "springer.com" in a.title_link or "10.1007" in a.title_link


def test_parse_doi():
    a = _parse_result(_make_html(), "query")
    assert a.doi == "10.1007/s00382-024-07123-4"


def test_parse_abstract():
    a = _parse_result(_make_html(), "query")
    assert "machine learning" in a.abstract.lower()


def test_parse_year():
    a = _parse_result(_make_html(), "query")
    assert a.year == 2024


def test_parse_authors():
    a = _parse_result(_make_html(), "query")
    assert a.authors == "Alice Smith, Bob Jones"


def test_parse_source():
    a = _parse_result(_make_html(), "query")
    assert a.source == "springer"


def test_parse_query_stored():
    a = _parse_result(_make_html(), "my query")
    assert a.query == "my query"


def test_parse_returns_none_when_no_title():
    soup = BeautifulSoup("<li></li>", "html.parser").find("li")
    assert _parse_result(soup, "q") is None


def test_parse_doi_extracted_from_link():
    a = _parse_result(_make_html(doi="", link="/article/10.1007/s12345-024-001"), "q")
    assert a.doi == "10.1007/s12345-024-001"


# ── constants ────────────────────────────────────────────────────────────────

def test_page_size_positive():
    assert _PAGE_SIZE > 0


def test_max_limit_reasonable():
    assert _MAX_LIMIT >= 50
