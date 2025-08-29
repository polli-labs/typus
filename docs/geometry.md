# Canonical Geometry

As of `typus v0.3.0`, the library provides canonical geometry types that establish a **single source of truth** for bounding box coordinates across all Polli-Labs repositories.

## 📋 **Contract**

The canonical geometry contract establishes these **immutable rules**:

- **🎯 Origin**: Top-left corner (0,0) at upper-left of image
- **📏 Format**: `[x, y, width, height]` - never xyxy or center-based
- **🔢 Normalization**: All values in `[0, 1]` range relative to image dimensions  
- **🔒 Immutability**: `BBoxXYWHNorm` instances cannot be modified after creation
- **✅ Invariants**: Enforced at construction time with precise error messages
- **🎚️ Tolerance**: Boundary checks use ε=1e-9 for floating-point precision
- **📐 Pixel Edges**: In pixel space, xyxy coordinates have **exclusive** x2/y2 bounds
- **🔄 Rounding**: Pixel conversions round to nearest integer (ties away from zero)

## Canonical Bounding Box Format

The canonical format is:

- **Coordinate System**: Top-left origin (0,0 at top-left corner)
- **Format**: `[x, y, width, height]` 
- **Normalization**: All values in `[0, 1]` range relative to image dimensions
- **Type**: `BBoxXYWHNorm` (immutable Pydantic model)

### Invariants

The `BBoxXYWHNorm` type enforces these constraints:

- `0 ≤ x ≤ 1` (left coordinate)
- `0 ≤ y ≤ 1` (top coordinate)  
- `0 < w ≤ 1` (width, must be positive)
- `0 < h ≤ 1` (height, must be positive)
- `x + w ≤ 1` (cannot exceed right image boundary)
- `y + h ≤ 1` (cannot exceed bottom image boundary)

## Usage Examples

### Creating Canonical Bboxes

```python
from typus import BBoxXYWHNorm

# Create a bbox covering 20% to 70% horizontally, 10% to 60% vertically
bbox = BBoxXYWHNorm(x=0.2, y=0.1, w=0.5, h=0.5)

# The bbox is immutable
# bbox.x = 0.3  # This would raise TypeError
```

### 🔄 **Coordinate System Conversions** 

Here are worked examples showing conversions between different coordinate systems:

#### **Example: 100×100 image, object from (20,10) to (70,60)**

| System | Representation | Notes |
|--------|----------------|--------|
| **Canonical (TL-xywh-norm)** | `x=0.2, y=0.1, w=0.5, h=0.5` | ⭐ **TARGET FORMAT** |
| **TL-pixel-xyxy** | `(20, 10, 70, 60)` | x2,y2 exclusive bounds |
| **TL-pixel-xywh** | `(20, 10, 50, 50)` | width = x2-x1, height = y2-y1 |
| **BR-pixel-xyxy (Gemini)** | `(30, 40, 80, 90)` | Bottom-right origin |

```python
from typus import BBoxXYWHNorm, to_xyxy_px, from_xyxy_px, BBoxMapper

# 1. Create canonical bbox
bbox = BBoxXYWHNorm(x=0.2, y=0.1, w=0.5, h=0.5)

# 2. Convert to TL pixel coordinates  
x1, y1, x2, y2 = to_xyxy_px(bbox, W=100, H=100)
print(f"TL-pixel-xyxy: ({x1}, {y1}, {x2}, {y2})")  # (20, 10, 70, 60)

# 3. Convert from TL pixel coordinates
bbox_from_px = from_xyxy_px(20, 10, 70, 60, W=100, H=100)
print(f"Round-trip: {bbox_from_px}")  # x=0.2, y=0.1, w=0.5, h=0.5

# 4. Convert from Gemini BR coordinates  
gemini_mapper = BBoxMapper.get("gemini_br_xyxy")
bbox_from_gemini = gemini_mapper(30, 40, 80, 90, W=100, H=100)
print(f"From Gemini: {bbox_from_gemini}")  # x=0.2, y=0.1, w=0.5, h=0.5
```

#### **Pixel Edge Semantics**

- **Inclusive**: `x1, y1` (top-left pixel included)
- **Exclusive**: `x2, y2` (bottom-right pixel NOT included)
- **1-pixel box**: `(x1=20, y1=10, x2=21, y2=11)` covers exactly 1 pixel
- **Rounding**: `int(round(coordinate))` with ties away from zero

## Provider Mapping

Different vision APIs use different coordinate systems. The `BBoxMapper` registry provides conversions from provider-specific formats to canonical format.

### Supported Providers

#### Gemini (Bottom-Right Origin)

Gemini Vision API uses bottom-right origin coordinates. Use the built-in mapper:

```python
from typus import BBoxMapper

# Get the Gemini mapper
mapper = BBoxMapper.get("gemini_br_xyxy")

# Convert Gemini bottom-right xyxy to canonical
gemini_coords = [50, 50, 80, 90]  # Bottom-right origin pixel coordinates
image_width, image_height = 100, 100

canonical_bbox = mapper(*gemini_coords, image_width, image_height)
```

#### Provider Discovery

List all available providers for introspection:

```python
from typus import BBoxMapper

# Discover available providers
providers = BBoxMapper.list_providers()
print(providers)  # ['gemini_br_xyxy', ...]

# Use a specific provider by canonical name
mapper = BBoxMapper.get("gemini_br_xyxy")
```

#### Custom Providers

Register your own provider mappings:

```python
from typus import BBoxMapper, BBoxXYWHNorm

def my_provider_mapper(x1, y1, x2, y2, W, H):
    # Custom conversion logic here
    # Must return BBoxXYWHNorm
    return BBoxXYWHNorm(
        x=x1/W, y=y1/H,
        w=(x2-x1)/W, h=(y2-y1)/H
    )

BBoxMapper.register("my_provider", my_provider_mapper)

# Use it
bbox = BBoxMapper.get("my_provider")(10, 20, 50, 60, 100, 100)
```

## Integration with Models

### Detection Models

The `Detection` model (used in tracks) supports both canonical and legacy bbox formats:

```python
from typus.models.tracks import Detection
from typus import BBoxXYWHNorm

# Preferred: Use canonical bbox
detection = Detection(
    frame_number=100,
    bbox_norm=BBoxXYWHNorm(x=0.1, y=0.2, w=0.5, h=0.6),
    confidence=0.95
)

# Legacy support (deprecated)
detection_legacy = Detection(
    frame_number=100, 
    bbox=[10, 20, 50, 60],  # Pixel coordinates - DEPRECATED
    confidence=0.95
)
```

### Converting Raw Detection Data

Use the factory method to convert from provider-specific formats:

```python
# Raw detection from Gemini API
raw_detection = {
    "frame_number": 100,
    "bbox": [50, 50, 80, 90],  # Gemini bottom-right coordinates
    "confidence": 0.95
}

# Convert to canonical format
detection = Detection.from_raw_detection(
    raw_detection,
    upload_w=100, upload_h=100,
    provider="gemini_br_xyxy"
)

# Now has both canonical and legacy fields
assert detection.bbox_norm is not None  # Canonical format
assert detection.bbox == [50, 50, 80, 90]  # Legacy preserved
```

## Migration Guide

### From Pixel to Canonical

If you have existing code using pixel bboxes:

```python
# Before (v0.2.x)
bbox_pixels = [10, 20, 50, 60]  # x, y, width, height in pixels

# After (v0.3.0+) 
from typus import BBoxXYWHNorm
image_width, image_height = 100, 100
bbox_canonical = BBoxXYWHNorm(
    x=10/image_width,    # 0.1
    y=20/image_height,   # 0.2  
    w=50/image_width,    # 0.5
    h=60/image_height    # 0.6
)
```

### From Multiple Formats to Canonical

Replace ad-hoc format handling:

```python
# Before: Multiple format support
def handle_bbox(bbox, format_hint):
    if format_hint == "xyxy":
        # Handle xyxy
    elif format_hint == "xywh":
        # Handle xywh
    # ... more formats

# After: Single canonical format
def handle_bbox(bbox: BBoxXYWHNorm):
    # Always canonical TL-normalized xywh
    # No format ambiguity
```

## Best Practices

1. **Always use canonical format** for new code
2. **Convert at API boundaries** using provider mappers  
3. **Store in canonical format** to avoid coordinate system bugs
4. **Use factory methods** like `Detection.from_raw_detection()` for conversion
5. **Validate early** - canonical types enforce invariants at construction time

## JSON Schema

The canonical geometry types provide JSON schemas for API documentation and validation:

```python
from typus import BBoxXYWHNorm

schema = BBoxXYWHNorm.model_json_schema()
# Use schema for OpenAPI docs, request validation, etc.
```

Generated schemas are available in `typus/schemas/` directory:
- `BBoxXYWHNorm.json`
- `Detection.json` 
- `Track.json`