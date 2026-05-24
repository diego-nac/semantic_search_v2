"""DOI lookup (Crossref) → BibTeX (doi2bib) → PDF link (Unpaywall).

Works on any list of BaseArticle subclasses — source-agnostic.
Pipeline per article:
  1. Crossref API  → DOI  (skipped if article already has one)
  2. doi2bib API   → BibTeX entry
  3. Unpaywall API → open-access PDF link
"""
from __future__ import annotations

import asyncio
import logging
import re

import httpx
from doi2bib.crossref import get_bib as _doi2bib_get_bib
from habanero import Crossref

from ..models.base import BaseArticle

log = logging.getLogger("mss.doi")

_cr = Crossref(mailto="melo@pumpkinlabs.io")
_UNPAYWALL_URL = "https://api.unpaywall.org/v2/{doi}"
_UNPAYWALL_EMAIL = "melo@pumpkinlabs.io"


def _normalize(text: str) -> str:
    return re.sub(r"\W+", " ", text.lower()).strip()


def _lookup_doi(title: str) -> str | None:
    """Query Crossref by title; only accept if the top result title roughly matches."""
    try:
        result = _cr.works(query=title, limit=1)
        items = result.get("message", {}).get("items", [])
        if not items:
            return None
        item = items[0]
        doi = item.get("DOI")
        if not doi:
            return None
        # Basic sanity check: at least 3 words from query appear in the result title
        result_title = " ".join(item.get("title", []))
        query_words = set(_normalize(title).split())
        result_words = set(_normalize(result_title).split())
        overlap = query_words & result_words
        if len(overlap) < min(3, len(query_words)):
            log.debug("Crossref title mismatch for %r (overlap=%d)", title[:60], len(overlap))
            return None
        return doi
    except Exception as exc:
        log.debug("Crossref lookup failed for %r: %s", title[:60], exc)
        return None


def _fetch_bibtex(doi: str) -> str | None:
    """Fetch BibTeX via doi2bib package (uses doi.org content negotiation)."""
    try:
        found, bibtex = _doi2bib_get_bib(doi)
        if not found or not bibtex:
            log.debug("doi2bib: no entry for %s", doi)
            return None
        text = bibtex.strip()
        return text if text.startswith("@") else None
    except Exception as exc:
        log.debug("doi2bib failed for %s: %s", doi, exc)
        return None


def _fetch_pdf_link(doi: str) -> str | None:
    """Fetch open-access PDF URL from Unpaywall."""
    try:
        resp = httpx.get(
            _UNPAYWALL_URL.format(doi=doi),
            params={"email": _UNPAYWALL_EMAIL},
            timeout=10,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        best = resp.json().get("best_oa_location") or {}
        return best.get("url_for_pdf") or best.get("url") or None
    except Exception as exc:
        log.debug("Unpaywall failed for %s: %s", doi, exc)
        return None


def _enrich_one(article: BaseArticle) -> None:
    """Mutate article in-place: resolve DOI → BibTeX → PDF link."""
    doi = article.doi or _lookup_doi(article.title)
    if not doi:
        log.debug("No DOI found for: %s", article.title[:60])
        return

    article.doi = doi
    log.info("[doi] %s → %s", article.title[:50], doi)

    article.bibtex = _fetch_bibtex(doi)
    if article.bibtex:
        log.info("[bibtex] OK for %s", doi)
    else:
        log.debug("[bibtex] not found for %s", doi)

    if not article.pdf_link:
        article.pdf_link = _fetch_pdf_link(doi)
    if article.pdf_link:
        log.info("[pdf] %s → %s", doi, article.pdf_link)
    else:
        log.debug("[pdf] not found for %s", doi)


async def enrich_articles(articles: list[BaseArticle]) -> None:
    """Enrich all articles concurrently via thread pool (all HTTP calls are blocking)."""
    loop = asyncio.get_event_loop()
    await asyncio.gather(
        *[loop.run_in_executor(None, _enrich_one, a) for a in articles]
    )
