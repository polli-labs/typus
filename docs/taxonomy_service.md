# Taxonomy Service

Typus exposes a common asynchronous interface for working with taxonomic data. Two concrete implementations are provided:

* `PostgresTaxonomyService` – connects to a live PostgreSQL database containing the `expanded_taxa` materialised view.
* `SQLiteTaxonomyService` – reads the same schema from a local SQLite file for offline or testing scenarios.

Both classes implement the `AbstractTaxonomyService` API:

```python
class AbstractTaxonomyService:
    async def get_taxon(self, taxon_id: int) -> Taxon: ...
    async def children(self, taxon_id: int, *, depth: int = 1): ...
    async def lca(self, taxon_ids: set[int], *, include_minor_ranks: bool = False) -> Taxon: ...
    async def distance(
        self, a: int, b: int, *, include_minor_ranks: bool = False, inclusive: bool = False
    ) -> int: ...
    async def fetch_subtree(self, root_ids: set[int]) -> dict[int, int | None]: ...
    async def subtree(self, root_id: int) -> dict[int, int | None]: ...
```

The return types are `Taxon` models or simple dictionaries. All methods are `async` so they can be awaited inside any asyncio application.

## Postgres service

```python
from typus import PostgresTaxonomyService

svc = PostgresTaxonomyService("postgresql+asyncpg://user:pw@host/db")
bee = await svc.get_taxon(630955)
```

`PostgresTaxonomyService` requires the optional `asyncpg` dependency (`pip install polli-typus[postgres]`). It expects the `expanded_taxa` view with columns `immediateAncestor_taxonID` and `immediateMajorAncestor_taxonID`. The service first attempts to use an ltree `path` column for `lca()` and `distance()` queries but will automatically fall back to a recursive CTE when that column is missing.

## SQLite service

```python
from typus.services import SQLiteTaxonomyService
svc = SQLiteTaxonomyService(Path("expanded_taxa.sqlite"))
```

The SQLite implementation works with a local fixture using blocking `sqlite3` under the hood and therefore runs queries in a thread pool. If no file is provided, a small bundled dataset is used.

### Loading a fixture

`load_expanded_taxa()` can download a prepared database or convert a TSV dump:

```python
from typus.services import load_expanded_taxa

path = load_expanded_taxa(Path("expanded_taxa.sqlite"))
```

```
usage: typus-load-sqlite --sqlite PATH [--tsv TSV] [--url URL] [--replace] [--cache DIR]
```

Downloads come from `https://assets.polli.ai/expanded_taxa/latest/expanded_taxa.sqlite` by default and are cached in `~/.cache/typus` (override with `$TYPUS_CACHE_DIR`). Use `--replace` to overwrite an existing file or `--tsv my.tsv` to populate from a local TSV dump.

See [Offline mode](offline_mode.md) for more details on the loader.

## Example workflow

```python
from typus import PostgresTaxonomyService, SQLiteTaxonomyService

# Remote database
pg = PostgresTaxonomyService("postgresql+asyncpg://user:pw@host/db")
bee = await pg.get_taxon(630955)
children = await pg.children(52747, depth=2)

# Offline
db = load_expanded_taxa(Path("expanded_taxa.sqlite"))
local = SQLiteTaxonomyService(db)
lca = await local.lca({630955, 54328})
```

The two services share behaviour so code can accept `AbstractTaxonomyService` and run identically in both modes.
