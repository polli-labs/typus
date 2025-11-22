# Typus v0.4.2 – Taxonomy summaries & pollinator groups

## Added API
- `TaxonTrailNode`, `TaxonSummary` (typus.models.summary)
  - `TaxonSummary.format_trail(separator=" → ", include_vernacular=True)`
- Service helpers (both backends):
  - `taxon_summary(taxon_id: int, *, major_ranks_only: bool = True) -> TaxonSummary`
  - `pollinator_groups_for_taxon(taxon_id: int) -> set[PollinatorGroup]`
- Pollinator helpers:
  - `PollinatorGroup` enum (`Bee`, `Butterfly/Moth`, `Fly`, `Wasp`, `Beetle`, `Bird`, `Bat`, `Other`)
  - `pollinator_groups_for_ancestry(ancestry: Iterable[int])`

## Notes for WFC Moments / ibrida‑SAM3
- UI taxonomy trails can call `taxon_summary(...)` and display `summary.trail` or `summary.format_trail()`.
- Pollinator cards can label with `pollinator_groups_for_taxon(...)`; mapping is coarse and opinionated.
- Pipelines **must not** hard‑depend on v0.4.2: if unavailable, fall back to in‑app lineage strings.

## Mapping roots (expanded_taxa snapshot 2025‑06‑28)
- Bee: Anthophila `630955`
- Butterfly/Moth: Lepidoptera `47157`
- Fly: Diptera `47822`
- Wasp: Vespidae `52747`
- Beetle: Coleoptera `47208`
- Bird: Aves `3`
- Bat: Chiroptera `40268`

## Release checklist
- Version bumped to `0.4.2`; schemas regenerated.
- Tests: `make ci` (SQLite); optional PG tests remain guarded by `TYPUS_TEST_DSN`.
- Build/publish: follow `build/typus_publish.md` (tag `v0.4.2`, TestPyPI→PyPI, push tag + HEAD).
