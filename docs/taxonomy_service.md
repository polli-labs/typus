# Taxonomy Service

Typus exposes a common asynchronous interface for working with taxonomic data. Two concrete implementations are provided:

* `PostgresTaxonomyService` – connects to a live PostgreSQL database containing the `expanded_taxa` materialised view.
* `SQLiteTaxonomyService` – reads the same schema from a local SQLite file for offline or testing scenarios.

Both classes implement the `AbstractTaxonomyService` API:

```python
class AbstractTaxonomyService:
    async def get_taxon(self, taxon_id: int) -> Taxon: ...
    async def children(self, taxon_id: int, *, depth: int = 1): ...  # async-iterable on Postgres
    async def children_list(self, taxon_id: int, *, depth: int = 1) -> list[Taxon]: ...
    async def lca(self, taxon_ids: set[int], *, include_minor_ranks: bool = False) -> Taxon: ...
    async def distance(
        self, a: int, b: int, *, include_minor_ranks: bool = False, inclusive: bool = False
    ) -> int: ...
    async def fetch_subtree(self, root_ids: set[int]) -> dict[int, int | None]: ...
    async def subtree(self, root_id: int) -> dict[int, int | None]: ...
    async def get_many_batched(self, ids: set[int]) -> dict[int, Taxon]: ...
    async def ancestors(self, taxon_id: int, *, include_minor_ranks: bool = True) -> list[int]: ...
    async def search_taxa(self, query: str, *, scopes={"scientific","vernacular"}, match="auto", fuzzy=True, threshold=0.8, limit=20, rank_filter=None, with_scores=False): ...
    async def taxon_summary(self, taxon_id: int, *, major_ranks_only: bool = True) -> TaxonSummary: ...
    async def pollinator_groups_for_taxon(self, taxon_id: int) -> set[PollinatorGroup]: ...
```

The return types are `Taxon` models or simple dictionaries. All methods are `async` so they can be awaited inside any asyncio application.

## Postgres service

```python
from typus import PostgresTaxonomyService

svc = PostgresTaxonomyService("postgresql+asyncpg://user:pw@host/db")
bee = await svc.get_taxon(630955)
```

`PostgresTaxonomyService` requires the optional `asyncpg` dependency (`uv pip install "polli-typus[postgres]"`). It expects the `expanded_taxa` view with columns `immediateAncestor_taxonID` and `immediateMajorAncestor_taxonID`. The service first attempts to use an ltree `path` column for `lca()` and `distance()` queries but will automatically fall back to a recursive CTE when that column is missing.

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
usage: typus-load-sqlite --sqlite PATH [--tsv TSV] [--url URL] [--replace] [--cache DIR] [--with-indexes/--no-with-indexes]
```

Downloads come from `https://assets.polli.ai/expanded_taxa/latest/expanded_taxa.sqlite` by default and are cached in `~/.cache/typus` (override with `$TYPUS_CACHE_DIR`). Use `--replace` to overwrite an existing file or `--tsv my.tsv` to populate from a local TSV dump. The loader creates recommended indexes by default for fast name search; disable with `--no-with-indexes`.

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

## Taxonomy summaries & pollinator groups (v0.4.2)

```python
from typus import PollinatorGroup

summary = await svc.taxon_summary(47219)  # Apis mellifera
trail = summary.format_trail()  # Animalia → Arthropoda → Insecta → Hymenoptera → Apidae → Apis → Apis mellifera

groups = await svc.pollinator_groups_for_taxon(47219)
assert groups == {PollinatorGroup.BEE}
```

- `taxon_summary(taxon_id, major_ranks_only=True)` returns a `TaxonSummary` with
  the ordered root→taxon trail. Set `major_ranks_only=False` to include minor
  ranks; the focal taxon is always included.
- `pollinator_groups_for_taxon()` maps a taxon's ancestry to coarse UI-friendly
  buckets (Bee, Fly, Butterfly/Moth, Wasp, Beetle, Bird, Bat). The mapping is
  intentionally opinionated and should not be used for precise taxonomy.

## Backend Differences & Guidance (v0.4.0)

- Parity: API and semantics are aligned across SQLite and Postgres. Minor result-order differences can occur with fuzzy re-ranking.
- Datasets: SQLite typically uses a compact fixture while Postgres points to a full production dataset. Expect different result counts when data volumes differ.
- Performance: exact/prefix searches are fast on both backends (SQLite uses expression indexes; Postgres should use the helper indexes). Substring searches involve scans; prefer prefix where possible.
- Indexes: SQLite loader creates indexes by default. Postgres should run `typus-pg-ensure-indexes` once in maintenance to ensure optimal plans.
- Elevation: Provided via a separate Postgres-only service (`PostgresRasterElevation`). No elevation support on SQLite.

## Postgres Indexes (optional helper)

For production Postgres deployments, ensure the recommended indexes for fast name search and ancestry operations:

```
uv run typus-pg-ensure-indexes --dsn "$POSTGRES_DSN" --schema public --ensure-trgm
```

Programmatic:

```python
from typus.services.pg_index_helper import ensure_expanded_taxa_indexes
await ensure_expanded_taxa_indexes(POSTGRES_DSN, include_trigram_indexes=True, ensure_pg_trgm_extension=False)
```

## Name Search (v0.4.0+)

Typus includes a uniform search capability across scientific and vernacular names with optional fuzzy matching:

```python
taxa = await svc.search_taxa(
    "Apis", scopes={"scientific"}, match="prefix", fuzzy=True, threshold=0.8, limit=20,
)
```

- scopes: {"scientific", "vernacular"}
- match: "exact" | "prefix" | "substring" | "auto"
- fuzzy: True uses RapidFuzz to re-rank a SQL superset
- rank_filter: restricts by `RankLevel`
- with_scores: return `(Taxon, score)` tuples

## Children ergonomics

- Postgres `children()` is an async-iterable (good for streaming in services).
- Use `children_list()` to get a list on all backends for simple workflows:

```python
kids = await svc.children_list(52747, depth=2)
```

## Ancestors & Batched Lookups

- `ancestors(taxon_id, include_minor_ranks=True)` returns a parent chain (root→self), assembled via immediate ancestor hops.
- `get_many_batched(ids)` resolves many taxa efficiently in one query per backend.
