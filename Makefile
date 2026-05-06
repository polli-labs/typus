.PHONY: help dev-setup dev-install lock-age-check lint lint-check typecheck format test test-fast ci test-pg-smoke test-pg pg-indexes schemas schemas-check typus-sqlite docs check-all quick perf clean

# Colors
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m

.DEFAULT_GOAL := help

PYTEST_NO_PG_MARKER := -m "not pg_optional"
PYTEST_PG_MARKER := -m "pg_optional"
PYTEST_CI_K_EXPR := not ancestry_verification and not ancestor_descendant_distance and not perf_name_search_local
PYTEST_CI_ARGS := $(PYTEST_NO_PG_MARKER) -k "$(PYTEST_CI_K_EXPR)"
UV_CHECK_EXTRAS := --extra dev --extra sqlite --extra loader --extra docs
UV_RUN := uv run --locked $(UV_CHECK_EXTRAS)
UV_SYNC := uv sync --locked $(UV_CHECK_EXTRAS)

help: ## Show this help message
	@echo '$(BLUE)Available targets:$(NC)'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-18s$(NC) %s\n", $$1, $$2}'

dev-setup: ## Ensure a py310 venv and install the full dev toolchain with uv
	@echo "$(BLUE)Ensuring py310 via uv and syncing dev environment...$(NC)"
	uv python install 3.10
	uv venv --python 3.10 --allow-existing
	$(UV_SYNC)
	@echo "$(GREEN)✓ Environment ready$(NC)"

dev-install: ## Install pre-commit hooks
	$(UV_RUN) pre-commit install
	$(UV_RUN) pre-commit install --hook-type pre-push
	@echo "$(GREEN)✓ Pre-commit hooks installed$(NC)"

lock-age-check: ## Verify locked artifacts respect the dependency cooldown
	$(UV_RUN) python scripts/check_lock_upload_age.py --max-age-days 7

lint: ## Lint (ruff)
	$(UV_RUN) ruff check --fix .

lint-check: ## Lint checks only (no auto-fixes)
	$(UV_RUN) ruff format --check .
	$(UV_RUN) ruff check .

typecheck: ## Type-check runtime/tests/scripts with ty (warnings fail)
	$(UV_RUN) ty check

format: ## Format (ruff)
	$(UV_RUN) ruff format .

test: ## Run default suite (excludes optional Postgres-backed tests)
	$(UV_RUN) pytest -q $(PYTEST_NO_PG_MARKER)

test-fast: ## Run tests, verbose output
	$(UV_RUN) pytest -v

ci: ## CI-friendly tests (skip optional Postgres + full-ancestry checks)
	$(UV_RUN) pytest -q $(PYTEST_CI_ARGS)

test-pg-smoke: ## Validate DSN/database/table before optional Postgres tests
	$(UV_RUN) python scripts/pg_smoke.py

test-pg: ## Run optional Postgres-backed tests (requires TYPUS_TEST_DSN or POSTGRES_DSN)
	@([ -n "$$TYPUS_TEST_DSN" ] || [ -n "$$POSTGRES_DSN" ]) || (echo "$(YELLOW)TYPUS_TEST_DSN/POSTGRES_DSN not set; skipping PG tests$(NC)" && exit 0)
	@$(MAKE) test-pg-smoke
	$(UV_RUN) pytest -q $(PYTEST_PG_MARKER)

pg-indexes: ## Ensure Postgres indexes for expanded_taxa (uses POSTGRES_DSN or TYPUS_TEST_DSN)
	$(UV_RUN) typus-pg-ensure-indexes

typus-sqlite: ## Download/build latest expanded_taxa SQLite DB to .cache/typus/expanded_taxa.sqlite
	$(UV_RUN) typus-load-sqlite --sqlite .cache/typus/expanded_taxa.sqlite

docs: ## Build docs with mkdocs from the locked uv environment
	$(UV_RUN) mkdocs build

schemas: ## Export JSON Schemas and show changes
	$(UV_RUN) python -m typus.export_schemas
	@git status --porcelain typus/schemas || true

schemas-check: ## Verify schemas are fresh
	$(UV_RUN) python -m typus.export_schemas
	git diff --exit-code typus/schemas

perf: ## Run name-search perf harness (writes dev/agents/perf_report.md)
	TYPUS_PERF_WRITE=1 $(UV_RUN) python scripts/perf_report.py

check-all: lock-age-check lint-check typecheck docs schemas-check ci ## Canonical local quality gate (matches CI/publish)

quick: format lint ## Format + lint only

clean: ## Clean caches (pytest/ruff)
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
