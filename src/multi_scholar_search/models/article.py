from dataclasses import dataclass, field


@dataclass
class Article:
    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    abstract: str | None = None
    doi: str | None = None
    url: str | None = None
    source: str | None = None
    citations: int = 0
