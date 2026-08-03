# Typus Geometry Utilities

Use this reference when working on bbox contracts, mapper conversions, or
portable spatial observations.

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

## Spatial Observation Models

Primary file: `typus/models/spatial.py`
Supplemental docs: `docs/spatial.md`

- `SpatialObservation` keeps presence, visibility, task resolvability,
  measurement, frame identity, transforms, and provenance orthogonal.
- `PointMeasurement`, `BBoxMeasurement`, and `MaskReference` form a tagged union.
- `CoordinateSpace` declares unit, origin, axes, extent, dimensions, asset/crop
  identity, grid semantics, and bounds/numeric policy.
- `TransformChain` carries replayable affine matrices rather than method labels alone.
- `SourceObservationLocator` and `EvidenceFrameReference` are independent;
  decoded evidence uses literal PTS plus rational time base, never implicit FPS.

When touching this contract:

- preserve explicit coordinate and temporal interpretation
- keep missing measurement distinct from absence and task non-resolvability
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
- Validate shared-contract changes against a real downstream round-trip fixture.
