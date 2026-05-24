import asyncio
import logging
import re
import sys
from enum import Enum
from typing import Optional
from urllib.parse import urlparse

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

app = typer.Typer()
console = Console(highlight=False)

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(console=console, show_path=False, markup=True)],
)
log = logging.getLogger("mss")


class Source(str, Enum):
    google_scholar = "google_scholar"
    scopus = "scopus"
    web_of_science = "web_of_science"
    semantic_scholar = "semantic_scholar"
    research_rabbit = "research_rabbit"
    connected_papers = "connected_papers"
    elicit = "elicit"
    scite = "scite"
    openalex = "openalex"


class SortOrder(str, Enum):
    citations = "citations"
    year = "year"
    relevance = "relevance"


ALL_SOURCES = [s for s in Source]

_NOT_IMPLEMENTED = {
    Source.scopus,
    Source.web_of_science,
    Source.research_rabbit,
    Source.elicit,
    Source.scite,
    Source.openalex,
}


def _citation_count(article) -> int:
    if article.cited_by_count:
        m = re.search(r"\d+", article.cited_by_count)
        return int(m.group()) if m else 0
    return 0


def _sort_articles(articles: list, order: SortOrder) -> list:
    if order == SortOrder.citations:
        return sorted(articles, key=lambda a: (-_citation_count(a), -(a.year or 0)))
    if order == SortOrder.year:
        return sorted(articles, key=lambda a: (-(a.year or 0), -_citation_count(a)))
    # relevance: keep original order from source
    return articles


def _print_results(articles: list) -> None:
    if not articles:
        console.print("  [dim]No results found.[/dim]\n")
        return

    table = Table(
        show_header=True,
        header_style="bold cyan",
        box=None,
        padding=(0, 1),
        expand=True,
    )
    table.add_column("#", style="dim", width=3, no_wrap=True)
    table.add_column("Title", min_width=30)
    table.add_column("Authors", min_width=20, style="green")
    table.add_column("Year", width=6, style="magenta", no_wrap=True)
    table.add_column("Cited by", width=10, style="yellow", no_wrap=True)
    table.add_column("DOI", width=22, style="cyan", no_wrap=True)
    table.add_column("Link", style="blue")

    for i, a in enumerate(articles, 1):
        cited = a.cited_by_count or "-"
        year = str(a.year) if a.year else "-"
        doi = a.doi or "-"
        if len(doi) > 22:
            doi = doi[:20] + "…"
        if a.title_link:
            parsed = urlparse(a.title_link)
            link_display = parsed.netloc.replace("www.", "") or a.title_link[:40]
        else:
            link_display = "-"
        table.add_row(str(i), a.title, a.authors or "-", year, cited, doi, link_display)

    console.print(table)
    console.print()


async def _run_source(
    source: Source,
    query: str,
    limit: int,
    sort: SortOrder,
    year_from: Optional[int],
    year_to: Optional[int],
    enrich: bool,
    save: bool,
) -> tuple[Source, list]:
    from .utils.storage import save_articles

    articles: list = []
    try:
        if source == Source.google_scholar:
            from .sources.google_scholar import search_async
            articles = await search_async(query, limit=limit)

        elif source == Source.semantic_scholar:
            from .sources.semantic_scholar import search_async
            articles = await search_async(query, limit=limit)

        elif source == Source.connected_papers:
            from .sources.connected_papers import search_async
            articles = await search_async(query, limit=limit)

        # Year filter
        if articles and (year_from or year_to):
            articles = [
                a for a in articles
                if (year_from is None or (a.year or 0) >= year_from)
                and (year_to is None or (a.year or 0) <= year_to)
            ]

        if articles and enrich:
            from .utils.doi_enricher import enrich_articles
            log.info("[%s] enriching %d article(s) with DOI/BibTeX/PDF…", source.value, len(articles))
            await enrich_articles(articles)

        articles = _sort_articles(articles, sort)

        if save and articles:
            save_articles(articles, query, "data")

    except Exception as exc:
        log.error("[%s] failed: %s", source.value, exc.__class__.__name__)
        return source, []

    return source, articles


async def _run_all(
    sources: list[Source],
    query: str,
    limit: int,
    sort: SortOrder,
    year_from: Optional[int],
    year_to: Optional[int],
    enrich: bool,
    save: bool,
) -> list[tuple[Source, list]]:
    tasks = [_run_source(s, query, limit, sort, year_from, year_to, enrich, save) for s in sources]
    return await asyncio.gather(*tasks)


@app.command()
def search(
    query: str = typer.Option(..., "--query", "-q", help="Search query"),
    sources: Optional[list[Source]] = typer.Option(
        None, "--source", "-s",
        help="Source to search (repeatable). Default: all implemented sources.",
    ),
    limit: int = typer.Option(
        None, "--limit", "-l",
        help="Max results per source. Defaults to DEFAULT_LIMIT env var (default: 10).",
    ),
    sort: SortOrder = typer.Option(
        SortOrder.citations, "--sort", "-o",
        help="Sort order: citations (most cited first), year (newest first), relevance (source order).",
    ),
    year_from: Optional[int] = typer.Option(
        None, "--year-from",
        help="Include only articles published from this year onwards.",
    ),
    year_to: Optional[int] = typer.Option(
        None, "--year-to",
        help="Include only articles published up to this year.",
    ),
    enrich: bool = typer.Option(
        True, "--enrich/--no-enrich",
        help="Resolve DOI, BibTeX and PDF link for each result (slower).",
    ),
    save: bool = typer.Option(
        False, "--save/--no-save",
        help="Save results to data/ as JSONL. Overrides SAVE_RESULTS env var.",
    ),
):
    from .config import settings
    effective_limit = limit if limit is not None else settings.default_limit
    effective_save = save or settings.save_results

    selected = [s for s in (sources or ALL_SOURCES) if s not in _NOT_IMPLEMENTED]
    skipped  = [s for s in (sources or ALL_SOURCES) if s in _NOT_IMPLEMENTED]

    year_range = ""
    if year_from or year_to:
        year_range = f"\n[bold]Year range:[/bold] {year_from or '…'} – {year_to or '…'}"

    console.print(Panel(
        f"[bold]Query:[/bold] {query}\n"
        f"[bold]Sources:[/bold] {', '.join(s.value for s in (sources or ALL_SOURCES))}\n"
        f"[bold]Limit:[/bold] {effective_limit} per source\n"
        f"[bold]Sort:[/bold] {sort.value}\n"
        f"[bold]Enrich:[/bold] {'yes' if enrich else 'no (fast)'}"
        + year_range,
        title="[bold magenta]Multi Scholar Search[/bold magenta]",
        expand=False,
    ))

    for s in skipped:
        log.warning("[dim]%s not yet implemented, skipping.[/dim]", s.value)

    if not selected:
        console.print("[red]No implemented sources selected.[/red]")
        raise typer.Exit(1)

    log.info("Searching %d source(s) in parallel…", len(selected))
    results = asyncio.run(_run_all(selected, query, effective_limit, sort, year_from, year_to, enrich, effective_save))

    total = 0
    for source, articles in results:
        total += len(articles)
        console.print(f"[bold cyan]{source.value}[/bold cyan] — {len(articles)} result(s)")
        _print_results(articles)

    console.print(f"[bold green]Done.[/bold green] {total} total result(s) found.")


if __name__ == "__main__":
    app()
