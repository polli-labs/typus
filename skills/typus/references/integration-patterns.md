# Typus Integration Patterns

Use this reference when planning or implementing Typus changes that affect downstream repositories.

## Integration Principles

- Treat `typus/__init__.py` as the public API contract.
- Depend on service abstractions (`AbstractTaxonomyService`) instead of backend details.
- Convert external geometry inputs at system boundaries, then keep canonical `BBoxXYWHNorm` internally.
- Prefer additive, backward-compatible model changes unless a breaking release is intentional.

## Stack Role

Typus currently plays four distinct roles in the Polli stack:

- canonical taxonomy authority for biological taxon IDs, names, ancestry, LCA,
  and distance queries
- canonical geometry and detection/track DTO surface at the package boundary
- shared classification/result contract owner for downstream inference and UI
  consumers
- API/service facade over data ultimately sourced from ibridaDB tables and
  SQLite extracts

That means Typus changes often propagate outward even when the repo-local diff
looks small.

## Common Consumer Patterns

- service callers consume taxonomy APIs (`get_taxon`, `search_taxa`, `ancestors`, `lca`, `distance`)
- inference/tracking callers consume DTOs (`Detection`, `Track`, classification models)
- UI/reporting callers consume summary helpers (`TaxonSummary`, `PollinatorGroup`)

Concrete downstream ownership today:

- `ibridaDB` is the authoritative storage plane for `expanded_taxa` and related
  taxonomy/elevation data; Typus is the service and contract layer over that
  data
- `linnaeus` depends on Typus-owned taxonomy and classification contracts for
  inference-facing outputs and postprocessing
- `ibrida` and serving/reporting flows consume Typus geometry and
  classification/taxonomy DTOs rather than re-defining their own
- `polli` UI/reporting surfaces should treat Typus-owned generated schemas and
  DTOs as canonical when the data crosses the API boundary

If you need to change these surfaces, document migration impact before code lands.

## Sequencing Rule

For shared contract changes, the safe rollout order is usually:

1. `typus`
2. `linnaeus`
3. `ibrida`
4. `polli`

If a change does not fit that order, call it out explicitly in the issue or
release notes before implementation.

## Dependency and Environment Pattern

- Keep runtime core light; optional backends stay behind extras.
- Use extras from `pyproject.toml`:
  - `[postgres]` for live Postgres taxonomy backends
  - `[sqlite]` for offline/test SQLite backend
  - `[loader]` for SQLite ingest and download tooling
- Keep loader-only dependencies out of top-level imports.

## Schema Lifecycle Pattern

When adding or changing public Pydantic models:

1. Update model code under `typus/models/`.
2. Add the dotted model path to `typus/export_schemas.py`.
3. Regenerate schemas (`uv run python -m typus.export_schemas`).
4. Commit generated files under `typus/schemas/`.
5. Run schema freshness checks (`make schemas-check` or `make ci`).

## Testing Pattern

Run fast gates first, then backend-specific gates as needed:

1. `make format`
2. `make lint`
3. `make typecheck`
4. `make test` (SQLite-focused default suite)
5. For Postgres-sensitive work: `make test-pg-smoke` then `make test-pg`

For taxonomy logic changes, add targeted tests under `tests/` covering both behavior and edge cases.

## Release and Compatibility Guardrails

- Coordinate contract changes with downstream repositories before release.
- Highlight API changes in `CHANGELOG.md`.
- Avoid hidden behavior drift in `search_taxa`, rank inference, or geometry invariants.
- Keep docs current (`README.md`, relevant files in `docs/`) when public behavior changes.
