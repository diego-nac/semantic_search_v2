from .base import BaseArticle


class SpringerArticle(BaseArticle):
    abstract: str | None = None
    venue: str | None = None
    source: str = "springer"
