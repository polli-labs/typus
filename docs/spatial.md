# Spatial Observations

Typus 0.8 defines the portable boundary for spatial evidence. It answers five
questions independently:

1. Is the subject present, and how visible is it?
2. Is the requested localization or segmentation task resolvable?
3. What was measured: a point, a normalized top-left bbox, or a mask artifact?
4. In which explicit coordinate space does that measurement live, and how can
   it be replayed into another declared space?
5. Which source observation and decoded evidence frame support it, and how was
   it produced?

These are not tracker models. A tracker, annotation application, inference
runtime, or database may carry its own lifecycle state and link observations by
`subject_id` or `parent_observation_ids` without redefining the evidence
contract.

## Core model

`SpatialObservation` contains:

- `presence`, `visibility`, and per-task `resolvability` as separate facts;
- an optional tagged `measurement` union;
- an optional source-authored `SourceObservationLocator`;
- an optional exact decoded `EvidenceFrameReference`;
- a `TransformChain` that registers every coordinate space and ordered affine
  step needed to replay the measurement;
- `ObservationProvenance`, whose `producer` and `derivation` axes keep facts
  such as human vs. model and measured vs. corrected vs. imputed independent.

Missing geometry does not imply absence. A present but occluded subject may be
unresolvable and carry no measurement. Conversely, an explicitly absent
observation cannot carry spatial geometry.

## Coordinate-space contract

Every `CoordinateSpace` declares:

- unit, origin, axis directions, coordinate extent, and raster dimensions;
- asset and optional crop identity;
- point, bbox-edge, and mask-grid semantics;
- bounds, numeric-representation, and alias policy.

`BBoxMeasurement` deliberately reuses `BBoxXYWHNorm`, so its coordinate space
must be normalized with a top-left origin. Points and mask references still name
their space explicitly. Transform steps name both endpoint spaces and carry the
actual affine matrix, rounding, bounds, invertibility, and round-trip tolerance;
a method label alone is never treated as replay provenance.

## Time and frame identity

Source-authored identity and decoded evidence identity are independent and
optional:

- `SourceObservationLocator` carries the authored clip, event, point index,
  frame index, and literal source time.
- `EvidenceFrameReference` carries media SHA-256, decoded-frame index, integer
  PTS, rational time base, and PTS-table SHA-256.

There is intentionally no FPS field and no rule that derives time from a frame
number. Variable-frame-rate media and changed decoder tables must remain
distinguishable.

## Real fixture

`tests/fixtures/spatial/pol-2068-observation.json` is a promoted-data fixture,
not a synthetic example. It binds one Saffron CLIP19 point to:

- the exact annotation and repair-batch digests;
- media and literal PTS-table digests;
- frame 79 at PTS 20224 with time base `1/15104`;
- the crop-to-source affine transform from the displayed normalized point to
  the source-frame normalized point.

The test suite parses the fixture, serializes it, parses it again, and replays
the transform to the expected source coordinate. It also rejects implicit FPS,
undeclared spaces, out-of-bounds points under `reject`, malformed union members,
and geometry on absent observations.

## Minimal example

```python
from typus import SpatialObservation

observation = SpatialObservation.model_validate_json(payload)

if observation.measurement is not None:
    space_id = observation.measurement.coordinate_space
    space = next(
        space for space in observation.transforms.spaces
        if space.space_id == space_id
    )
    print(space.asset_id, space.dimensions)
```

Generated JSON Schemas for the contract models ship in `typus/schemas/`.
