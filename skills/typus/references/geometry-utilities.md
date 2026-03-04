# Typus Geometry Utilities

Use this reference when working on bbox contracts, mapper conversions, or track geometry fields.

## Canonical Geometry Contract

Primary file: `typus/models/geometry.py`
Supplemental docs: `docs/geometry.md`

Canonical type:

- `BBoxXYWHNorm` (top-left origin, normalized `[x, y, w, h]`)
- Invariants:
  - `0 <= x <= 1`
  - `0 <= y <= 1`
  - `0 < w <= 1`
  - `0 < h <= 1`
  - `x + w <= 1` and `y + h <= 1` (with epsilon tolerance)

Conversion helpers:

- `to_xyxy_px(bbox, W, H)` uses half-up rounding semantics
- `from_xyxy_px(x1, y1, x2, y2, W, H)` validates and clamps safely

## Mapper Registry

`BBoxMapper` is the provider registry for boundary conversions.

- Register provider mapper with `BBoxMapper.register(name, fn)`
- Resolve mapper with `BBoxMapper.get(name)`
- Inspect available providers with `BBoxMapper.list_providers()`
- Built-in provider: `gemini_br_xyxy`

Pattern: convert at boundaries, keep internal storage canonical.

## Detection and Track Models

Primary file: `typus/models/tracks.py`

- `Detection` supports canonical `bbox_norm` and legacy `bbox`
- `Detection.from_raw_detection(...)` enforces provider-aware conversion and validation
- `Track` aggregates detections and normalizes derived frame bounds

When touching these models:

- preserve compatibility for both `bbox_norm` and legacy `bbox` paths
- avoid implicit assumptions about provider coordinate systems
- keep validation errors explicit and actionable

## Geometry Ops Helpers

Primary file: `typus/ops/bbox.py`

- overlap math: `intersect_xyxy`, `iou_xyxy`, `area_xyxy`
- bounds handling: `clamp_xyxy`
- format conversions: `xyxy_to_xywh`, `xywh_to_xyxy`, `to_xywh_px`, `from_xywh_px`

Use `typus/ops/` helpers instead of duplicating bbox math in service code.

## Change Safety Checklist

- Ensure canonical invariants remain strict and explicit.
- Keep pixel edge semantics consistent in conversions.
- Add or update tests when mapper logic or validation behavior changes.
- Coordinate any geometry contract changes with downstream consumers before release.
