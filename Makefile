.PHONY: help dev-setup dev-install lint format test test-fast test-pg typus-sqlite docs check-all quick clean

# Colors
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m

.DEFAULT_GOAL := help

help: ## Show this help message
	@echo '$(BLUE)Available targets:$(NC)'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-18s$(NC) %s\n", $$1, $$2}'

dev-setup: ## Create venv and install dev + sqlite extras with uv
	@echo "$(BLUE)Setting up venv (py310) and installing extras...$(NC)"
	uv venv --python 3.10
	uv pip install -e ".[dev,sqlite]"
	@echo "$(GREEN)✓ Environment ready$(NC)"

dev-install: ## Install pre-commit hooks
	uv run pre-commit install
	uv run pre-commit install --hook-type pre-push
	@echo "$(GREEN)✓ Pre-commit hooks installed$(NC)"

lint: ## Lint (ruff)
	uv run ruff check --fix .

format: ## Format (ruff)
	uv run ruff format .

test: ## Run default suite (excludes optional Postgres-backed tests)
	uv run pytest -q -m "not pg_optional"

test-fast: ## Run tests, verbose output
	uv run pytest -v

ci: ## CI-friendly tests (skip optional Postgres + full-ancestry checks)
	uv run pytest -q -m "not pg_optional" -k 'not test_ancestry_verification and not test_ancestor_descendant_distance'

test-pg: ## Run optional Postgres-backed tests (requires TYPUS_TEST_DSN)
	@[ -n "$$TYPUS_TEST_DSN" ] || (echo "$(YELLOW)TYPUS_TEST_DSN not set; skipping PG tests$(NC)" && exit 0)
	uv run pytest -q -m "pg_optional"

pg-indexes: ## Ensure Postgres indexes for expanded_taxa (uses POSTGRES_DSN or TYPUS_TEST_DSN)
	uv run typus-pg-ensure-indexes

typus-sqlite: ## Download/build latest expanded_taxa SQLite DB to .cache/typus/expanded_taxa.sqlite
	uv run typus-load-sqlite --sqlite .cache/typus/expanded_taxa.sqlite

docs: ## Build docs with mkdocs (requires extras [docs])
	uv pip install -e ".[docs]"
	uv run mkdocs build

schemas: ## Export JSON Schemas and show changes
	uv run python -m typus.export_schemas
	@git status --porcelain typus/schemas || true

perf: ## Run name-search perf harness (writes dev/agents/perf_report.md)
	TYPUS_PERF_WRITE=1 uv run python scripts/perf_report.py

check-all: format lint test ## Format, lint, test

quick: format lint ## Format + lint only

clean: ## Clean caches (pytest/ruff)
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
