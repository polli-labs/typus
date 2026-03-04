# Typus Integration Patterns

Use this reference when planning or implementing Typus changes that affect downstream repositories.

## Integration Principles

- Treat `typus/__init__.py` as the public API contract.
- Depend on service abstractions (`AbstractTaxonomyService`) instead of backend details.
- Convert external geometry inputs at system boundaries, then keep canonical `BBoxXYWHNorm` internally.
- Prefer additive, backward-compatible model changes unless a breaking release is intentional.

## Common Consumer Patterns

- service callers consume taxonomy APIs (`get_taxon`, `search_taxa`, `ancestors`, `lca`, `distance`)
- inference/tracking callers consume DTOs (`Detection`, `Track`, classification models)
- UI/reporting callers consume summary helpers (`TaxonSummary`, `PollinatorGroup`)

If you need to change these surfaces, document migration impact before code lands.

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
