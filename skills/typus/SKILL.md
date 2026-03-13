---
name: typus
description: "Typus repo knowledge for taxonomy primitives, canonical geometry, and integration-safe usage patterns. Use before modifying typus or consumers of taxonomy/geometry DTO contracts."
version: "0.3.0"
x:
  source_repo: "typus"
  source_branch: "main"
  source_commit: "a5e6742"
  package_version: "0.5.0"
  last_modified: "2026-03-13T18:35:00Z"
---

# Typus

Use this skill before changing Typus internals or any integration that depends on Typus contracts.

## Quick Facts

- Package: `polli-typus` (`pyproject.toml` version `0.5.0`)
- Python target: `>=3.10`
- Public exports entrypoint: `typus/__init__.py`
- Optional extras: `[postgres]`, `[sqlite]`, `[loader]`, `[pgvector]`, `[dev]`, `[docs]`
- Core domains: taxonomy service contract, canonical geometry, track/classification DTOs
- Canonical contributor docs: `docs/contributing.md`
- Canonical bootstrap: `./dev/scripts/bootstrap-dev.sh`
- Canonical local quality gate: `make check-all`

## Trigger Conditions

Use this skill when the task touches one or more of these:

- taxonomy primitives or taxonomy service behavior
- canonical bbox geometry or provider mapping
- track/detection/classification model contracts
- schema export surface used by downstream validation
- Typus integration planning in other Polli repositories

## Working Sequence

1. Read `typus/__init__.py` first to confirm the public API surface.
2. Load only the reference file needed for the task:
   - taxonomy contract and rank primitives: `references/taxonomy-primitives.md`
   - bbox and geometry helpers: `references/geometry-utilities.md`
   - downstream usage and compatibility guardrails: `references/integration-patterns.md`
3. Keep changes backwards compatible unless a breaking change is explicitly requested.
4. Use `docs/contributing.md` for contributor setup and gate policy instead of duplicating setup steps in task notes.
5. Bootstrap or resync the local dev environment with `./dev/scripts/bootstrap-dev.sh` when needed.
6. Run `make check-all` before handoff. Use focused commands like `make typecheck` or `make test` only for narrower loops during implementation.

## Guardrails

- Use `uv` and Makefile workflows; do not add `pip install` flows.
- Do not add new runtime dependencies without maintainer approval.
- Preserve canonical geometry as TL-normalized `xywh` and convert only at boundaries.
- If you add a public Pydantic model, append it to `typus/export_schemas.py` and regenerate `typus/schemas/*.json`.

## References

- `references/taxonomy-primitives.md`
- `references/geometry-utilities.md`
- `references/integration-patterns.md`
