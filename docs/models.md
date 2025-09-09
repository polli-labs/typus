# Typus Models

This document describes the Pydantic models used in Typus for representing various data structures.

## Classification Models

Refer to existing documentation or source code for `HierarchicalClassificationResult` and `TaxonomyContext`.
*(Assumption: These are documented elsewhere or users should refer to code. If this file were being extended, this section would already exist.)*

## Geometry Models

### **Canonical Geometry (v0.3.0+)**

**For new code, always use the canonical `BBoxXYWHNorm` type.** See the [Canonical Geometry](geometry.md) documentation for full details.

#### `BBoxXYWHNorm` (Recommended)

The canonical bounding box format with enforced invariants:

- **Format**: `[x, y, width, height]` (top-left origin)
- **Normalization**: All values in `[0, 1]` range
- **Immutable**: Cannot be modified after creation
- **Validated**: Enforces coordinate bounds and non-finite rejection

**Example:**

```python
from typus import BBoxXYWHNorm

# Canonical bbox covering 20%-70% horizontally, 10%-60% vertically
bbox = BBoxXYWHNorm(x=0.2, y=0.1, w=0.5, h=0.5)

# Convert to/from pixel coordinates
from typus import to_xyxy_px, from_xyxy_px

# To pixels (for 1920x1080 image)
x1, y1, x2, y2 = to_xyxy_px(bbox, W=1920, H=1080)
# Result: (384, 108, 1344, 648)

# From pixels
bbox_from_pixels = from_xyxy_px(384, 108, 1344, 648, W=1920, H=1080)
```

### Legacy Geometry Types

*The following types are maintained for backward compatibility but should not be used in new code.*

#### `BBoxFormat` (Enum) - Legacy

Defines the format of a legacy bounding box's coordinates.

*   `XYXY_REL`: Relative coordinates representing [x_min, y_min, x_max, y_max], where values are fractions of image width/height.
*   `XYXY_ABS`: Absolute pixel coordinates representing [x_min, y_min, x_max, y_max].
*   `CXCYWH_REL`: Relative coordinates representing [center_x, center_y, width, height], where values are fractions of image width/height.
*   `CXCYWH_ABS`: Absolute pixel coordinates representing [center_x, center_y, width, height].

#### `MaskEncoding` (Enum)

Defines the encoding method for an instance mask.

*   `RLE_COCO`: Run-Length Encoding in COCO format. The `data` field in `EncodedMask` will be a string (or COCO RLE dict if pre-formatted).
*   `POLYGON`: Polygon representation as a list of [x,y] points. The `data` field in `EncodedMask` will be a `List[List[float]]`.
*   `PNG_BASE64`: Base64 encoded PNG image representing the mask. The `data` field in `EncodedMask` will be a string.

#### `BBox` - Legacy

*Legacy bounding box with multiple format support. Use `BBoxXYWHNorm` for new code.*

*   `coords: Tuple[float, float, float, float]`: The coordinates of the bounding box.
*   `fmt: BBoxFormat = BBoxFormat.XYXY_REL`: The format of the coordinates. Defaults to relative XYXY.

### `EncodedMask`

Represents an encoded instance mask.

*   `data: str | List[List[float]]`: The mask data, format depends on `encoding`.
*   `encoding: MaskEncoding`: The encoding method used for the mask.
*   `bbox_hint: BBox | None = None`: An optional bounding box associated with the mask, which can be useful as a hint for processing.

**Example:**

```python
from typus.models.geometry import EncodedMask, MaskEncoding, BBox

# Polygon mask (list of [x,y] points)
polygon_mask = EncodedMask(
    data=[[10.0, 10.0], [50.0, 10.0], [50.0, 50.0], [10.0, 50.0]],
    encoding=MaskEncoding.POLYGON
)

# RLE mask (data is a string, details depend on COCO RLE specifics)
rle_mask = EncodedMask(
    data="someRLEString...",
    encoding=MaskEncoding.RLE_COCO,
    bbox_hint=BBox(coords=(10,10,50,50), fmt=BBoxFormat.XYXY_ABS)
)
```

## Detection Models

These models are used to represent the output of object detection and instance segmentation systems.

### `InstancePrediction`

Represents a single detected instance within an image.

*   `instance_id: int`: A unique identifier for the instance within the image (non-negative).
*   `bbox: BBox`: The bounding box of the detected instance.
*   `mask: EncodedMask | None = None`: The instance mask (optional).
*   `score: float`: The confidence score of the detection (between 0 and 1).
*   `taxon_id: int | None = None`: Optional taxonomic identifier for the instance.
*   `classification: HierarchicalClassificationResult | None = None`: Optional hierarchical classification result for the instance.

**Example:**

```python
from typus.models.geometry import BBox, BBoxFormat
from typus.models.detection import InstancePrediction

instance = InstancePrediction(
    instance_id=1,
    bbox=BBox(coords=(0.2, 0.3, 0.6, 0.7), fmt=BBoxFormat.XYXY_REL),
    score=0.92,
    taxon_id=1001
)
```

### `ImageDetectionResult`

Represents the complete set of detections for a single image.

*   `width: int`: The width of the image in pixels.
*   `height: int`: The height of the image in pixels.
*   `instances: List[InstancePrediction]`: A list of all detected instances in the image.
*   `taxonomy_context: TaxonomyContext | None = None`: Optional context about the taxonomy used for classifications.

**Example:**

```python
from typus.models.detection import ImageDetectionResult, InstancePrediction
from typus.models.geometry import BBox

img_result = ImageDetectionResult(
    width=1920,
    height=1080,
    instances=[
        InstancePrediction(
            instance_id=1,
            bbox=BBox(coords=(0.1, 0.1, 0.3, 0.3)),
            score=0.95,
            taxon_id=101
        ),
        InstancePrediction(
            instance_id=2,
            bbox=BBox(coords=(0.4, 0.4, 0.6, 0.6)),
            score=0.88,
            taxon_id=102
        )
    ]
)

# Serializing to JSON (uses CompactJsonMixin for camelCase and no Nones)
json_output = img_result.to_json(indent=2)
print(json_output)
```

## Helper Utilities (`typus.models.detection.utils`)

### `to_coco()`

Converts an `ImageDetectionResult` object into a COCO-style dictionary (primarily the "annotations" part).

*   `image: ImageDetectionResult`: The detection result to convert.
*   `category_map: dict[int, int]`: A mapping from Typus `taxon_id` to COCO `category_id`.

**Example:**
```python
from typus.models.detection import ImageDetectionResult, InstancePrediction
from typus.models.geometry import BBox
from typus.models.detection.utils import to_coco

# (Assuming ImageDetectionResult 'img_result' is defined as above)
category_map = {101: 1, 102: 2} # typus taxon_id -> coco category_id
coco_annotations = to_coco(img_result, category_map)
# coco_annotations will be a dict like:
# {
#   "annotations": [
#     { "image_id": 0, "category_id": 1, "bbox": [...], "score": 0.95, "id": 1 },
#     { "image_id": 0, "category_id": 2, "bbox": [...], "score": 0.88, "id": 2 }
#   ]
# }
```

### `from_coco()`

Converts a COCO-style JSON dictionary into a list of `ImageDetectionResult` objects.

*   `coco: dict`: The COCO JSON data (can contain information for multiple images).

**Example:**
```python
from typus.models.detection.utils import from_coco

coco_json_data = {
    "images": [
        {"id": 1, "width": 1920, "height": 1080}
    ],
    "annotations": [
        {"image_id": 1, "id": 1, "category_id": 1, "bbox": [192, 108, 384, 216], "score": 0.95} # xywh_abs
    ],
    "categories": [{"id": 1, "name": "object"}]
}

typus_results = from_coco(coco_json_data)
if typus_results:
    img_result_from_coco = typus_results[0]
    print(f"Image dimensions: {img_result_from_coco.width}x{img_result_from_coco.height}")
    for instance in img_result_from_coco.instances:
        print(f"Instance {instance.instance_id}, BBox: {instance.bbox.coords}, Score: {instance.score}")
```

This provides a basic structure. Diagrams would need to be created separately and embedded if this were a full Markdown rendering environment.

## ExpandedTaxa ORM columns

| Column | Description |
|-------|-------------|
| `taxonID` | primary key |
| `rankLevel` | numeric rank value |
| `rank` | canonical rank name |
| `name` | scientific name |
| `taxonActive` | boolean active flag |
| `commonName` | english common name |
| `immediateAncestor_taxonID` | direct parent taxon ID |
| `immediateAncestor_rankLevel` | rank level of the parent |
| `immediateMajorAncestor_taxonID` | nearest major ancestor ID |
| `immediateMajorAncestor_rankLevel` | rank level of that ancestor |

*Legacy `trueParentID`, `majorParentID`, `path` and `ancestry` columns were removed in v0.1.9.*
