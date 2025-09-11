# AGENTS.md – Coding conventions & environment bootstrap

Obey these rules when modifying Typus.

1. **Python version** Target **3.10+**.
   All new syntax should compile on 3.10; do *not* use 3.11-only features.

2. **Formatting / lint**
   * Run `ruff format .` to auto-format.
   * Run `ruff check .` and fix all errors except E501 (line length) which is
     ignored – the formatter wraps strings automatically.
   * Ensure the lightweight test subset passes before opening a PR (see docs/contributing.md).

3. **Dependencies**
   * Use the `[project.optional-dependencies]` groups in *pyproject.toml*.
     – postgres extras for Postgres-specific code
     – sqlite extras for SQLite-only helpers
   * **Never** add a runtime dependency without asking the maintainer.

4. **Environment**
   * Always use uv, not pip.
    * Create/update env: `make dev-setup` (uv venv + uv pip install -e .[dev,sqlite])
    * Run tools: `uv run ruff …`, `uv run pytest …`, `uv run pre-commit …`
  * Formatting & lint
    * Local: `ruff format . && ruff check .` (via `make format` / `make lint`)
    * CI is check-only (no auto-apply). Pre-commit shows diffs on failure.
  * Don’t introduce pip install commands in scripts, docs, or CI.
  * Prefer Makefile targets for common flows: `format`, `lint`, `test`, `ci`.
  * When pre-commit disagrees with `uv run ruff`, align versions by pinning ruff dev extra to match pre-commit rev.

4. **Tests**
   * New modules must include unit tests under `tests/`.
   * Use the `taxonomy_service` fixture provided by `conftest.py`
     (auto-selects Postgres or SQLite).
        * Note: becuase Codex environments are sandboxed, you must generate the sqlite fixture via `scripts/gen_fixture_sqlite.py` (postgres not an option without network access).
   * **Optional Database Tests**: Some tests in `test_async_compatibility.py` require
     a real PostgreSQL database and will be skipped in CI unless `TYPUS_TEST_DSN` is set.
     CI-friendly mock versions are provided in `test_async_compatibility_ci.py`.
   * See `docs/contributing.md` for the exact `pytest -k` expression used by pre-commit/CI.


5. **Docs**
   * Public models require docstrings; update `README.md` if public API grows.
   * After adding a Pydantic model, append its dotted path to
     `typus/export_schemas.py` so the JSON-Schema exporter picks it up.
