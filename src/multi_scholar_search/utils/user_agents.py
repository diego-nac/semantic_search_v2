import random

import requests

from ..config import settings

_cache: list[str] = []


def _fetch_user_agents(url: str) -> list[str]:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return [line.strip() for line in response.text.splitlines() if line.strip()]


def get_random(url: str | None = None) -> str:
    global _cache
    if not _cache:
        _cache = _fetch_user_agents(url or settings.user_agents_url)
    return random.choice(_cache)


def parse_user_agents(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]
