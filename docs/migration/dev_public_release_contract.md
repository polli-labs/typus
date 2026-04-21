---
title: "Typus Local Dev/Public Contract"
summary: "Repo-local remotes, paths, and standing overrides for typus-dev vs public typus."
tags: [docs, migration, release]
date: 2026-04-17
lastmod: 2026-04-17
---

# Purpose

This page is intentionally narrow. The canonical dev/public parity posture for
Polli split repos lives in the org-level `polli-dev-conventions` skill,
`references/release-ritual.md` in `agents-infra`.

Use this page only for Typus-specific local surfaces, remotes, and standing
overrides. Do not duplicate org-level promotion policy here.

# Local surfaces

- private integration clone: `~/dev/typus/dev`
- private worktrees: `~/dev/typus/wt/<branch>`
- public inspection/release clone: `~/dev/typus/public/typus`

# Remote contract

In the private integration clone:

- `origin` => `polli-labs/typus-dev`
- `public` => `polli-labs/typus`

# Standing local overrides

- Public inspection/release clone: `~/dev/typus/public/typus`
- No standing repo-specific private-only paths or public-owned exceptions are
  recorded here today.
- Keep this page limited to local paths, remotes, and explicit long-lived
  overrides when they exist.
