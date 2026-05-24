# Multi Scholar Search

CLI tool that searches academic papers across multiple sources in parallel, enriches results with DOI, BibTeX and open-access PDF links, and outputs a sorted, filterable table.

## Sources

| Source | Status | Method |
|---|---|---|
| Google Scholar | ✅ | DrissionPage browser → Playwright fallback → scholarly fallback |
| Semantic Scholar | ✅ | Public Graph API (no key) → Playwright XHR fallback |
| Scopus | 🔜 | — |
| Web of Science | 🔜 | — |
| OpenAlex | 🔜 | — |

## Quick start

```bash
make install
make run Q="forest image recognition"
```

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) — `pip install uv`
- Chromium (installed via Playwright)
- ffmpeg (optional — reCAPTCHA audio solver only)

## Installation

```bash
git clone https://github.com/diego-nac/semantic_search_v2.git
cd semantic_search_v2

make install    # installs deps + venv
make browsers   # installs Playwright Chromium
```

## Configuration

```bash
cp .env.example .env
```

| Variable | Default | Description |
|---|---|---|
| `SAVE_RESULTS` | `false` | Save results to `data/` as JSONL |
| `DATA_DIR` | `data` | Output directory |
| `CHROMIUM_PROXY` | — | Proxy (`http://user:pass@host:port`) |
| `PAGE_DELAY` | `3.0` | Seconds between Google Scholar page fetches |
| `PAGE_RETRIES` | `2` | Browser retry attempts per page |
| `DRISSION_SETTLE_TIME` | `2.0` | Extra wait after browser page load |

## Usage

```bash
# All sources, default 50 results, sorted by citations
uv run mss -q "deep learning forest fire detection"

# Single source, 20 results, save to JSONL
uv run mss -q "remote sensing deforestation" --source google_scholar -l 20 --save

# Filter by year, sort by year
uv run mss -q "UAV tree species" --year-from 2020 --year-to 2024 --sort year

# Fast mode — skip DOI/BibTeX/PDF enrichment
uv run mss -q "convolutional neural network" --no-enrich

# Both sources in parallel
uv run mss -q "plant disease" --source google_scholar --source semantic_scholar
```

### CLI reference

```
--query,  -q   TEXT                        Search query (required)
--source, -s   [google_scholar|...]        Source — repeatable, default: all
--limit,  -l   INT                         Max results per source (default 50, max 50)
--sort,   -o   [citations|year|relevance]  Sort order (default: citations)
--year-from    INT                         Filter: published from this year
--year-to      INT                         Filter: published up to this year
--enrich / --no-enrich                     Resolve DOI, BibTeX, PDF (default: on)
--save   / --no-save                       Save JSONL to data/ (default: off)
```

## JSONL output schema

```json
{
  "title": "...",
  "title_link": "...",
  "authors": "...",
  "year": 2022,
  "cited_by_count": "Cited by 142",
  "doi": "10.1234/...",
  "bibtex": "@article{...}",
  "pdf_link": "https://...",
  "source": "google_scholar",
  "query": "forest image recognition",
  "scraped_at": "2026-05-24T18:00:00Z"
}
```

## Development

```bash
make test     # run all tests
make test-v   # verbose tests
make lint     # ruff check
make fmt      # ruff format
```

## Architecture

```
src/multi_scholar_search/
├── main.py                   # CLI, orchestration, sorting, filtering
├── config.py                 # pydantic-settings (.env)
├── models/
│   ├── base.py               # BaseArticle shared by all sources
│   ├── google_scholar.py
│   └── semantic_scholar.py
├── sources/
│   ├── google_scholar.py     # scholarly → DrissionPage → Playwright
│   └── semantic_scholar.py   # Graph API (backoff) → Playwright XHR
└── utils/
    ├── browser_client.py     # DrissionPage + Playwright async wrapper
    ├── doi_enricher.py       # Crossref → doi2bib → Unpaywall (concurrent)
    ├── recaptcha_solver.py   # Audio CAPTCHA (ffmpeg + Whisper)
    ├── storage.py            # Sequential JSONL file writer
    └── user_agents.py        # Random User-Agent rotation
```
