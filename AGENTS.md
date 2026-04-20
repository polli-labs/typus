---
title: "Typus-dev — Agent/Dev Guide"
doc_type: "agents"
status: "active"
owner: "polli-labs"
last_modified: "2026-04-17T21:30:00Z"
last_reviewed: "2026-04-17T21:30:00Z"
scope: "repository:typus-dev"
---

# Typus-dev — Agent/Dev Guide

Repo-specific guide for `polli-labs/typus-dev`, the private development mirror
for Polli Typus.

## Repository contract

- Private dev repo: `polli-labs/typus-dev`
- Public release repo: `polli-labs/typus`
- Local main clone: `~/dev/typus/dev`
- Local worktrees: `~/dev/typus/wt/<branch>`
- Public inspection clone: `~/dev/typus/public/typus`
- Private remote: `origin`
- Public remote: `public`

Use the org-level `polli-dev-conventions` release ritual as the canonical
dev/public policy for this repo family.

For dev/public guidance, use:
- Org policy: `polli-dev-conventions` -> `references/release-ritual.md`
- Repo-local paths, remotes, and standing overrides: `docs/migration/dev_public_release_contract.md`

## Start Here

1. Confirm whether you are in `~/dev/typus/dev` or a worktree under
   `~/dev/typus/wt/<branch>`.
2. Read `docs/contributing.md` and `skills/typus/SKILL.md`.
3. Use `./dev/scripts/bootstrap-dev.sh` if the environment looks stale.
4. Run `make check-all` before handoff.
5. Leave receipts: changed files, verification commands, commit SHA, PR link,
   and any public follow-up still required.

## Canonical model

- Package: `polli-typus`
- Public exports entrypoint: `typus/__init__.py`
- Python target: `>=3.10`
- Canonical bootstrap: `./dev/scripts/bootstrap-dev.sh`
- Canonical local quality gate: `make check-all`

Typus provides Polli taxonomy primitives, canonical geometry helpers, and the
track or classification DTOs used across the broader stack.

## Key repo surfaces

- `typus/` — package code and public exports
- `typus/export_schemas.py` — JSON Schema export surface for public models
- `docs/contributing.md` — contributor setup and CI-friendly test policy
- `scripts/` — bootstrap helpers and fixture tooling
- `skills/typus/` — repo-local agent skill
- `tests/` — unit, contract, and optional database coverage

## Working rules

- Use `uv`, not `pip`.
- Keep new syntax compatible with Python 3.10+.
- Do not add new runtime dependencies without maintainer approval.
- Run the Makefile targets humans use:
  - `make format`
  - `make lint`
  - `make typecheck`
  - `make test`
  - `make check-all`
- If you add a public Pydantic model, append it to `typus/export_schemas.py`
  and regenerate `typus/schemas/*.json`.
- Update `README.md` when the public API grows.
- For public-promotion work, follow the org-level `polli-dev-conventions`
  policy and use `docs/migration/dev_public_release_contract.md` for this
  repo's local paths and remotes.

## Testing notes

- New modules should include unit tests under `tests/`.
- Optional PostgreSQL-backed tests may require `TYPUS_TEST_DSN`; keep CI-safe
  mock coverage in place when a real database is not available.
- Prefer the contributor guide's exact `pytest -k` filters when matching CI or
  pre-commit behavior.

## Canonical commands

```bash
./dev/scripts/bootstrap-dev.sh
make check-all
make format
make lint
make typecheck
make test
```
