import json
from pathlib import Path

import pytest

from multi_scholar_search.models.google_scholar import ScholarArticle
from multi_scholar_search.utils.storage import _next_index, _slugify, build_filepath, save_articles


def make_article(**kwargs) -> ScholarArticle:
    defaults = dict(title="Test Article", query="test query")
    return ScholarArticle(**{**defaults, **kwargs})


# --- slugify ---

def test_slugify_basic():
    assert _slugify("Deep Learning") == "deep_learning"


def test_slugify_special_chars():
    assert _slugify("NLP: a survey!") == "nlp_a_survey"


def test_slugify_truncates_at_50():
    long = "a" * 100
    assert len(_slugify(long)) <= 50


def test_slugify_trims_whitespace():
    assert _slugify("  test  ") == "test"


# --- _next_index ---

def test_next_index_empty_folder(tmp_path):
    assert _next_index(tmp_path) == 0


def test_next_index_nonexistent_folder(tmp_path):
    assert _next_index(tmp_path / "does_not_exist") == 0


def test_next_index_counts_jsonl_files(tmp_path):
    for i in range(3):
        (tmp_path / f"file_{i}.jsonl").write_text("")
    assert _next_index(tmp_path) == 3


def test_next_index_ignores_non_jsonl(tmp_path):
    (tmp_path / "file.jsonl").write_text("")
    (tmp_path / "file.txt").write_text("")
    (tmp_path / "file.json").write_text("")
    assert _next_index(tmp_path) == 1


# --- build_filepath ---

def test_filepath_is_under_google_scholar(tmp_path):
    path = build_filepath("deep learning", str(tmp_path))
    assert path.parent.name == "google_scholar"


def test_filepath_has_jsonl_extension(tmp_path):
    path = build_filepath("deep learning", str(tmp_path))
    assert path.suffix == ".jsonl"


def test_filepath_starts_at_00_when_empty(tmp_path):
    path = build_filepath("query", str(tmp_path))
    assert path.name.startswith("00_")


def test_filepath_contains_slug(tmp_path):
    path = build_filepath("deep learning nlp", str(tmp_path))
    assert "deep_learning_nlp" in path.name


# --- sequential index across saves ---

def test_sequential_index_increments(tmp_path):
    p1 = save_articles([make_article()], "query one", str(tmp_path))
    p2 = save_articles([make_article()], "query two", str(tmp_path))
    p3 = save_articles([make_article()], "query three", str(tmp_path))
    assert p1.name.startswith("00_")
    assert p2.name.startswith("01_")
    assert p3.name.startswith("02_")


def test_sequential_index_different_queries(tmp_path):
    p1 = save_articles([make_article()], "machine learning", str(tmp_path))
    p2 = save_articles([make_article()], "deep learning", str(tmp_path))
    assert p1.name.startswith("00_")
    assert p2.name.startswith("01_")


# --- save_articles ---

def test_save_creates_file(tmp_path):
    path = save_articles([make_article(title="Art 1")], "test query", str(tmp_path))
    assert path.exists()


def test_save_one_line_per_article(tmp_path):
    articles = [make_article(title=f"Art {i}") for i in range(3)]
    path = save_articles(articles, "test query", str(tmp_path))
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3


def test_save_valid_json_lines(tmp_path):
    articles = [make_article(title="Valid JSON Article")]
    path = save_articles(articles, "test query", str(tmp_path))
    for line in path.read_text(encoding="utf-8").strip().splitlines():
        obj = json.loads(line)
        assert obj["title"] == "Valid JSON Article"


def test_save_creates_parent_dirs(tmp_path):
    path = save_articles([make_article()], "query", str(tmp_path / "nested" / "deep"))
    assert path.exists()


def test_save_empty_list(tmp_path):
    path = save_articles([], "empty query", str(tmp_path))
    assert path.exists()
    assert path.read_text(encoding="utf-8") == ""
