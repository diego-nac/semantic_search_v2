"""Semantic Scholar source — uses the public Graph API (no key required).

Strategy:
  Primary:  GET /graph/v1/paper/search with exponential backoff on 429
  Fallback: Playwright browser (SPA — BeautifulSoup alone won't work)
"""
import asyncio
import logging
import time

import httpx

from ..models.semantic_scholar import SemanticScholarArticle

log = logging.getLogger("mss.semantic_scholar")

_BASE = "https://api.semanticscholar.org/graph/v1"
_FIELDS = ",".join([
    "title", "authors", "year", "citationCount", "referenceCount",
    "externalIds", "openAccessPdf", "abstract", "venue", "isOpenAccess",
    "publicationDate",
])
_PAGE_SIZE = 10
_MAX_LIMIT = 50
_MAX_RETRIES = 6          # backoff sequence: 2, 4, 8, 16, 32, 64 s
_BACKOFF_BASE = 2.0
_INTER_PAGE_DELAY = 1.0  # seconds between sequential page requests
_HEADERS = {
    "User-Agent": "multi-scholar-search/0.1 (melo@pumpkinlabs.io)",
}


def _parse_paper(raw: dict, query: str) -> SemanticScholarArticle | None:
    try:
        title = raw.get("title") or ""
        if not title:
            return None

        authors_list = raw.get("authors") or []
        authors = ", ".join(a.get("name", "") for a in authors_list) or None

        ext = raw.get("externalIds") or {}
        doi = ext.get("DOI")

        oa = raw.get("openAccessPdf") or {}
        pdf_url = oa.get("url") or None
        if pdf_url == "":
            pdf_url = None

        cited_count = raw.get("citationCount")
        cited_str = f"Cited by {cited_count}" if cited_count is not None else None

        paper_id = raw.get("paperId")
        paper_url = f"https://www.semanticscholar.org/paper/{paper_id}" if paper_id else None

        return SemanticScholarArticle(
            paper_id=paper_id,
            title=title,
            title_link=paper_url,
            authors=authors,
            year=raw.get("year"),
            doi=doi,
            pdf_link=pdf_url,
            abstract=raw.get("abstract"),
            venue=raw.get("venue"),
            citation_count=cited_count,
            cited_by_count=cited_str,
            reference_count=raw.get("referenceCount"),
            is_open_access=raw.get("isOpenAccess"),
            query=query,
        )
    except Exception as exc:
        log.warning("Skipping malformed paper: %s", exc.__class__.__name__)
        return None


def _fetch_page_sync(query: str, offset: int, limit: int) -> list[SemanticScholarArticle]:
    """Single page fetch with exponential backoff on 429."""
    params = {"query": query, "fields": _FIELDS, "limit": limit, "offset": offset}
    delay = _BACKOFF_BASE

    for attempt in range(1, _MAX_RETRIES + 2):
        try:
            resp = httpx.get(f"{_BASE}/paper/search", params=params, headers=_HEADERS, timeout=15)
        except Exception as exc:
            log.warning("API request failed (attempt %d): %s", attempt, exc.__class__.__name__)
            if attempt <= _MAX_RETRIES:
                time.sleep(delay)
                delay *= 2
            continue

        if resp.status_code == 200:
            data = resp.json().get("data") or []
            articles = [_parse_paper(p, query) for p in data]
            return [a for a in articles if a is not None]

        if resp.status_code == 429:
            if attempt <= _MAX_RETRIES:
                log.warning("Rate limited (429), waiting %.0fs before retry %d…", delay, attempt + 1)
                time.sleep(delay)
                delay *= 2
            else:
                log.error("Rate limited after %d retries, giving up on this page", _MAX_RETRIES)
            continue

        log.error("Unexpected status %d for offset=%d", resp.status_code, offset)
        break

    return []


async def _fetch_via_playwright(query: str, limit: int) -> list[SemanticScholarArticle]:
    """Browser fallback: intercept the XHR the SPA makes to the graph API."""
    from ..utils.browser_client import BrowserClient

    articles: list[SemanticScholarArticle] = []
    pw = BrowserClient()
    try:
        await pw.start()
        captured: list[dict] = []

        async def _on_response(response):
            if "/graph/v1/paper/search" in response.url and response.status == 200:
                try:
                    body = await response.json()
                    captured.extend(body.get("data") or [])
                except Exception:
                    pass

        pw.page.on("response", _on_response)
        url = f"https://www.semanticscholar.org/search?q={query.replace(' ', '+')}&sort=Relevance"
        await pw.goto(url)
        await asyncio.sleep(5)

        for raw in captured[:limit]:
            a = _parse_paper(raw, query)
            if a:
                articles.append(a)

        log.info("Playwright captured %d results from SPA XHR", len(articles))
    except Exception as exc:
        log.error("Playwright fallback failed: %s", exc.__class__.__name__)
    finally:
        try:
            await pw.close()
        except Exception:
            pass

    return articles


async def search_async(query: str, limit: int = 10) -> list[SemanticScholarArticle]:
    limit = min(limit, _MAX_LIMIT)
    loop = asyncio.get_event_loop()
    all_articles: list[SemanticScholarArticle] = []

    offsets = list(range(0, limit, _PAGE_SIZE))
    page_size = _PAGE_SIZE

    log.info("Fetching %d page(s) from Semantic Scholar API (sequential)", len(offsets))

    # Sequential to respect rate limits — concurrent causes immediate 429
    for i, off in enumerate(offsets):
        if len(all_articles) >= limit:
            break
        if i > 0:
            await asyncio.sleep(_INTER_PAGE_DELAY)
        page = await loop.run_in_executor(None, _fetch_page_sync, query, off, page_size)
        if not page:
            log.warning("Page at offset %d returned no results, stopping", off)
            break
        all_articles.extend(page)
        log.info("Total so far: %d/%d", len(all_articles), limit)

    if not all_articles:
        log.warning("API returned 0 results — trying Playwright browser fallback")
        all_articles = await _fetch_via_playwright(query, limit)

    return all_articles[:limit]


def search(query: str, limit: int = 10) -> list[SemanticScholarArticle]:
    return asyncio.run(search_async(query, limit))
