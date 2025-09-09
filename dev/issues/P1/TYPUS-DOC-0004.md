---
id: TYPUS-DOC-0004
title: Document canonical TL-normalized xywh + provider mappings; update model docs
status: open
priority: P1
component: docs
milestone: v0.3.0
labels: [docs, geometry, migration]
owner: typus-agent
created: 2025-08-29
depends_on: [TYPUS-GEOM-0001, TYPUS-MODELS-0002]
---

**Work**

* Add a new `docs/geometry.md` explaining canonical invariants & examples; link from `docs/index.md`.
* Update `docs/models.md` geometry section (currently lists many formats) to **highlight canonical** and demote others as non‑canonical.
* Update `docs/tracks.md` examples to use `BBoxXYWHNorm` and remove "list[float]" bboxes.

**Acceptance**

* MkDocs build includes a **Canonical geometry** page.
* Examples use canonical types end‑to‑end.
