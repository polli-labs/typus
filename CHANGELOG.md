# Changelog

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