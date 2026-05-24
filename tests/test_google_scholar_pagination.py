import math

import pytest

from multi_scholar_search.sources.google_scholar import (
    MAX_LIMIT,
    RESULTS_PER_PAGE,
    _build_url,
)


def test_build_url_start_zero_by_default():
    url = _build_url("machine learning")
    assert "start=0" in url


def test_build_url_start_increments_per_page():
    url_p1 = _build_url("machine learning", start=0)
    url_p2 = _build_url("machine learning", start=10)
    url_p3 = _build_url("machine learning", start=20)
    assert "start=0" in url_p1
    assert "start=10" in url_p2
    assert "start=20" in url_p3


def test_build_url_always_requests_10_per_page():
    url = _build_url("query", start=30)
    assert f"num={RESULTS_PER_PAGE}" in url


def test_pages_needed_for_10():
    assert math.ceil(10 / RESULTS_PER_PAGE) == 1


def test_pages_needed_for_11():
    assert math.ceil(11 / RESULTS_PER_PAGE) == 2


def test_pages_needed_for_50():
    assert math.ceil(50 / RESULTS_PER_PAGE) == 5


def test_max_limit_is_50():
    assert MAX_LIMIT == 50


def test_results_per_page_is_10():
    assert RESULTS_PER_PAGE == 10


def test_start_offset_formula():
    for page in range(5):
        start = page * RESULTS_PER_PAGE
        assert start == page * 10
