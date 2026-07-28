![TwitterBanner\_SkyHyperpole2\_1991](https://github.com/user-attachments/assets/be996e61-d7f0-42aa-a38b-dae32e8f40f7)

# Typus

[![CI](https://github.com/polli-labs/typus/actions/workflows/ci.yml/badge.svg)](https://github.com/polli-labs/typus/actions/workflows/ci.yml)

**Shared taxonomy & geo‑temporal types for the Polli‑Labs ecological stack**

Documentation: https://docs.polli.ai/typus

Typus centralises every domain object that the rest of our platform —
`linnaeus`, `pollinalysis-server`, dashboards … — needs: taxon records,
clades, canonical classification results, projection helpers and async
database services. Anything that speaks taxonomy imports **Typus** and stays DRY.

---

## Features

* **Wide ancestry view** – `expanded_taxa` ORM exposes each rank (L10 → L70)
  on a single row for constant‑time lineage queries.
* **Async services** – `PostgresTaxonomyService` (ltree) &
  `SQLiteTaxonomyService` (fixture) share one interface.
* **Pydantic v2 models** – `Taxon`, `Clade`, `ClassificationResult`, and
  one-release deprecated classification aliases, all JSON-Schema-exportable.
* **Classification decision helpers** – Chow thresholds, hierarchy repair, and
  cost-sensitive expected-utility policies operate on calibrated
  `ClassificationResult` belief without retraining.
* **Taxonomy summaries & pollinator groups** – `TaxonSummary` trails plus coarse
  `PollinatorGroup` helpers for UI labels.
* **Projection utils** – lat/lon ↔ unit‑sphere, cyclical‑time features,
  multi‑scale elevation sinusoids.
* **Optional dependencies only when you need them** – the core install is
  pydantic-only: DTOs, geometry, and `typus.ops` import without sqlalchemy or
  rapidfuzz. Add `polli-typus[services]` for the taxonomy/elevation services,
  `[postgres]` / `[sqlite]` for a driver, `[fuzzy]` for fuzzy rank inference,
  `[loader]` for TSV/HTTP ingest, or `[all]` for everything.
* **Offline SQLite loader** – `typus-load-sqlite` CLI builds and caches the offline dataset

---

## Requirements

* Python **≥ 3.10**

---

## Installation

### Core (pydantic only)

```bash
uv pip install polli-typus        # import typus
```

The core install depends on **pydantic alone**. Models, canonical geometry,
`typus.ops`, projections, and the classification/decision helpers all import
without sqlalchemy, rapidfuzz, or any DB driver.

### Extras

| Extra | Adds | Needed for |
| --- | --- | --- |
| `fuzzy` | `rapidfuzz` | fuzzy (non-exact) `infer_rank` lookups |
| `services` | `sqlalchemy[asyncio]` + `[fuzzy]` | `TaxonomyService`, `SQLiteTaxonomyService`, `PostgresTaxonomyService`, `ElevationService`, `typus.orm` |
| `postgres` | `[services]` + `asyncpg` | Postgres taxonomy/elevation backends |
| `sqlite` | `[services]` + `aiosqlite` | offline SQLite backend (CI, sandboxes) |
| `pgvector` | `psycopg-binary` | pgvector helpers |
| `loader` | polars/pandas/requests/tqdm | `typus-load-sqlite` TSV/HTTP ingest |
| `all` | `[services,postgres,sqlite,pgvector]` | everything except loader/docs tooling |

```bash
uv pip install "polli-typus[postgres]"    # services + asyncpg
uv pip install "polli-typus[sqlite]"      # services + aiosqlite
uv pip install "polli-typus[loader]"      # TSV/HTTP ingest tooling
uv pip install "polli-typus[all]"         # services + every driver
```

The service symbols re-exported from `typus` (`TaxonomyService`,
`SQLiteTaxonomyService`, `PostgresTaxonomyService`, `TaxonomyServiceError`,
`BackendConnectionError`, `TaxonNotFoundError`, `ElevationService`,
`PostgresRasterElevation`) are resolved lazily on first attribute access, so a
bare `polli-typus` install can still `import typus`. Accessing one without the
extra raises a `ModuleNotFoundError` naming the extra to install. Note that
`from typus import *` eagerly resolves all of them and therefore requires
`polli-typus[services]`.

### Development / tests / lint

```bash
uv pip install -e ".[dev,loader]"   # [dev] pulls [all] plus pytest, ruff, ty, pre-commit …
```

---

## Quick start

### SQLite (recommended for getting started)

```bash
# Download or build the expanded taxonomy dataset locally (~475MB sqlite / ~440MB tsv.gz)
# The loader creates recommended indexes by default for fast name search
typus-load-sqlite --sqlite expanded_taxa.sqlite
```

```python
from pathlib import Path
from typus.services import SQLiteTaxonomyService

svc = SQLiteTaxonomyService(Path("expanded_taxa.sqlite"))
bee = await svc.get_taxon(630955)           # Anthophila
print(bee.scientific_name, bee.rank_level)  # Anthophila RankLevel.L32
assert bee.source == "iNaturalist"          # authority of the numeric concept IDs
```

You can also load on-demand in code (will download if missing):

```python
from pathlib import Path
from typus.services import load_expanded_taxa, SQLiteTaxonomyService

db_path = load_expanded_taxa(Path("expanded_taxa.sqlite"))  # create_indexes=True by default
svc = SQLiteTaxonomyService(db_path)
```

### Name search (v0.4.0+)

```python
# Scientific prefix match
taxa = await svc.search_taxa("Apis", scopes={"scientific"}, match="prefix")

# Vernacular (common name) exact
taxa = await svc.search_taxa("honey bee", scopes={"vernacular"}, match="exact")
```

### Taxonomy summaries & pollinator groups (v0.4.2)

```python
from pathlib import Path
from typus import PollinatorGroup
from typus.services import SQLiteTaxonomyService

svc = SQLiteTaxonomyService(Path("expanded_taxa.sqlite"))

# Compact trail for UIs
bee_summary = await svc.taxon_summary(630955)  # Anthophila
print(bee_summary.format_trail())  # Animalia → Arthropoda → Insecta → Hymenoptera → Apidae → Anthophila

# Coarse pollinator grouping
groups = await svc.pollinator_groups_for_taxon(47219)  # Apis mellifera
assert PollinatorGroup.BEE in groups
```

### Elevation (Postgres only)

```python
import os
from typus import PostgresRasterElevation

dsn = os.getenv("ELEVATION_DSN") or os.getenv("TYPUS_TEST_DSN")
elev = PostgresRasterElevation(dsn, raster_table=os.getenv("ELEVATION_TABLE", "elevation_raster"))

la = await elev.elevation(34.0522, -118.2437)
vals = await elev.elevations([
    (34.0522, -118.2437),  # LA
    (0.0, -30.0),          # ocean (likely None)
])
```

### Geo helpers

```python
from typus import latlon_to_unit_sphere
print(latlon_to_unit_sphere(31.5, -110.4))  # → x, y, z on S²
```

### Postgres (optional for production deployments)

```python
from typus import PostgresTaxonomyService
svc = PostgresTaxonomyService("postgresql+asyncpg://user:pw@host/db")
bee = await svc.get_taxon(630955)
```

---

## Developer guide

Contributor setup and the canonical gate live in [`docs/contributing.md`](docs/contributing.md).

* **Bootstrap the repo-local dev environment**

  ```bash
  ./dev/scripts/bootstrap-dev.sh
  ```

* **Run the canonical local quality gate**

  ```bash
  make check-all
  ```

* **Format whole repo**

  ```bash
  make format
  ```

* **Build docs**

  ```bash
  make docs
  ```

* **JSON Schemas** – `make schemas` → `typus/schemas/`
* **Type checking** – `make typecheck`
* **Contributor guide** – `docs/contributing.md`

* **SQLite fixture** – `uv run python scripts/gen_fixture_sqlite.py`

* **Pre‑commit hooks** – `make dev-install`

### Environment Variables

- `TYPUS_TEST_DSN`: Postgres DSN for tests and perf harness (e.g., `postgresql+asyncpg://user:pw@host/db`).
- `POSTGRES_DSN`: Alternate Postgres DSN; used if `TYPUS_TEST_DSN` is unset.
- Optional test/ops normalization maps legacy `/ibrida-v0-r1` DSNs to `/ibrida-v0`.
- `ELEVATION_DSN`: Optional DSN override for elevation tests; falls back to `TYPUS_TEST_DSN`.
- `ELEVATION_TABLE`: Elevation raster table name (default: `elevation_raster`).
- `TYPUS_ELEVATION_TEST`: Set `1` to enable guarded elevation tests.
- Perf harness:
  - `TYPUS_PERF_WRITE=1`: write report to `dev/agents/perf_report.md`.
  - `TYPUS_PERF_VERIFY=1`: enable result sanity checks.
  - `TYPUS_PERF_EXPLAIN=1`: append PG EXPLAIN snippets.

---

## Publishing (maintainers)

See `build/typus_publish.md` for tag → TestPyPI → PyPI workflow.

---

## License

MIT © 2025 Polli Labs
