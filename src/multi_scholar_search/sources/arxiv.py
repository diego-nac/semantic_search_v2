"""arXiv source — direct HTTPS API calls via httpx + feedparser."""
import asyncio
import logging
from datetime import datetime, timezone
from types import SimpleNamespace
from urllib.parse import quote

import httpx

from ..models.arxiv import ArxivArticle

log = logging.getLogger("mss.arxiv")

_BASE = "https://export.arxiv.org/api/query"
_PAGE_SIZE = 50
_MAX_LIMIT = 300
_INTER_PAGE_DELAY = 1.0


def _parse_result(result, query: str) -> ArxivArticle | None:
    try:
        title = (result.title or "").strip()
        if not title:
            return None

        authors_list = [a.name for a in (result.authors or []) if a.name]
        authors = ", ".join(authors_list) or None

        year = result.published.year if result.published else None

        doi = result.doi or None

        pdf_url = getattr(result, "pdf_url", None) or None

        category = None
        if hasattr(result, "primary_category") and result.primary_category:
            category = getattr(result.primary_category, "term", None)

        return ArxivArticle(
            title=title,
            title_link=result.entry_id,
            authors=authors,
            year=year,
            doi=doi,
            pdf_link=pdf_url,
            abstract=(result.summary or "").strip() or None,
            category=category,
            query=query,
        )
    except Exception as exc:
        log.warning("Skipping malformed arXiv result: %s", exc.__class__.__name__)
        return None


def _feed_entry_to_ns(entry: dict) -> SimpleNamespace:
    """Convert a feedparser entry dict into a SimpleNamespace matching arxiv.Result API."""
    import feedparser  # noqa: F401 — already a dep of arxiv package

    title = entry.get("title", "").replace("\n", " ").strip()
    summary = entry.get("summary", "").replace("\n", " ").strip()
    entry_id = entry.get("id", "")

    # Published date
    published = None
    pub_parsed = entry.get("published_parsed")
    if pub_parsed:
        try:
            published = datetime(*pub_parsed[:6], tzinfo=timezone.utc)
        except Exception:
            pass

    # Authors
    authors = [
        SimpleNamespace(name=a.get("name", ""))
        for a in entry.get("authors", [])
    ]

    # DOI
    doi = None
    for link in entry.get("links", []):
        if link.get("title") == "doi":
            doi = link.get("href", "").replace("https://doi.org/", "")
            break
    # Also try arxiv_doi tag
    if not doi:
        doi = entry.get("arxiv_doi") or None

    # PDF link
    pdf_url = None
    for link in entry.get("links", []):
        if link.get("type") == "application/pdf":
            pdf_url = link.get("href")
            break
    if not pdf_url and entry_id:
        pdf_url = entry_id.replace("/abs/", "/pdf/")

    # Primary category
    primary_category = None
    tags = entry.get("tags", [])
    if tags:
        primary_category = SimpleNamespace(term=tags[0].get("term", ""))

    return SimpleNamespace(
        entry_id=entry_id,
        title=title,
        summary=summary,
        published=published,
        authors=authors,
        doi=doi,
        pdf_url=pdf_url,
        primary_category=primary_category,
    )


def _search_sync(query: str, limit: int) -> list[ArxivArticle]:
    import feedparser

    articles: list[ArxivArticle] = []
    start = 0

    with httpx.Client(timeout=30, follow_redirects=True) as client:
        while len(articles) < limit:
            batch = min(_PAGE_SIZE, limit - len(articles))
            url = (
                f"{_BASE}?search_query=all:{quote(query)}"
                f"&sortBy=relevance&sortOrder=descending"
                f"&start={start}&max_results={batch}"
            )
            try:
                resp = client.get(url)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                log.error("arXiv request failed: %s", exc)
                break

            feed = feedparser.parse(resp.text)
            entries = feed.get("entries", [])
            if not entries:
                break

            for entry in entries:
                if len(articles) >= limit:
                    break
                ns = _feed_entry_to_ns(entry)
                article = _parse_result(ns, query)
                if article:
                    articles.append(article)

            log.info("arXiv: fetched %d/%d results (start=%d)", len(articles), limit, start)

            if len(entries) < batch:
                break  # no more results
            start += batch
            if start > 0 and len(articles) < limit:
                import time
                time.sleep(_INTER_PAGE_DELAY)

    return articles


async def search_async(query: str, limit: int = 10) -> list[ArxivArticle]:
    limit = min(limit, _MAX_LIMIT)
    loop = asyncio.get_event_loop()
    articles = await loop.run_in_executor(None, _search_sync, query, limit)
    if not articles:
        log.warning("arXiv returned 0 results")
    return articles[:limit]


def search(query: str, limit: int = 10) -> list[ArxivArticle]:
    return asyncio.run(search_async(query, limit))
