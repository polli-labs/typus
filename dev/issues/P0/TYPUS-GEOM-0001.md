---
id: TYPUS-GEOM-0001
title: Canonical bbox types + provider mapping registry
status: open
priority: P0
component: geometry
milestone: v0.3.0
labels: [schema, geometry, canonical, non-breaking]
owner: typus-agent
created: 2025-08-29
blocks: [TYPUS-MODELS-0002, TYPUS-SCHEMA-0003, TYPUS-DOC-0004]
---

**Motivation**
`typus` must be the **single canonical package** for geometry contracts across org repos. We will introduce an immutable, strictly‑validated **canonical bbox** type (TL‑origin, normalized `[x, y, w, h]`) and a tiny registry for **provider‑specific mappings** (initially: Gemini BR/xyxy → canonical). Current docs and examples still show ad‑hoc "list[float]" bboxes and multiple formats; we need a contract lock‑in here.

**Scope (deliverables)**

1. **Type: `BBoxXYWHNorm` (Pydantic, frozen)**

   * Fields: `x: float`, `y: float`, `w: float`, `h: float`
   * Invariants: `0 ≤ x ≤ 1`, `0 ≤ y ≤ 1`, `0 < w ≤ 1`, `0 < h ≤ 1`, `x + w ≤ 1 + 1e-9`, `y + h ≤ 1 + 1e-9`
   * `model_config = ConfigDict(frozen=True)` for immutability.

2. **Converters (pure functions)**

   * `to_xyxy_px(b: BBoxXYWHNorm, W: int, H: int) -> tuple[int, int, int, int]`
   * `from_xyxy_px(x1: float, y1: float, x2: float, y2: float, W: int, H: int) -> BBoxXYWHNorm`
     (Clamp with ε=1e‑9; assert `x2 ≥ x1`, `y2 ≥ y1` pre‑normalize.)

3. **Provider mapping registry**

   * `class BBoxMapper:` `register(name: str, fn: Callable)`, `get(name: str) -> Callable`
   * Provide entry: `"gemini_br_xyxy"` → function that takes Gemini **bottom‑right–origin** xyxy + `(upload_w, upload_h)` and returns canonical `BBoxXYWHNorm`. (Document the BR→TL math in code docstrings.)

4. **Inferences (optional, guard‑railed)**

   * `infer_from_raw(raw: Sequence[float] | dict, upload_w: int, upload_h: int, *, prefer="tl_xywh_norm") -> BBoxXYWHNorm`
     with explicit failure unless a provider hint or unambiguous normalized TL‑xywh is detected. (No silent magic.)

5. **Public API exports**

   * Re‑export in `typus/models/__init__.py`: `BBoxXYWHNorm`, `BBoxMapper`, and the converter functions.
     Current exports only include `BBox`, `EncodedMask`, `InstancePrediction`, `ImageDetectionResult`; add the new canonical pieces next to them.

**Tests**

* `tests/test_geometry_bbox_norm.py`: validators, boundary cases (`x+w==1`, `w==1`).
* `tests/test_geometry_px_roundtrip.py`: pix ↔ norm round‑trip within 0.5px.
* `tests/test_provider_gemini_mapping.py`: golden vectors for BR/xyxy → TL/xywh on representative dims.

**Acceptance**

* All new tests pass; no mutation of `BBoxXYWHNorm` after construction.
* Public imports: `from typus import BBoxXYWHNorm` succeed.
* Mappers are pluggable via `BBoxMapper.register(...)`.

**Notes**
This is **additive**; no existing import paths break. Follow repo's dev workflow & test tooling (`pytest`, `ruff`, `pre‑commit`).
