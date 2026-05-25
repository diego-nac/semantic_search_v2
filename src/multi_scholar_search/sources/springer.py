"""Springer Link source — Playwright browser scraping."""
import asyncio
import logging
import re
from urllib.parse import quote

from bs4 import BeautifulSoup

from ..models.springer import SpringerArticle

log = logging.getLogger("mss.springer")

_BASE = "https://link.springer.com"
_PAGE_SIZE = 20
_MAX_LIMIT = 200
_INTER_PAGE_DELAY = 2.0

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_DOI_RE = re.compile(r"10\.\d{4,}/[^\s\"'<>]+")


def _extract_doi(text: str) -> str | None:
    if not text:
        return None
    m = _DOI_RE.search(text)
    return m.group(0).rstrip(".,;)") if m else None


def _parse_result(item, query: str) -> SpringerArticle | None:
    try:
        title_tag = (
            item.find(["h2", "h3", "h4"], attrs={"data-test": "title"})
            or item.find(["h2", "h3", "h4"], class_=re.compile(r"title|heading"))
            or item.find("a", class_=re.compile(r"title|heading"))
        )
        if not title_tag:
            return None

        link_tag = title_tag.find("a") or title_tag
        title = link_tag.get_text(strip=True)
        if not title:
            return None

        href = link_tag.get("href", "")
        if href and not href.startswith("http"):
            href = f"{_BASE}{href}"
        title_link = href or None

        # DOI: try dedicated span, then extract from link
        doi_tag = item.find(class_=re.compile(r"doi"))
        doi = _extract_doi(doi_tag.get_text() if doi_tag else "") or _extract_doi(href)

        # Abstract
        abstract_tag = item.find(class_=re.compile(r"abstract|description|snippet"))
        abstract = abstract_tag.get_text(strip=True) if abstract_tag else None

        # Year
        year = None
        year_tag = item.find(class_=re.compile(r"year|date|pub"))
        if year_tag:
            m = re.search(r"\b(19|20)\d{2}\b", year_tag.get_text())
            if m:
                year = int(m.group())
        if not year and href:
            m = re.search(r"\b(19|20)\d{2}\b", href)
            if m:
                year = int(m.group())

        # Authors
        authors_tag = item.find(class_=re.compile(r"author"))
        authors = authors_tag.get_text(strip=True) if authors_tag else None

        # Venue
        venue_tag = item.find(class_=re.compile(r"publication|journal|venue"))
        venue = venue_tag.get_text(strip=True) if venue_tag else None

        return SpringerArticle(
            title=title,
            title_link=title_link,
            authors=authors,
            year=year,
            doi=doi,
            abstract=abstract,
            venue=venue,
            query=query,
        )
    except Exception as exc:
        log.warning("Skipping malformed Springer result: %s", exc.__class__.__name__)
        return None


def _parse_page(soup: BeautifulSoup, query: str) -> list[SpringerArticle]:
    items = (
        soup.find_all("li", class_=re.compile(r"search-result|result-item"))
        or soup.find_all("article")
        or soup.find_all("li", class_="app-card-open")
    )
    articles = [_parse_result(item, query) for item in items]
    return [a for a in articles if a is not None]


def _build_url(query: str, page: int = 1) -> str:
    return (
        f"{_BASE}/search"
        f"?query={quote(query)}"
        f"&page={page}"
        f"&sortBy=relevance"
    )


async def _search_via_browser(query: str, limit: int) -> list[SpringerArticle]:
    from playwright.async_api import async_playwright

    all_articles: list[SpringerArticle] = []
    pages_needed = (limit + _PAGE_SIZE - 1) // _PAGE_SIZE

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            user_agent=_UA,
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = await context.new_page()

        for pg in range(1, pages_needed + 1):
            if len(all_articles) >= limit:
                break
            if pg > 1:
                await asyncio.sleep(_INTER_PAGE_DELAY)

            url = _build_url(query, pg)
            log.info("Springer page %d: %s", pg, url)
            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(2)
            except Exception as exc:
                log.warning("Springer page %d failed: %s", pg, exc.__class__.__name__)
                break

            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")
            page_articles = _parse_page(soup, query)

            if not page_articles:
                log.warning("Springer page %d: 0 results, stopping", pg)
                break

            all_articles.extend(page_articles)
            log.info("Springer page %d: %d articles (total: %d/%d)", pg, len(page_articles), len(all_articles), limit)

        await browser.close()

    return all_articles


async def search_async(query: str, limit: int = 10) -> list[SpringerArticle]:
    limit = min(limit, _MAX_LIMIT)
    articles = await _search_via_browser(query, limit)
    if not articles:
        log.warning("Springer returned 0 results")
    return articles[:limit]


def search(query: str, limit: int = 10) -> list[SpringerArticle]:
    return asyncio.run(search_async(query, limit))
