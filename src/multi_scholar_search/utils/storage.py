import re
from datetime import datetime, timezone
from pathlib import Path

from ..models.base import BaseArticle


def _slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "_", slug)
    return slug[:50]


def _next_index(folder: Path) -> int:
    if not folder.exists():
        return 0
    existing = [f for f in folder.iterdir() if f.suffix == ".jsonl"]
    return len(existing)


def build_filepath(query: str, data_dir: str, source: str = "google_scholar") -> Path:
    folder = Path(data_dir) / source
    index = _next_index(folder)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    slug = _slugify(query)
    filename = f"{index:02d}_{slug}_{timestamp}.jsonl"
    return folder / filename


def save_articles(articles: list[BaseArticle], query: str, data_dir: str) -> Path:
    source = articles[0].source if articles else "unknown"
    path = build_filepath(query, data_dir, source)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for article in articles:
            f.write(article.model_dump_json() + "\n")
    return path
