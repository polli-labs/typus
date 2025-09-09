---
id: TYPUS-SCHEMA-0003
title: Export JSON Schemas for BBoxXYWHNorm and updated detection/track models
status: open
priority: P1
component: schemas
milestone: v0.3.0
labels: [schemas, tooling]
owner: typus-agent
created: 2025-08-29
depends_on: [TYPUS-GEOM-0001, TYPUS-MODELS-0002]
---

**Work**

* Update `typus/export_schemas.py` `MODELS` list to include `typus.models.geometry.BBoxXYWHNorm` and any updated detection/track models; run `python -m typus.export_schemas` to emit JSON into `typus/schemas/`.
* Commit generated `*.json` files.

**Acceptance**

* `typus/schemas/BBoxXYWHNorm.json` exists and contains the invariants.
* CI step prints `wrote BBoxXYWHNorm.json` along with the others.
