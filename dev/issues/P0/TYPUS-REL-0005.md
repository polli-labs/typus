---
id: TYPUS-REL-0005
title: Release typus v0.3.0 (canonical geometry)
status: open
priority: P0
component: release
milestone: v0.3.0
labels: [release, versioning, docs]
owner: typus-agent
created: 2025-08-29
depends_on: [TYPUS-GEOM-0001, TYPUS-MODELS-0002, TYPUS-SCHEMA-0003, TYPUS-DOC-0004]
---

**Work**

* Bump version to `0.3.0` in packaging metadata; keep CI/publish workflow as is.
* Update CHANGELOG: "Added canonical geometry types & mappings; updated models/docs; schemas exported."
* Ensure `__all__` re‑exports include `BBoxXYWHNorm` and `BBoxMapper`.
* Tag & publish (TestPyPI → PyPI) and deploy docs via existing GH Actions.

**Acceptance**

* Wheel published; docs deployed; schemas updated.
