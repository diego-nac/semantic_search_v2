from .base import BaseArticle


class ArxivArticle(BaseArticle):
    abstract: str | None = None
    category: str | None = None
    source: str = "arxiv"
