# Typus

*Shared taxonomy and metadata types for the Polli‑Labs ecological software stack*

Typus consolidates **all domain models** (Taxa, Clades, hierarchical classification
results, geo‑temporal projections …) along with the data‑access layer that backs
those models.  Down‑stream repos – `linnaeus`, `pollinalysis‑server`, notebooks –
import Typus and never re‑implement domain objects.

* **Instant taxonomy queries**   Async service that talks to the
  `expanded_taxa` view in Postgres or a lightweight SQLite fixture.
* **Pydantic v2 data classes**   Type‑safe, JSON‑serialisable, JSON‑Schema
  auto‑export.
* **Projection helpers**   Lat/Lon → unit sphere, day‑of‑year/hours
  sinusoids, elevation multi‑scale sinusoids.
* **Complete ORM for ColDP**   NameUsage, VernacularName, Media, Reference …
  ready for analytics and joins.

## Install

```bash
# editable install with Postgres extras (asyncpg)
uv pip install -e .[postgres]
```

or from the private index:

```bash
pip install --index-url https://pypi.polli.ai/simple typus==0.1.5a0
```

## Quick start

```python
from typus import (
    PostgresTaxonomyService, RankLevel,
    latlon_to_unit_sphere, HierarchicalClassificationResult
)

svc = PostgresTaxonomyService("postgresql+asyncpg://user:pw@host/db")
bee = await svc.get_taxon(630955)           # Anthophila
print(bee.rank_level)                       # RankLevel.L30 (family)

# projections
a,b,c = latlon_to_unit_sphere(31.5, -110.4)
```

### Offline / tests

A tiny SQLite fixture with real data ships in `tests/fixture_typus.sqlite`.
Typus automatically falls back to it if the `POSTGRES_DSN` env‑var is unset.

```bash
pytest -q               # runs against the fixture
POSTGRES_DSN=... pytest # runs full integration suite
```

## Development

* **Lint / format**: `ruff check . && ruff format .`
* **Tests**: `pytest -q`
* **Generate JSON schemas**: `python -m typus.export_schemas`
* **Rebuild fixture**: `python scripts/gen_fixture_sqlite.py`

A `.pre-commit-config.yaml` is provided to automate lint + tests on commit.

## License

MIT © 2025 Polli‑Labs
