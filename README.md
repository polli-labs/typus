![TwitterBanner\_SkyHyperpole2\_1991](https://github.com/user-attachments/assets/be996e61-d7f0-42aa-a38b-dae32e8f40f7)

# Typus

**Shared taxonomy & geo‑temporal types for the Polli‑Labs ecological stack**

Typus centralises every domain object that the rest of our platform —
`linnaeus`, `pollinalysis-server`, dashboards … — needs: taxon records,
clades, hierarchical classification results, projection helpers and async
database services. Anything that speaks taxonomy imports **Typus** and stays DRY.

---

## Features

* **Wide ancestry view** – `expanded_taxa` ORM exposes each rank (L10 → L70)
  on a single row for constant‑time lineage queries.
* **Async services** – `PostgresTaxonomyService` (ltree) &
  `SQLiteTaxonomyService` (fixture) share one interface.
* **Pydantic v2 models** – `Taxon`, `Clade`,
  `HierarchicalClassificationResult`, all JSON‑Schema‑exportable.
* **Projection utils** – lat/lon ↔ unit‑sphere, cyclical‑time features,
  multi‑scale elevation sinusoids.
* **Optional drivers only when you need them** – install
  `polli-typus[postgres]` or `[sqlite]`; core install stays lightweight.
* **Offline SQLite loader** – `typus-load-sqlite` CLI builds and caches the offline dataset

---

## Requirements

* Python **≥ 3.10**

---

## Installation

### Core (no DB drivers)

```bash
uv pip install polli-typus        # import typus
```

### With Postgres backend

```bash
uv pip install "polli-typus[postgres]"    # adds asyncpg
```

### With SQLite only (CI, offline, sandboxes)

```bash
uv pip install "polli-typus[sqlite]"
```

### Development / tests / lint

```bash
uv pip install -e ".[dev,sqlite]"   # pytest, pytest-asyncio, ruff, pre-commit, aiosqlite …
```

Install with plain pip:

```bash
pip install -e ".[dev,sqlite]"
```

---

## Quick start

```python
from typus import PostgresTaxonomyService, RankLevel, latlon_to_unit_sphere

svc = PostgresTaxonomyService("postgresql+asyncpg://user:pw@host/db")
bee = await svc.get_taxon(630955)           # Anthophila
print(bee.scientific_name, bee.rank_level)  # Anthophila RankLevel.L32

print(latlon_to_unit_sphere(31.5, -110.4))  # → x, y, z on S²
```

### Offline mode (SQLite fixture)

```python
from pathlib import Path
from typus.services import SQLiteTaxonomyService, load_expanded_taxa

db = Path("expanded_taxa.sqlite")
load_expanded_taxa(db)  # downloads if missing
svc = SQLiteTaxonomyService(db)
```
```bash
typus-load-sqlite --sqlite expanded_taxa.sqlite
```

---

## Developer guide

* **Lint & tests (one‑liner)**

  ```bash
  ruff check . && ruff format . && pytest -q
  ```

* **Format whole repo**

  ```bash
  ruff format .
  ```

* **JSON Schemas** – `python -m typus.export_schemas` → `typus/schemas/`

* **SQLite fixture** – `python scripts/gen_fixture_sqlite.py`

* **Pre‑commit hooks** – `pre-commit install`

---

## Publishing (maintainers)

See `build/typus_publish.md` for tag → TestPyPI → PyPI workflow.

---

## License

MIT © 2025 Polli Labs
