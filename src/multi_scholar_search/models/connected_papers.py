from .base import BaseArticle


class ConnectedPapersArticle(BaseArticle):
    paper_id: str | None = None
    snippet: str | None = None
    abstract: str | None = None
    venue: str | None = None
    reference_count: int | None = None
    citation_count: int | None = None
    is_open_access: bool | None = None
    fields_of_study: list[str] | None = None
    tldr: str | None = None
    source: str = "connected_papers"
