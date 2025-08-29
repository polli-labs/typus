**Superseded by:** `TYPUS-GEOM-0001`, `TYPUS-MODELS-0002`, `TYPUS-SCHEMA-0003`, `TYPUS-DOC-0004`, `TYPUS-REL-0005`.
**Rationale:** Split work into canonical type + mappers, models alignment, schemas, and docs; release tracked in `TYPUS-REL-0005`.

# BBOX-CANONICAL-0001: Update Track models to align with ibrida v0.6.3 canonical bbox format

## Issue Classification
- **Priority**: P1 (API contract alignment)
- **Component**: typus.models.tracks  
- **Filed**: 2025-08-29
- **Milestone**: typus v0.2.x (next release)

## Problem Statement

The typus Track models currently accept bbox coordinates in generic `list[float]` format without specifying the coordinate system contract. With ibrida v0.6.3's bbox geometry overhaul standardizing on **canonical format**, typus should align its models and documentation to prevent integration issues.

## Current Implementation

In `typus/models/tracks.py`, the Detection model defines:

```python
bbox: list[float] = Field(
    ..., min_length=4, max_length=4, description="Bounding box [x, y, width, height] in pixels"
)
```

This generic description doesn't specify:
- Coordinate origin (top-left vs bottom-right)
- Normalization (pixel vs normalized [0,1])
- Coordinate order (xywh vs xyxy)

## Target Canonical Format

Based on ibrida v0.6.3 implementation:
- **Format**: `[x, y, width, height]`
- **Origin**: Top-left corner
- **Coordinates**: Normalized float values in `[0, 1]` range
- **Validation**: `0 ≤ x ≤ 1`, `0 ≤ y ≤ 1`, `0 < w ≤ 1`, `0 < h ≤ 1`, `x+w ≤ 1`, `y+h ≤ 1`

## Required Changes

### 1. Update Field Documentation

```python
bbox: list[float] = Field(
    ..., 
    min_length=4, 
    max_length=4, 
    description="Canonical bounding box [x, y, width, height] - top-left origin, normalized [0,1]"
)
```

### 2. Add Validation (Optional)

Consider adding a Pydantic validator to ensure canonical compliance:

```python
@field_validator('bbox')
def validate_canonical_bbox(cls, v):
    if len(v) != 4:
        raise ValueError('bbox must have exactly 4 elements')
    
    x, y, w, h = v
    if not (0 <= x <= 1 and 0 <= y <= 1):
        raise ValueError('bbox x,y must be in [0,1] range')
    if not (0 < w <= 1 and 0 < h <= 1):
        raise ValueError('bbox width,height must be in (0,1] range')
    if x + w > 1.001 or y + h > 1.001:  # Allow small epsilon
        raise ValueError('bbox must not exceed frame boundaries')
        
    return v
```

### 3. Update Documentation

Update `docs/tracks.md` examples to use canonical format:

```python
detection = Detection(
    frame_number=100,
    bbox=[0.1, 0.2, 0.5, 0.6],  # Canonical: top-left normalized xywh
    confidence=0.95,
    taxon_id=47219,
    scientific_name="Apis mellifera"
)
```

### 4. Migration Guidance

Add adapter function for legacy pixel formats:

```python
def pixel_to_canonical_bbox(pixel_bbox: list[float], img_width: int, img_height: int) -> list[float]:
    """Convert pixel bbox to canonical normalized format."""
    x_px, y_px, w_px, h_px = pixel_bbox
    return [
        x_px / img_width,
        y_px / img_height,
        w_px / img_width,
        h_px / img_height
    ]
```

## API Compatibility Impact

- **Breaking Change**: No (current validation accepts any 4-element float list)
- **Behavioral Change**: Yes (documentation clarifies expected format)
- **Migration Path**: Existing pixel-space data needs conversion

## Integration Benefits

1. **Consistent Contract**: Matches ibrida v0.6.3 canonical format
2. **Better Validation**: Prevents coordinate system mix-ups
3. **Clearer Documentation**: Removes ambiguity for API consumers
4. **Future-Proofing**: Aligns with ecosystem bbox format standards

## Implementation Notes

- Coordinate with ibrida team on final canonical format specification
- Consider backward compatibility for existing typus data
- Update JSON schema exports to reflect canonical format
- Add unit tests for bbox validation edge cases

## Cross-Reference

- **Source**: ibrida v0.6.3 bbox geometry overhaul (PR #20)
- **Related**: ibrida BBOX-ORIGIN-0001, BBOX-OVERLAY-0004
- **Spec**: `ibrida/src/ibrida/distill/response_validation.py` canonical format implementation