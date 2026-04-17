---
name: typus
description: "Typus-dev repo knowledge for the private development mirror of Polli taxonomy primitives, canonical geometry, and DTO contracts. Use before modifying typus or its dev/public release workflow."
version: "0.3.1"
x:
  source_repo: "typus-dev"
  source_branch: "main"
  source_commit: "3e547c8"
  package_version: "0.5.0"
  last_modified: "2026-04-17T21:30:00Z"
---

# Typus

Use this skill before changing Typus internals or any integration that depends
on Typus contracts.

## Quick Facts

- Package: `polli-typus` (`pyproject.toml` version `0.5.0`)
- Python target: `>=3.10`
- Public exports entrypoint: `typus/__init__.py`
- Optional extras: `[postgres]`, `[sqlite]`, `[loader]`, `[pgvector]`, `[dev]`, `[docs]`
- Core domains: taxonomy service contract, canonical geometry, track/classification DTOs
- Stack role: Typus is the canonical taxonomy authority and shared contract
  layer for downstream Polli systems
- Current shared-contract posture: Typus owns the canonical classification DTO
  surface consumed downstream by Linnaeus, Ibrida, and Polli UI/reporting
- Canonical contributor docs: `docs/contributing.md`
- Canonical bootstrap: `./dev/scripts/bootstrap-dev.sh`
- Canonical local quality gate: `make check-all`

## Dev/Public Contract

- Private dev repo: `polli-labs/typus-dev`
- Public release repo: `polli-labs/typus`
- Local main clone: `~/dev/typus/dev`
- Local worktrees: `~/dev/typus/wt/<branch>`
- Public inspection clone: `~/dev/typus/public/typus`
- Private repo is the day-to-day source of truth; public releases should be
  promoted intentionally from private work.
- If a task touches public promotion or public drift, also read
  `docs/migration/dev_public_release_contract.md`.

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
6. If the task touches public release work, read
   `docs/migration/dev_public_release_contract.md`.
7. Run `make check-all` before handoff. Use focused commands like
   `make typecheck` or `make test` only for narrower loops during
   implementation.

## Guardrails

- Use `uv` and Makefile workflows; do not add `pip install` flows.
- Do not add new runtime dependencies without maintainer approval.
- Land daily work in `typus-dev` first; treat public `typus` as a release
  surface, not a second independent mainline.
- Treat Typus as the stack's contract owner for taxonomy semantics and
  cross-repo geometry/classification DTOs; if a change will ripple into
  Linnaeus, Ibrida, ibridaDB, or Polli, capture that migration surface before
  coding.
- Preserve canonical geometry as TL-normalized `xywh` and convert only at boundaries.
- If you add a public Pydantic model, append it to `typus/export_schemas.py` and regenerate `typus/schemas/*.json`.

## References

- `references/taxonomy-primitives.md`
- `references/geometry-utilities.md`
- `references/integration-patterns.md`
