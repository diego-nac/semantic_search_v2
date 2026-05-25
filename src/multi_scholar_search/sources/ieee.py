"""IEEE Xplore source — intercepts XHR from the search SPA via Playwright."""
import asyncio
import logging
import re
from urllib.parse import quote

from ..models.ieee import IEEEArticle

log = logging.getLogger("mss.ieee")

_BASE = "https://ieeexplore.ieee.org"
_PAGE_SIZE = 25
_MAX_LIMIT = 200
_INTER_PAGE_DELAY = 2.0

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://ieeexplore.ieee.org/",
}


def _parse_result(raw: dict, query: str) -> IEEEArticle | None:
    try:
        title = (raw.get("articleTitle") or raw.get("title") or "").strip()
        if not title:
            return None

        article_number = str(raw.get("articleNumber") or raw.get("arnumber") or "")
        doc_link = raw.get("documentLink") or ""
        if doc_link and not doc_link.startswith("http"):
            doc_link = f"{_BASE}{doc_link}"
        title_link = doc_link or (f"{_BASE}/document/{article_number}/" if article_number else None)

        authors_raw = raw.get("authors") or []
        if isinstance(authors_raw, list):
            authors_list = authors_raw
        elif isinstance(authors_raw, dict):
            authors_list = authors_raw.get("authors") or []
        else:
            authors_list = []
        names = [
            a.get("preferredName") or a.get("full_name") or a.get("name", "")
            for a in authors_list if isinstance(a, dict)
        ]
        authors = ", ".join(n for n in names if n) or None

        year_raw = raw.get("publicationYear") or raw.get("year")
        try:
            year = int(year_raw) if year_raw else None
        except (ValueError, TypeError):
            year = None

        doi = raw.get("doi") or None
        if doi == "":
            doi = None

        cited_count = raw.get("citationCount")
        if cited_count is None:
            cited_count = raw.get("citations")
        try:
            cited_count = int(cited_count) if cited_count is not None else None
        except (ValueError, TypeError):
            cited_count = None
        cited_str = f"Cited by {cited_count}" if cited_count is not None else None

        abstract = (raw.get("abstract") or raw.get("abstractText") or "").strip() or None
        venue = raw.get("publicationTitle") or raw.get("displayPublicationTitle") or raw.get("publisher") or None

        # PDF link
        pdf_path = raw.get("pdfLink") or raw.get("pdfPath") or None
        pdf_link = f"{_BASE}{pdf_path}" if pdf_path and not pdf_path.startswith("http") else pdf_path

        return IEEEArticle(
            title=title,
            title_link=title_link,
            authors=authors,
            year=year,
            doi=doi,
            pdf_link=pdf_link,
            abstract=abstract,
            venue=venue,
            citation_count=cited_count,
            cited_by_count=cited_str,
            query=query,
        )
    except Exception as exc:
        log.warning("Skipping malformed IEEE result: %s", exc.__class__.__name__)
        return None


async def _search_via_browser(query: str, limit: int) -> list[IEEEArticle]:
    """Intercept IEEE Xplore XHR API calls via Playwright."""
    from playwright.async_api import async_playwright

    all_articles: list[IEEEArticle] = []
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
        captured: dict[int, list] = {}

        async def on_response(response):
            url = response.url
            if "ieeexplore.ieee.org/rest/search" in url and response.status == 200:
                try:
                    body = await response.json()
                    records = body.get("records") or body.get("articles") or []
                    pg_num = body.get("currentPageNumber", 1)
                    parsed = [_parse_result(r, query) for r in records]
                    captured[pg_num] = [a for a in parsed if a is not None]
                    log.info("IEEE XHR page %d: %d results (total=%s)", pg_num, len(records), body.get("totalRecords"))
                except Exception as exc:
                    log.warning("Failed parsing IEEE XHR: %s", exc.__class__.__name__)

        page.on("response", on_response)

        search_url = (
            f"{_BASE}/search/searchresult.jsp"
            f'?queryText={quote(query)}'
            f"&newsearch=true&pageNumber=1&rowsPerPage={_PAGE_SIZE}"
        )
        log.info("Navigating to IEEE Xplore for query: %r", query)
        try:
            await page.goto(search_url, wait_until="networkidle", timeout=30000)
        except Exception:
            await asyncio.sleep(3)

        await asyncio.sleep(3)

        if 1 in captured:
            all_articles.extend(captured[1])
            log.info("IEEE page 1: %d articles", len(all_articles))

        # Additional pages
        for pg in range(2, pages_needed + 1):
            if len(all_articles) >= limit:
                break
            await asyncio.sleep(_INTER_PAGE_DELAY)
            next_url = (
                f"{_BASE}/search/searchresult.jsp"
                f'?queryText={quote(query)}'
                f"&newsearch=true&pageNumber={pg}&rowsPerPage={_PAGE_SIZE}"
            )
            try:
                await page.goto(next_url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(3)
            except Exception as exc:
                log.warning("IEEE page %d navigation failed: %s", pg, exc.__class__.__name__)
                break

            if pg in captured:
                all_articles.extend(captured[pg])
                log.info("IEEE page %d: %d articles (total: %d)", pg, len(captured[pg]), len(all_articles))
            else:
                log.warning("IEEE page %d: no XHR captured, stopping", pg)
                break

        await browser.close()

    return all_articles


async def search_async(query: str, limit: int = 10) -> list[IEEEArticle]:
    limit = min(limit, _MAX_LIMIT)
    articles = await _search_via_browser(query, limit)
    if not articles:
        log.warning("IEEE Xplore returned 0 results")
    return articles[:limit]


def search(query: str, limit: int = 10) -> list[IEEEArticle]:
    return asyncio.run(search_async(query, limit))
