from .base import BaseArticle


class IEEEArticle(BaseArticle):
    abstract: str | None = None
    venue: str | None = None
    citation_count: int | None = None
    source: str = "ieee"
