from datetime import datetime, timezone
from pydantic import BaseModel, Field


class BaseArticle(BaseModel):
    title: str
    title_link: str | None = None
    authors: str | None = None
    year: int | None = None
    cited_by_count: str | None = None
    doi: str | None = None
    bibtex: str | None = None
    pdf_link: str | None = None
    source: str
    query: str
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
