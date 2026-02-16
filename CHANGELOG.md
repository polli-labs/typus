# Changelog

## 0.5.0 – 2026-02-13
### Added
- `scripts/pg_smoke.py` and `make test-pg-smoke` for explicit optional-Postgres smoke validation (`current_database()` + table presence) before running `pg_optional` tests.
- Shared test/ops Postgres env utilities in `typus.services.pg_test_ops` (DSN resolution/normalization + availability classification), with coverage in `tests/test_pg_test_ops.py`.
- Typed backend exceptions (`TaxonomyServiceError`, `BackendConnectionError`, `TaxonNotFoundError`) and async lifecycle hooks (`aclose`, async context manager support) for taxonomy services.
- Type distribution marker `typus/py.typed` and `Typing :: Typed` classifier.

### Changed
- **Potentially breaking:** core install is now lightweight; TSV/HTTP loader dependencies moved behind optional extra `polli-typus[loader]`.
- `typus.services.load_expanded_taxa` now lazy-loads loader dependencies and returns a clear install hint when loader extras are missing.
- Test selector expressions are now sourced from Make targets (`make ci` / `make test-pg`) and reused by pre-commit + CI + publish workflows to avoid drift.
- Release/docs workflows are now `uv`-first and aligned with repo policy (no ad-hoc `pip` paths).
- Added `ty` project config + `make typecheck`; CI and publish test gates now enforce static type checks.
- SQLite and Postgres taxonomy backends now share common ancestry/search scoring helpers to reduce divergence.
- Optional Postgres tests/scripts now consume the same DSN resolution helper; removed hardcoded local DSN credential defaults.
- `tests/conftest.py` fixture is now deterministic SQLite-only (Postgres coverage lives in explicit `pg_optional` tests).

## 0.4.2 – 2025-11-22
### Added
- `TaxonSummary` / `TaxonTrailNode` models with `format_trail()` for UI-friendly lineage strings; exported JSON Schemas.
- Taxonomy services: `taxon_summary()` and `pollinator_groups_for_taxon()` helpers on both SQLite/Postgres backends.
- `PollinatorGroup` enum and mapping utilities (`pollinator_groups_for_ancestry`) covering Bee, Fly, Butterfly/Moth, Wasp, Beetle, Bird, Bat.
- Docs & examples for taxonomy summaries and pollinator groups; release notes under `dev/agents/typus-v0.4.2-notes.md`.

### Changed
- Version bumped to 0.4.2; schema bundle regenerated.

## 0.4.1
### Added
- Introduced `typus.ops` with portable geometry and tracking helpers:
  - Bounding box utilities: IoU (`iou_xyxy`), intersection (`intersect_xyxy`),
    clamping (`clamp_xyxy`), area (`area_xyxy`).
  - Pixel TL‑`xywh` converters complementing existing `xyxy` converters:
    `to_xywh_px()` and `from_xywh_px()`.
  - Tracking helpers: `group_detections_by_frame()` and
    `detection_xyxy_px()` to convert a detection to pixel `xyxy`.
### Docs
- New page `docs/reference/ops.md` summarizing helpers with examples and
  updated API index to include Ops.

## 0.4.0
### Removed
- Legacy `ancestry`/`ancestry_str` support fully removed from ORM and services. Modern databases and fixtures omit this column; use helpers like `ancestors()` to compute lineage when needed.

### Added
- Taxonomy services refactor:
  - Moved implementations under `typus/services/taxonomy/{abstract.py,postgres.py,sqlite.py}` with stable re‑exports.
  - PostgresTaxonomyService: added `ancestors()` and `get_many_batched()` to match SQLite parity.
- Name search (both backends): exact / prefix / substring with optional fuzzy re‑ranking; shared API on `AbstractTaxonomyService`.
- SQLite loader: default‑on index creation (`--with-indexes` flag; expression indexes on lower(name/commonName), btrees on rank/taxonID).
- Postgres index helper: idempotent CLI/API (`typus-pg-ensure-indexes`) for fast name search.
- Perf harness: scripts/perf_report.py with variance, optional verification, and EXPLAIN capture; report written to `dev/agents/perf_report.md`.
- Elevation service (Postgres‑only): `PostgresRasterElevation` with `elevation()` and `elevations()`; guarded tests and docs.

### Changed
- Documentation updates: taxonomy service guide, elevation service guide, README environment variables.
- Internal: removed legacy `typus/services/taxonomy.py` and `typus/services/sqlite.py`; imports updated.


## 0.3.0
### Added - Canonical Geometry
* **NEW**: `BBoxXYWHNorm` - Canonical top-left normalized bbox type with strict invariant validation
  - Immutable Pydantic model enforcing `[x, y, w, h]` format with `0 ≤ x,y ≤ 1`, `0 < w,h ≤ 1`
  - Coordinate bounds checking: `x + w ≤ 1`, `y + h ≤ 1`
  - Non-finite value rejection (NaN, Infinity)
* **NEW**: Provider-specific bbox mapping registry (`BBoxMapper`)
  - Built-in support for Gemini bottom-right origin conversion (`gemini_br_xyxy` mapper)
  - Pluggable architecture for custom coordinate system mappings
* **NEW**: Pixel ↔ normalized coordinate conversion utilities
  - `to_xyxy_px()` and `from_xyxy_px()` functions for round-trip conversion
  - Sub-pixel accuracy (≤0.5px error) across different image dimensions
  - Half-up rounding rule for pixel conversion (ties away from zero) ensures deterministic edge semantics
* **NEW**: Enhanced Track models with canonical geometry support
  - `Detection` model supports both `bbox_norm` (canonical) and `bbox` (legacy) fields
  - Factory method `Detection.from_raw_detection()` with provider mapping
  - Updated examples and validation to use canonical format
* **NEW**: JSON Schemas for canonical geometry types
  - Auto-generated schemas for `BBoxXYWHNorm`, `Detection`, `Track`, `TrackStats`
  - Available in `typus/schemas/` directory for API documentation
* **NEW**: Comprehensive documentation for canonical geometry
  - New `docs/geometry.md` with usage examples and migration guide
  - Updated `docs/models.md` to highlight canonical types over legacy formats
  - Updated `docs/tracks.md` with canonical bbox examples and provider mapping

### Changed
* **API**: Detection model now requires either `bbox_norm` or `bbox` field (validation enforced)
* **EXPORT**: Added canonical geometry types to public API exports
  - `from typus import BBoxXYWHNorm, BBoxMapper, to_xyxy_px, from_xyxy_px`
* **DOCS**: Legacy geometry types demoted to "Legacy" section with deprecation notices
* **EXAMPLES**: All documentation examples updated to use canonical format

### Backwards Compatibility
* **MAINTAINED**: All existing `bbox` (pixel) fields continue to work
* **MAINTAINED**: Existing `BBox` and geometry enums unchanged
* **MAINTAINED**: No breaking changes to public APIs

## 0.2.1
### Added
* **NEW**: Track models for video object tracking (`Detection`, `Track`, `TrackStats`)
  - Standardized data models for representing object trajectories through video
  - Support for raw detections, smoothed data, and enriched taxonomy information
  - Built-in validation workflow with status tracking (pending/validated/rejected)
  - Processing metadata for reproducibility (detector, tracker, smoothing methods)
  - Helper methods for track analysis (`is_continuous()`, `get_detection_at_frame()`)
  - Class method `from_raw_detections()` for easy track creation from dictionaries
  - **Track merging**: `merge_tracks()` method to reconnect incorrectly split tracks
  - **Convenience methods**: `duration` property, `frame_to_time()` conversion
* **NEW**: Comprehensive track model documentation in `docs/tracks.md`
* **TEST**: Full test suite for track models with 31 test cases including merge scenarios

### Changed
* Updated exports in `__init__.py` to include new track models

## 0.2.0
### Changed
* **BREAKING**: Complete removal of `ancestry` column from database operations
  - `ancestry` column fully deprecated and removed from all SQL queries and fixture generation
  - SQLite loader (`sqlite_loader.py`) no longer generates `ancestry` column
  - Test fixture generation script (`gen_fixture_sqlite.py`) updated to remove ancestry
  - Taxon model now returns empty ancestry list (can be computed on demand if needed)
  - ORM still maps `ancestry_str` for backward compatibility but it's marked deprecated

* **BREAKING**: Major performance improvements for LCA and distance calculations
  - LCA now uses efficient expanded L*_taxonID columns for major ranks (O(1) database queries)
  - Distance calculation rewritten to use recursive CTEs instead of building full ancestry paths
  - Removed dependency on non-existent `path` column (ltree) in production databases
  - Fixed transaction handling issues when ltree queries fail
  - Algorithms now leverage immediateAncestor and immediateMajorAncestor columns efficiently

* **BREAKING**: Fixed column name mismatches between SQLite and PostgreSQL
  - All raw SQL queries updated to use correct production column names (`taxonID` not `taxon_id`)
  - Consistently uses `immediateAncestor_taxonID` and `immediateMajorAncestor_taxonID`
  - Added proper quoting for all column names in SQL queries

* **FIX**: Resolved MissingGreenlet error in pure asyncio contexts (FastAPI/uvicorn)
  - Service no longer attempts to access deferred columns that may not exist
  - Fixed _row_to_taxon methods to handle missing columns gracefully
  - Added robust handling for databases without ancestry column

* **NEW**: CI-friendly mock tests for async compatibility verification
* **NEW**: Comprehensive documentation for expanded_taxa table structure
* **CHG**: Major ranks list corrected (uses 30 for tribe, not 34 for family)
* **TEST**: Added comprehensive async compatibility test suite

## 0.1.11
* added automated docs deployment to docs.polli.ai/typus/

## 0.1.10
* relaxed dependency constraints for `polars` (<2) and `requests` (<4)

## 0.1.9
* NEW: `sqlite_loader` service with `typus-load-sqlite` CLI for offline databases
* CHG: Postgres service falls back to recursive CTEs when path columns missing
* DOC: Added MkDocs site with `offline_mode.md` and `expanded_taxa.md`
* TEST: expanded suite covering offline loader and LCA cases
* DEP: optional extras for PyArrow and MkDocs

## 0.1.8 – 2025-06-29
### Changed
* **BREAKING (DB fixture only)** – parent columns in `expanded_taxa` (both SQLite fixture and expected in source TSVs for fixture generation) renamed to `immediateAncestor_taxonID`, `immediateAncestor_rankLevel`, `immediateMajorAncestor_taxonID`, `immediateMajorAncestor_rankLevel`. The `scripts/gen_fixture_sqlite.py` script now generates these columns and expects source TSVs to be compatible with this structure if they contain pre-computed parentage (though it primarily derives them from L*_taxonID columns).
  Old Python attribute names (`true_parent_id`, `true_parent_rank_level`) remain as deprecated synonyms in the ORM, mapping to the new underlying columns via `parent_id` etc. Code that queries raw SQL against the SQLite fixture must update to use the new column names.

## 0.1.7 – 2025-05-26
* FIX: Version detection bug - package correctly looks for "polli-typus" instead of "typus"

## 0.1.6 – 2025-05-21
* NEW: `typus.services.SQLiteTaxonomyService` – fully-functional offline, fixture-backed taxonomy service
* NEW: ExpandedTaxa ORM v2 with materialized rank columns for all RankLevel enum values
* NEW: Enhanced SQLite fixture with computed ancestry strings and parent relationships
* NEW: Stronger LCA/distance test-suite with hardened expectations and edge case coverage
* NEW: Broader sample fixture including Apocrita + Aculeata lineage data
* CHG: Promoted SQLite service from test helper to main library export

## 0.1.5 – 2025-05-21
* Initial release with core taxonomy services and models.
