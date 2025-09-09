---
id: TYPUS-MODELS-0002
title: Align Detection/Track models to canonical TL-normalized xywh
status: open
priority: P0
component: models
milestone: v0.3.0
labels: [models, geometry, canonical]
owner: typus-agent
created: 2025-08-29
depends_on: [TYPUS-GEOM-0001]
blocks: [TYPUS-SCHEMA-0003, TYPUS-DOC-0004, TYPUS-REL-0005]
---

**Problem**
`typus` docs and examples still illustrate bboxes as free‑form `list[float]` in "tracks" docs, with no coordinate contract. We need to **use the canonical type** in our public models and docs.

**Scope**

1. **Models**

   * In `typus/models/detection.py` and/or `typus/models/tracks.py` (if present), ensure bbox‑carrying objects reference **`BBoxXYWHNorm`** for canonical fields rather than bare `list[float]`.
     (The codebase already has `BBox` & `EncodedMask` and exports image detection models; extend without breaking those.)
   * If legacy fields exist (e.g., `bbox: List[float]`), keep a **compat** field (deprecated in docstring) and add a new `bbox_norm: BBoxXYWHNorm`. Migration path: populate `bbox_norm` from adapters when constructing from legacy payloads.

2. **Factory/adapters**

   * Provide `from_raw_detection(raw: dict, *, upload_w: int, upload_h: int, provider: str | None = None)` helpers that produce canonicalized models using `BBoxMapper` or strict `bbox_norm` validation when already canonical.

3. **Validation**

   * Enforce canonical invariants at model boundaries; reject ambiguous inputs unless a `provider` is given.

**Tests**

* `tests/test_models_canonical_bbox.py`: constructing detections/tracks with canonical bbox; legacy path raises or adapts only with explicit provider hint.

**Acceptance**

* Canonical fields present and required in model constructors.
* Legacy examples in docs removed or clearly marked.
