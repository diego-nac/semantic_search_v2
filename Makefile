Q ?= "forest image recognition"

.PHONY: install browsers test test-v lint fmt run clean

install:
	uv sync

browsers:
	uv run playwright install chromium

test:
	uv run pytest

test-v:
	uv run pytest -v

lint:
	uv run ruff check src tests

fmt:
	uv run ruff format src tests

run:
	uv run mss -q $(Q)

run-fast:
	uv run mss -q $(Q) --no-enrich

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
