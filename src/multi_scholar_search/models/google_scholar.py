from .base import BaseArticle


class ScholarArticle(BaseArticle):
    article_id: str | None = None
    snippet: str | None = None
    cited_link: str | None = None
    versions_count: str | None = None
    versions_link: str | None = None
    source: str = "google_scholar"
