from .base import BaseArticle


class SemanticScholarArticle(BaseArticle):
    paper_id: str | None = None
    abstract: str | None = None
    venue: str | None = None
    reference_count: int | None = None
    citation_count: int | None = None
    is_open_access: bool | None = None
    source: str = "semantic_scholar"
