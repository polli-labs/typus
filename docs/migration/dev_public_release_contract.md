---
title: "Typus Dev/Public Release Contract"
summary: "Repository contract and promotion rules for private typus-dev vs public typus."
tags: [docs, migration, release]
date: 2026-04-17
lastmod: 2026-04-17
---

# Purpose

`polli-labs/typus-dev` is the private development surface for day-to-day work.
`polli-labs/typus` remains the public release surface.

`typus-dev/main` is the source of truth for public-safe changes.

# Local surfaces

- private integration clone: `~/dev/typus/dev`
- private worktrees: `~/dev/typus/wt/<branch>`
- public inspection/release clone: `~/dev/typus/public/typus`

# Remote contract

In the private integration clone:

- `origin` => `polli-labs/typus-dev`
- `public` => `polli-labs/typus`

# Release flow

1. Develop and validate changes in `typus-dev`.
2. Land approved private work to `typus-dev/main`.
3. Promote public-safe changes intentionally to `typus`.
4. Treat direct public commits as debt until they are classified.
5. Once the histories diverge materially, prefer explicit file-surface or
   release-PR sync over raw cherry-pick-by-default workflows.

# Guardrails

- Keep `~/dev/typus/public/typus` read-only except during explicit public
  promotion work.
- Leave Linear receipts with the local paths, remotes, verification commands,
  and any public follow-up still required.
