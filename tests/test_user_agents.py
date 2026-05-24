import pytest

from multi_scholar_search.utils.user_agents import parse_user_agents


SAMPLE = """\
Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36
Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15
Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36


Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)
"""


def test_parse_strips_blank_lines():
    result = parse_user_agents(SAMPLE)
    assert len(result) == 4


def test_parse_strips_whitespace():
    result = parse_user_agents(SAMPLE)
    for ua in result:
        assert ua == ua.strip()


def test_parse_empty_string():
    assert parse_user_agents("") == []


def test_parse_single_line():
    result = parse_user_agents("Mozilla/5.0 (Windows NT 10.0)")
    assert result == ["Mozilla/5.0 (Windows NT 10.0)"]


def test_parse_preserves_content():
    result = parse_user_agents(SAMPLE)
    assert "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)" in result


def test_get_random_returns_one_of_the_list(monkeypatch):
    from multi_scholar_search.utils import user_agents as ua_module

    agents = ["AgentA", "AgentB", "AgentC"]
    monkeypatch.setattr(ua_module, "_cache", agents)

    result = ua_module.get_random()
    assert result in agents


def test_get_random_different_on_multiple_calls(monkeypatch):
    from multi_scholar_search.utils import user_agents as ua_module

    agents = [f"Agent{i}" for i in range(50)]
    monkeypatch.setattr(ua_module, "_cache", agents)

    results = {ua_module.get_random() for _ in range(20)}
    assert len(results) > 1
