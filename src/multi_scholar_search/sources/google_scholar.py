import asyncio
import logging
import math
import re
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from ..config import settings
from ..models.google_scholar import ScholarArticle
from ..utils.browser_client import BrowserClient

log = logging.getLogger("mss.google_scholar")

RESULTS_PER_PAGE = 10
MAX_LIMIT = 50


def _build_url(query: str, start: int = 0) -> str:
    params = {
        "as_q": query,
        "hl": settings.google_scholar_language,
        "as_sdt": "0,5",
        "num": RESULTS_PER_PAGE,
        "start": start,
    }
    return f"{settings.google_scholar_base_url}?{urlencode(params)}"


def _clean(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    text = text.replace("–", "-").replace("—", "-")
    text = text.replace("…", "...").replace("·", ".")
    text = text.replace(" ", " ").replace(" ", " ")
    return text.strip()


def _parse_results(soup: BeautifulSoup | str, query: str) -> list[ScholarArticle]:
    if isinstance(soup, str):
        soup = BeautifulSoup(soup, "html.parser")

    articles = []
    for result in soup.find_all("div", {"class": "gs_ri"}):
        try:
            title_elem = result.find("h3", {"class": "gs_rt"})
            link_elem = title_elem.find("a") if title_elem else None
            title = _clean(link_elem.get_text()) if link_elem else (
                _clean(title_elem.get_text()) if title_elem else None
            )
            link = link_elem.get("href", "") if link_elem else ""
            article_id = link_elem.get("id") if link_elem else None
            if not title:
                continue

            meta = result.find("div", {"class": "gs_a"})
            authors = None
            year = None
            if meta:
                meta_text = meta.get_text()
                parts = meta_text.split(" - ")
                if parts:
                    authors = _clean(parts[0])
                year_match = re.search(r"\b(19|20)\d{2}\b", meta_text)
                if year_match:
                    year = int(year_match.group())

            abstract_elem = result.find("div", {"class": "gs_rs"})
            snippet = _clean(abstract_elem.get_text()) if abstract_elem else None

            cited_by_count = cited_link = versions_count = versions_link = None
            fl_div = result.find("div", {"class": "gs_fl"})
            if fl_div:
                for a in fl_div.find_all("a"):
                    text = _clean(a.get_text(separator=" "))
                    href = a.get("href", "")
                    base = "https://scholar.google.com"
                    if "cited by" in text.lower():
                        digits = "".join(re.findall(r"\d+", text))
                        cited_by_count = f"Cited by {digits}" if digits else "N/A"
                        cited_link = base + href if href.startswith("/") else href
                    elif "version" in text.lower():
                        versions_count = text
                        versions_link = base + href if href.startswith("/") else href

            articles.append(ScholarArticle(
                title=title,
                title_link=link or None,
                article_id=article_id,
                authors=authors,
                year=year,
                snippet=snippet,
                cited_by_count=cited_by_count,
                cited_link=cited_link,
                versions_count=versions_count,
                versions_link=versions_link,
                query=query,
            ))
        except Exception as exc:
            log.warning("Skipping malformed result: %s", exc)

    return articles


# ---------------------------------------------------------------------------
# scholarly fallback — used when browser scraping returns 0 results
# ---------------------------------------------------------------------------

def _pub_to_article(pub: dict, query: str) -> ScholarArticle | None:
    try:
        bib = pub.get("bib", {})
        title = bib.get("title") or pub.get("title")
        if not title:
            return None

        authors_list = bib.get("author", [])
        authors = ", ".join(authors_list) if isinstance(authors_list, list) else str(authors_list)

        cited_by = pub.get("num_citations")
        cited_str = f"Cited by {cited_by}" if cited_by is not None else None

        eprint = pub.get("eprint_url") or pub.get("pub_url")

        raw_year = bib.get("pub_year")
        try:
            year = int(raw_year) if raw_year else None
        except (ValueError, TypeError):
            year = None

        return ScholarArticle(
            title=title,
            title_link=pub.get("pub_url"),
            authors=authors or None,
            year=year,
            snippet=bib.get("abstract"),
            cited_by_count=cited_str,
            cited_link=pub.get("citedby_url"),
            doi=pub.get("doi"),
            pdf_link=eprint,
            query=query,
        )
    except Exception as exc:
        log.warning("Skipping malformed scholarly result: %s", exc.__class__.__name__)
        return None


def _scholarly_search_sync(query: str, limit: int) -> list[ScholarArticle]:
    from scholarly import scholarly as _scholarly
    articles: list[ScholarArticle] = []
    try:
        log.info("scholarly fallback: searching for %r", query)
        results = _scholarly.search_pubs(query)
        for pub in results:
            if len(articles) >= limit:
                break
            article = _pub_to_article(pub, query)
            if article:
                articles.append(article)
                log.info("scholarly: fetched %d/%d", len(articles), limit)
    except Exception as exc:
        log.error("scholarly fallback failed: %s", exc.__class__.__name__)
    return articles


# ---------------------------------------------------------------------------
# Browser scraping (primary)
# ---------------------------------------------------------------------------

async def _fetch_page_once(client: BrowserClient, url: str, query: str, page: int) -> list[ScholarArticle]:
    loop = asyncio.get_event_loop()

    try:
        soup = await loop.run_in_executor(None, client.fetch_with_drission, url)
        articles = _parse_results(soup, query)
        if articles:
            log.info("Page %d: DrissionPage returned %d results", page, len(articles))
            return articles
        log.warning("Page %d: DrissionPage returned 0 results, trying Playwright", page)
    except Exception as exc:
        log.warning("Page %d: DrissionPage failed (%s), trying Playwright", page, exc.__class__.__name__)

    pw_client = BrowserClient()
    try:
        await pw_client.start()
        await pw_client.goto(url)
        await asyncio.sleep(settings.drission_settle_time)
        soup = await pw_client.get_content()
        articles = _parse_results(soup, query)
        log.info("Page %d: Playwright returned %d results", page, len(articles))
        return articles
    except Exception as exc:
        log.error("Page %d: Playwright fallback failed (%s)", page, exc.__class__.__name__)
        return []
    finally:
        try:
            await pw_client.close()
        except Exception:
            pass


async def _fetch_page(client: BrowserClient, url: str, query: str, page: int) -> list[ScholarArticle]:
    for attempt in range(1, settings.page_retries + 2):
        articles = await _fetch_page_once(client, url, query, page)
        if articles:
            return articles
        if attempt <= settings.page_retries:
            wait = attempt * 5
            log.warning("Page %d attempt %d returned 0 results, retrying in %ds...", page, attempt, wait)
            await asyncio.sleep(wait)
    return []


async def search_async(query: str, limit: int = 10) -> list[ScholarArticle]:
    limit = min(limit, MAX_LIMIT)
    log.info("Fetching up to %d results via scholarly", limit)

    loop = asyncio.get_event_loop()
    all_articles = await loop.run_in_executor(None, _scholarly_search_sync, query, limit)

    # If scholarly yielded nothing, fall back to browser scraping
    if not all_articles:
        log.warning("scholarly returned 0 results — falling back to browser scraping")
        pages_needed = math.ceil(limit / RESULTS_PER_PAGE)
        client = BrowserClient()

        for page in range(pages_needed):
            start = page * RESULTS_PER_PAGE
            url = _build_url(query, start=start)
            page_articles = await _fetch_page(client, url, query, page + 1)

            if not page_articles:
                log.warning("Page %d returned no results, stopping pagination", page + 1)
                break

            all_articles.extend(page_articles)
            log.info("Total so far: %d/%d", len(all_articles), limit)

            if len(all_articles) >= limit:
                break

            if page < pages_needed - 1 and settings.page_delay > 0:
                await asyncio.sleep(settings.page_delay)

    return all_articles[:limit]


def search(query: str, limit: int = 10) -> list[ScholarArticle]:
    return asyncio.run(search_async(query, limit))
