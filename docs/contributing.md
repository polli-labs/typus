Title: Development & Contributing

This page describes how to set up a local development environment, run tests, and understand the CI gates for Typus.

Environment

- Python 3.10+ (CI runs on 3.10, 3.11, 3.12)
- Use `uv` and Makefile shortcuts (no plain `pip` in scripts/CI):

```
make dev-setup      # creates .venv (py310) and installs -e .[dev,sqlite,loader]
make dev-install    # installs pre-commit hooks
```

Formatting & Lint

```
make format         # uv run ruff format .
make lint           # uv run ruff check --fix .
```

Type checking

```
make typecheck      # uv run ty check
```

Tests

Lightweight SQLite-backed tests (default for local dev and CI):

```
make ci
```

Default test suite (SQLite + tests that do not require optional Postgres access):

```
make test
```

Postgres-backed tests (optional, requires a running DB):

```
export TYPUS_TEST_DSN=postgresql+asyncpg://<user>:<pass>@<host>:5432/ibrida-v0
export POSTGRES_DSN=$TYPUS_TEST_DSN
export ELEVATION_DSN=$TYPUS_TEST_DSN
export ELEVATION_TABLE=elevation_raster

# Smoke-check DSN / DB / required table before optional PG tests
make test-pg-smoke

# Optional Postgres marker subset (dataset-dependent)
make test-pg

# Elevation smoke tests (guarded; requires raster table)
TYPUS_ELEVATION_TEST=1 uv run pytest -q -k elevation_service

Important: `make test` and CI exclude `pg_optional` tests by marker. Run
`make test-pg-smoke` + `make test-pg` explicitly when you want live Postgres coverage. Some tests
assert counts that are specific to the SQLite sample fixture and will not match
the full production dataset. The recommended workflow is:

1) Run `make ci` / `make test` to exercise the SQLite fixture path.
2) Run `make test-pg-smoke` and then `make test-pg` for Postgres-specific coverage.
```

Notes:

- Ensure the Postgres database contains the required `expanded_taxa` table with the
  recommended indexes. You can bootstrap indexes with:

```
uv run typus-pg-ensure-indexes
```

Pre-commit

```
make dev-install
```

Hooks run on commit and in CI:
- ruff (lint)
- ruff-format (check-only in CI)
- whitespace/yaml fixers
- pytest-lite (fast subset; mirrors `make ci` test selection)

JSON Schemas

If you add or change public Pydantic models, append the dotted path to
`typus/export_schemas.py` and regenerate schemas:

```
uv run python -m typus.export_schemas
```

Generated JSON files live under `typus/schemas/` and are committed to the repo.
CI and release workflows enforce schema freshness with `make schemas-check`.

Perf Harness (optional)

```
make perf
```

Writes a report to `dev/agents/perf_report.md`. You can enable `TYPUS_PERF_VERIFY=1` for strict checks,
and `TYPUS_PERF_EXPLAIN=1` to append EXPLAIN snippets for Postgres.

Service Backends

- SQLite: for offline/dev; loader creates indexes by default.
- Postgres: for production or full datasets; `typus-pg-ensure-indexes` adds recommended indexes.
- Elevation: Postgres-only; use `ELEVATION_DSN` and `ELEVATION_TABLE` (default `elevation_raster`).

CI/CD Overview

- CI workflow (`.github/workflows/ci.yml`):
  - Matrix on Python 3.10/3.11/3.12.
  - Runs `ruff format --check` and `ruff check`.
  - Runs `ty` type checks via `make typecheck`.
  - Runs schema freshness checks and a lightweight SQLite-backed pytest selection.
  - Triggers on PRs and pushes to `main` (to avoid duplicate branch + PR runs for the same commit).
- Publish workflow (`.github/workflows/publish.yml`):
  - Blocks build/publish on tests job (ruff + ty + schemas + SQLite test selection).
  - Builds and uploads wheels, then deploys docs on tag.
