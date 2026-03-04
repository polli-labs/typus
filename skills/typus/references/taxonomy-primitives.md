# Typus Taxonomy Primitives

Use this reference when changing rank semantics, taxonomy DTOs, or service behavior.

## Core Files

- `typus/constants.py`
  - `RankLevel` enum with major and selected minor levels
  - `RANK_CANON` and `NAME_TO_RANK` mappings
  - `infer_rank(name, cutoff=80)` fuzzy helper (RapidFuzz)
- `typus/models/taxon.py`
  - canonical taxon object used across services
- `typus/models/lineage.py`
  - lineage map DTO
- `typus/models/clade.py`
  - clade representation
- `typus/models/summary.py`
  - `TaxonTrailNode` and `TaxonSummary` for compact lineage rendering
- `typus/pollinator_groups.py`
  - `PollinatorGroup`, `POLLINATOR_GROUP_DEFS`, and ancestry mapping helper

## Service Contract

The stable taxonomy contract is `typus/services/taxonomy/abstract.py` (`AbstractTaxonomyService`).

Primary methods:

- lookup and traversal: `get_taxon`, `children`, `children_list`, `ancestors`
- topology: `lca`, `distance`, `subtree`, `fetch_subtree`
- batch: `get_many_batched`
- search: `search_taxa` with scope/match/fuzzy options
- UI helpers: `taxon_summary`, `pollinator_groups_for_taxon`

Backends:

- `typus/services/taxonomy/postgres.py` (`PostgresTaxonomyService`)
- `typus/services/taxonomy/sqlite.py` (`SQLiteTaxonomyService`)
- shared errors in `typus/services/taxonomy/errors.py`

## Backend Behavior Notes

- Keep semantics aligned across Postgres and SQLite backends.
- Prefer coding against `AbstractTaxonomyService` for integration-facing code.
- Use `children_list` when callers should not depend on backend-specific iteration style.
- Maintain existing `search_taxa` behavior across scopes/match modes when changing query logic.

## SQLite Fixture and Loader

- Loader entrypoint: `typus/services/sqlite_loader.py`
- CLI: `typus-load-sqlite --sqlite <path> [--tsv <path>] [--url <url>] [--replace] [--with-indexes|--no-with-indexes]`
- Default asset URL is controlled by `TYPUS_EXPANDED_TAXA_URL`.
- Cache root defaults to `~/.cache/typus` and can be overridden with `TYPUS_CACHE_DIR`.

## Optional Dependency Wiring

- Postgres backend: install `[postgres]` (`asyncpg`)
- SQLite backend: install `[sqlite]` (`aiosqlite`)
- Loader path: install `[loader]` (`polars`, `pandas`, `requests`, `tqdm`)

When adding imports in service modules, preserve optional dependency boundaries so core imports stay lightweight.

## Verification Checklist

- `make lint` for API/typing regressions in service code
- `make test` for SQLite-backed parity checks
- `make test-pg-smoke` and `make test-pg` for Postgres changes
- Run targeted tests for search, LCA, and ancestor traversal when touching taxonomy internals
