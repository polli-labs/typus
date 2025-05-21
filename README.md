# Typus

**Shared taxonomy & geo‑temporal types for the Polli‑Labs ecological stack**

Typus centralises every domain object that the rest of our platform —
`linnaeus`, `pollinalysis‑server`, dashboards — needs: taxon records, clades,
hierarchical classification results, projection helpers and async database
services.  Anything that speaks taxonomy imports *Typus* and stays DRY.

---

## Features

* **Wide ancestry view** – `expanded_taxa` ORM exposes each rank (L10‑L70) on a
  single row for constant‑time lineage queries.
* **Async services** – `PostgresTaxonomyService` (ltree‑based) and
  `SQLiteTaxonomyService` (fixture) share an abstract interface.
* **Pydantic v2 models** – `Taxon`, `Clade`, `HierarchicalClassificationResult`,
  all JSON‑Schema‑exportable.
* **Projection utils** – lat/lon ↔ unit‑sphere, cyclical time features,
  multi‑scale elevation sinusoids.
* **Optional drivers only when you need them** – install `*[postgres]` or
  `*[sqlite]` extras; core install stays lightweight.

---

## Requirements

* Python **≥ 3.10**

---

## Installation

### Core (no DB drivers)

```bash
pip install typus
```

### With Postgres backend

```bash
pip install "typus[postgres]"            # adds asyncpg
```

### With SQLite only (CI, offline, Codex sandboxes)

```bash
pip install "typus[sqlite]"
```

### Development / tests / lint

```bash
pip install -e ".[dev,sqlite]"   # pytest, pytest-asyncio, ruff, pre-commit, aiosqlite
```

Using `uv`:

```bash
uv pip install -e ".[dev,sqlite]"
```

---

## Quick start

```python
from typus import PostgresTaxonomyService, latlon_to_unit_sphere, RankLevel

svc = PostgresTaxonomyService("postgresql+asyncpg://user:pw@host/db")
bee = await svc.get_taxon(630955)   # Anthophila
print(bee.scientific_name, bee.rank_level)  # Anthophila RankLevel.L32

print(latlon_to_unit_sphere(31.5, -110.4))  # → x,y,z on S²
```

### Offline mode (fixture)

```python
from typus.services import SQLiteTaxonomyService
svc = SQLiteTaxonomyService()       # uses tests/fixture_typus.sqlite
```

---

## Developer guide

* **Lint & tests** (single command):

  ```bash
  ruff check . && ruff format . && pytest -q
  ```

* **Auto-format all files**:

  ```bash
  ruff format .  # formats both typus/ and tests/
  ```

* **JSON Schemas**: `python -m typus.export_schemas` → `typus/schemas/`.
* **SQLite fixture**: `python scripts/gen_fixture_sqlite.py` regenerates
  `tests/fixture_typus.sqlite` from the TSV snippets.
* **Pre‑commit**: install hooks with `pre‑commit install`.

---

## Publishing (maintainers)

See `polli‑labs/build/typus_publish.md` for tag → TestPyPI → PyPI workflow.

---

## License

MIT © 2025 Polli Labs
