"""Connected Papers source.

Strategy:
  Primary:  Playwright browser → intercept XHR to /search/{query}/{page}
            (10 results/page, unlimited pages, requires browser session)
  Detail:   GET /paper/{s2_id} via httpx (no auth needed — richer data)
  Fallback: Direct httpx with session cookies captured from browser
"""
import asyncio
import logging
import time
from urllib.parse import quote

import httpx

from ..models.connected_papers import ConnectedPapersArticle

log = logging.getLogger("mss.connected_papers")

_REST_BASE = "https://rest.prod.connectedpapers.com"
_PAGE_SIZE = 10
_MAX_LIMIT = 500
_MAX_RETRIES = 4
_BACKOFF_BASE = 2.0
_INTER_PAGE_DELAY = 1.5

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.connectedpapers.com/",
    "Origin": "https://www.connectedpapers.com",
}


# ── Parsers ──────────────────────────────────────────────────────────────────

def _parse_search_result(raw: dict, query: str) -> ConnectedPapersArticle | None:
    try:
        title = (raw.get("title") or {}).get("text") or ""
        if not title:
            return None

        paper_id = raw.get("id")
        s2_url = f"https://www.semanticscholar.org/paper/{paper_id}" if paper_id else None

        year_raw = (raw.get("year") or {}).get("text")
        try:
            year = int(year_raw) if year_raw else None
        except (ValueError, TypeError):
            year = None

        authors_nested = raw.get("authors") or []
        names = []
        for group in authors_nested:
            if isinstance(group, list):
                for a in group:
                    n = a.get("name")
                    if n:
                        names.append(n)
            elif isinstance(group, dict):
                n = group.get("name")
                if n:
                    names.append(n)
        authors = ", ".join(names) or None

        doi_info = raw.get("doiInfo") or {}
        doi = doi_info.get("doi") or None

        stats = raw.get("citationStats") or {}
        cited_count = stats.get("numCitations")
        cited_str = f"Cited by {cited_count}" if cited_count is not None else None
        ref_count = stats.get("numReferences")

        abstract_obj = raw.get("paperAbstract") or {}
        snippet = abstract_obj.get("text") or None

        return ConnectedPapersArticle(
            paper_id=paper_id,
            title=title,
            title_link=s2_url,
            authors=authors,
            year=year,
            doi=doi,
            snippet=snippet,
            citation_count=cited_count,
            cited_by_count=cited_str,
            reference_count=ref_count,
            query=query,
        )
    except Exception as exc:
        log.warning("Skipping malformed search result: %s", exc.__class__.__name__)
        return None


def _parse_paper_detail(raw: dict, query: str) -> ConnectedPapersArticle | None:
    try:
        title = raw.get("title") or ""
        if not title:
            return None

        paper_id = raw.get("id")
        s2_url = raw.get("s2Url") or (
            f"https://www.semanticscholar.org/paper/{paper_id}" if paper_id else None
        )

        authors_list = raw.get("authors") or []
        authors = ", ".join(a.get("name", "") for a in authors_list if a.get("name")) or None

        pdf_urls = raw.get("pdfUrls") or []
        pdf_link = pdf_urls[0] if pdf_urls else None

        tldr_obj = raw.get("tldr") or {}
        tldr = tldr_obj.get("text") or None if isinstance(tldr_obj, dict) else None

        cited_count = raw.get("citationCount")
        cited_str = f"Cited by {cited_count}" if cited_count is not None else None

        return ConnectedPapersArticle(
            paper_id=paper_id,
            title=title,
            title_link=s2_url,
            authors=authors,
            year=raw.get("year"),
            doi=raw.get("doi"),
            pdf_link=pdf_link,
            abstract=raw.get("paperAbstract"),
            venue=raw.get("venue"),
            citation_count=cited_count,
            cited_by_count=cited_str,
            reference_count=raw.get("referenceCount"),
            is_open_access=raw.get("isOpenAccess"),
            fields_of_study=raw.get("fieldsOfStudy"),
            tldr=tldr,
            query=query,
        )
    except Exception as exc:
        log.warning("Skipping malformed paper detail: %s", exc.__class__.__name__)
        return None


# ── HTTP fetch (with cookies from browser session) ───────────────────────────

def _fetch_page_sync(
    query: str,
    page: int,
    cookies: dict,
) -> list[ConnectedPapersArticle]:
    """Fetch one search page with retry/backoff. Cookies must come from a live browser session."""
    url = f"{_REST_BASE}/search/{quote(query)}/{page}"
    delay = _BACKOFF_BASE

    for attempt in range(1, _MAX_RETRIES + 2):
        try:
            resp = httpx.get(
                url,
                headers=_HEADERS,
                cookies=cookies,
                timeout=15,
                follow_redirects=True,
            )
        except Exception as exc:
            log.warning("Request failed (attempt %d): %s", attempt, exc.__class__.__name__)
            if attempt <= _MAX_RETRIES:
                time.sleep(delay)
                delay *= 2
            continue

        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results") or []
            articles = [_parse_search_result(r, query) for r in results]
            return [a for a in articles if a is not None]

        if resp.status_code == 429:
            if attempt <= _MAX_RETRIES:
                log.warning("Rate limited (429), waiting %.0fs before retry %d...", delay, attempt + 1)
                time.sleep(delay)
                delay *= 2
            else:
                log.error("Rate limited after %d retries", _MAX_RETRIES)
            continue

        log.warning("Status %d for page=%d, stopping", resp.status_code, page)
        break

    return []


def _fetch_paper_detail_sync(paper_id: str, query: str) -> ConnectedPapersArticle | None:
    """Fetch full paper details — no auth required."""
    url = f"{_REST_BASE}/paper/{paper_id}"
    try:
        resp = httpx.get(url, headers=_HEADERS, timeout=15)
        if resp.status_code == 200:
            return _parse_paper_detail(resp.json(), query)
    except Exception as exc:
        log.warning("Paper detail fetch failed for %s: %s", paper_id, exc.__class__.__name__)
    return None


# ── Browser-based search (primary) ───────────────────────────────────────────

async def _search_via_browser(query: str, limit: int) -> list[ConnectedPapersArticle]:
    """Use Playwright to intercept XHR calls from the Connected Papers SPA."""
    from playwright.async_api import async_playwright

    all_articles: list[ConnectedPapersArticle] = []
    captured_cookies: dict = {}
    pages_needed = (limit + _PAGE_SIZE - 1) // _PAGE_SIZE

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            user_agent=_HEADERS["User-Agent"],
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = await context.new_page()

        search_pages_captured: dict[int, list] = {}

        async def on_response(response):
            url = response.url
            if "rest.prod.connectedpapers.com/search/" in url and response.status == 200:
                # extract page number from URL: /search/{query}/{page}
                parts = url.rstrip("/").split("/")
                try:
                    pg = int(parts[-1])
                except ValueError:
                    pg = 1
                try:
                    body = await response.json()
                    results = body.get("results") or []
                    articles = [_parse_search_result(r, query) for r in results]
                    search_pages_captured[pg] = [a for a in articles if a is not None]
                    log.info("Intercepted page %d: %d results (total=%s)", pg, len(results), body.get("totalResults"))
                except Exception as exc:
                    log.warning("Failed to parse intercepted page %d: %s", pg, exc.__class__.__name__)

        page.on("response", on_response)

        # Navigate and trigger page 1
        log.info("Navigating to Connected Papers for query: %r", query)
        await page.goto("https://www.connectedpapers.com", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(1)

        inp = await page.query_selector("input:visible")
        if inp:
            await inp.fill(query)
            await page.keyboard.press("Enter")
            log.info("Search submitted via input field")
        else:
            log.warning("Search input not found, trying URL navigation")
            await page.goto(
                f"https://www.connectedpapers.com/search?q={quote(query)}",
                wait_until="networkidle",
                timeout=30000,
            )

        await asyncio.sleep(4)

        # Collect cookies for direct API calls on subsequent pages
        cookies_list = await context.cookies()
        captured_cookies = {c["name"]: c["value"] for c in cookies_list}

        # Collect page 1 results
        if 1 in search_pages_captured:
            all_articles.extend(search_pages_captured[1])
            log.info("Page 1: %d articles (total so far: %d)", len(search_pages_captured[1]), len(all_articles))

        # For pages 2+, click the "Next" button or page number buttons
        for pg in range(2, pages_needed + 1):
            if len(all_articles) >= limit:
                break
            await asyncio.sleep(_INTER_PAGE_DELAY)

            # Try clicking "Next" button first, then specific page number
            clicked = False
            for sel in [f"a:text-is('{pg}')", "a:text-is('Next')", "button:text-is('Next')"]:
                try:
                    elem = await page.query_selector(sel)
                    if elem and await elem.is_visible():
                        await elem.click()
                        await asyncio.sleep(3)
                        clicked = True
                        log.info("Clicked pagination element for page %d", pg)
                        break
                except Exception:
                    pass

            if not clicked:
                log.warning("Could not find pagination control for page %d, stopping", pg)
                break

            if pg in search_pages_captured:
                page_articles = search_pages_captured[pg]
                all_articles.extend(page_articles)
                log.info("Page %d: %d articles (total: %d/%d)", pg, len(page_articles), len(all_articles), limit)
            else:
                log.warning("Page %d XHR not captured after click, stopping", pg)
                break

        await browser.close()

    return all_articles


# ── Public API ────────────────────────────────────────────────────────────────

async def search_async(query: str, limit: int = 10) -> list[ConnectedPapersArticle]:
    limit = min(limit, _MAX_LIMIT)
    articles = await _search_via_browser(query, limit)

    if not articles:
        log.warning("Connected Papers returned 0 results")

    return articles[:limit]


def search(query: str, limit: int = 10) -> list[ConnectedPapersArticle]:
    return asyncio.run(search_async(query, limit))
