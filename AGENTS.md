# AGENTS.md – Coding conventions & environment bootstrap

Obey these rules when modifying Typus.

1. **Python version** Target **3.10+**.  
   All new syntax should compile on 3.10; do *not* use 3.11-only features.

2. **Formatting / lint**  
   * Run `ruff format .` to auto-format.  
   * Run `ruff check .` and fix all errors except E501 (line length) which is
     ignored – the formatter wraps strings automatically.  
   * Ensure `pytest -q` passes before opening a PR.

3. **Dependencies**  
   * Use the `[project.optional-dependencies]` groups in *pyproject.toml*.  
     – postgres extras for Postgres-specific code  
     – sqlite extras for SQLite-only helpers  
   * **Never** add a runtime dependency without asking the maintainer.

4. **Tests**  
   * New modules must include unit tests under `tests/`.  
   * Use the `taxonomy_service` fixture provided by `conftest.py`
     (auto-selects Postgres or SQLite).
        * Note: becuase Codex environments are sandboxed, you must generate the sqlite fixture via `scripts/gen_fixture_sqlite.py` (postgres not an option without network access).


5. **Docs**  
   * Public models require docstrings; update `README.md` if public API grows.  
   * After adding a Pydantic model, append its dotted path to
     `typus/export_schemas.py` so the JSON-Schema exporter picks it up.