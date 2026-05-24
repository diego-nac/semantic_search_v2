import os

import pytest

from multi_scholar_search.config import Settings


def test_default_base_url():
    s = Settings()
    assert s.google_scholar_base_url == "https://scholar.google.com/scholar"


def test_default_save_results_is_false(monkeypatch):
    monkeypatch.delenv("SAVE_RESULTS", raising=False)
    s = Settings(_env_file=None)
    assert s.save_results is False


def test_default_data_dir():
    s = Settings()
    assert s.data_dir == "data"


def test_save_results_from_env(monkeypatch):
    monkeypatch.setenv("SAVE_RESULTS", "true")
    s = Settings()
    assert s.save_results is True


def test_custom_base_url_from_env(monkeypatch):
    monkeypatch.setenv("GOOGLE_SCHOLAR_BASE_URL", "https://custom.example.com/scholar")
    s = Settings()
    assert s.google_scholar_base_url == "https://custom.example.com/scholar"


def test_language_default():
    s = Settings()
    assert s.google_scholar_language == "en"


def test_proxy_default_is_none(monkeypatch):
    monkeypatch.delenv("CHROMIUM_PROXY", raising=False)
    s = Settings(_env_file=None)
    assert s.chromium_proxy is None


def test_proxy_from_env(monkeypatch):
    monkeypatch.setenv("CHROMIUM_PROXY", "http://user:pass@proxy.example.com:8080")
    s = Settings(_env_file=None)
    assert s.chromium_proxy == "http://user:pass@proxy.example.com:8080"


def test_proxy_socks5_from_env(monkeypatch):
    monkeypatch.setenv("CHROMIUM_PROXY", "socks5://proxy.example.com:1080")
    s = Settings(_env_file=None)
    assert s.chromium_proxy == "socks5://proxy.example.com:1080"
