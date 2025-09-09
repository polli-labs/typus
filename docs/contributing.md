Title: Development & Contributing

This page describes how to set up a local development environment, run tests, and understand the CI gates for Typus.

Environment

- Python 3.10+ (CI tests run on 3.10, 3.11, 3.12)
- Install dev extras with SQLite support:

```
pip install -e ".[dev,sqlite]"
```

Pre-commit

- Install hooks:

```
pre-commit install
```

- Hooks run on commit and in CI:
  - ruff (lint + format check)
  - whitespace/yaml fixers
  - pytest-lite (a fast subset; see below)

Tests

- Lightweight tests (default):

```
pytest -q -k "not test_async_compatibility.py and not test_ancestry_verification and not test_ancestor_descendant_distance and not test_perf_name_search_local"
```

- Elevation smoke tests (Postgres only):
  - Enable with `TYPUS_ELEVATION_TEST=1` and provide a DSN (`ELEVATION_DSN` or `TYPUS_TEST_DSN`).
  - These are skipped by default in CI and pre-commit.

- Postgres-backed tests (optional):
  - Set `TYPUS_TEST_DSN` to enable connection (search, lineage, etc.).
  - Keep these off in CI unless explicitly required.

Perf Harness (optional)

- Run with:

```
make perf
```

Writes a report to `dev/agents/perf_report.md`. You can enable `TYPUS_PERF_VERIFY=1` for strict checks, and `TYPUS_PERF_EXPLAIN=1` to append EXPLAIN snippets for Postgres.

Service Backends

- SQLite: For offline/dev, uses a cached fixture. Loader creates indexes by default.
- Postgres: For production or full datasets. Use `typus-pg-ensure-indexes` to create recommended indexes.
- Elevation: Postgres-only; use `ELEVATION_DSN` and `ELEVATION_TABLE` (default `elevation_raster`).

CI/CD Overview

- CI workflow (`.github/workflows/ci.yml`):
  - Matrix on Python 3.10/3.11/3.12.
  - Runs pre-commit (includes pytest-lite) plus a separate lightweight pytest run.
- Publish workflow (`.github/workflows/publish.yml`):
  - Blocks build/publish on tests job.
  - Builds and uploads wheels, then deploys docs on tag.

