# Track Models Documentation

## Overview

The `typus.models.tracks` module provides standardized data models for representing object tracks in video analysis. These models are designed to support the complete lifecycle of tracking data, from raw detections through smoothing, enrichment with taxonomic information, and human validation.

## Core Models

### Detection

Represents a single detection of an object at a specific frame in a video.

```python
from typus import Detection

detection = Detection(
    frame_number=100,
    bbox=[10.5, 20.5, 50.0, 60.0],  # [x, y, width, height]
    confidence=0.95,
    taxon_id=47219,  # Optional
    scientific_name="Apis mellifera",  # Optional
    common_name="Western honey bee"  # Optional
)
```

**Key Features:**
- Bounding box validation (must be exactly 4 elements)
- Confidence score validation (0.0 to 1.0)
- Optional taxonomy fields for post-detection enrichment
- Optional smoothed bbox and velocity for processed data

### TrackStats

Provides statistical summaries of track metrics for quality assessment.

```python
from typus import TrackStats

stats = TrackStats(
    confidence_mean=0.92,
    confidence_std=0.05,
    confidence_min=0.85,
    confidence_max=0.98,
    bbox_stability=0.88  # Optional measure of bbox consistency
)
```

### Track

Complete track representing an object's journey through a video, consisting of multiple linked detections.

```python
from typus import Track, Detection

track = Track(
    track_id="track_001",
    clip_id="video_20240108",
    detections=[detection1, detection2, detection3],
    start_frame=100,
    end_frame=150,
    duration_frames=51,
    duration_seconds=1.7,
    confidence=0.92,
    # Optional fields
    taxon_id=47219,
    scientific_name="Apis mellifera",
    common_name="Western honey bee",
    validation_status="validated",
    detector="yolov8",
    tracker="bytetrack"
)
```

## Creating Tracks from Raw Data

The `Track.from_raw_detections()` class method provides a convenient way to create tracks from raw detection dictionaries:

```python
raw_detections = [
    {"frame_number": 100, "bbox": [10, 20, 50, 60], "confidence": 0.90},
    {"frame_number": 101, "bbox": [11, 21, 50, 60], "confidence": 0.92},
    {"frame_number": 102, "bbox": [12, 22, 50, 60], "confidence": 0.95},
]

track = Track.from_raw_detections(
    track_id="track_002",
    clip_id="video_20240109",
    detections=raw_detections,
    fps=30.0,  # For duration calculation
    detector="yolov8"
)
```

This method automatically:
- Converts raw dictionaries to Detection objects
- Calculates frame ranges and duration
- Computes confidence statistics
- Creates a TrackStats object

## Track Methods

### Query Detections

```python
# Get detection at specific frame
detection = track.get_detection_at_frame(101)

# Get all frame numbers (sorted)
frame_numbers = track.get_frame_numbers()  # [100, 101, 102]
```

### Check Track Quality

```python
# Check if track is continuous (no gaps)
is_continuous = track.is_continuous(max_gap=1)  # True if no gaps > 1 frame
```

## Validation Workflow

Tracks support a complete validation workflow for human review:

```python
from datetime import datetime

track.validation_status = "validated"
track.validation_notes = "Clear bee identification, high confidence"
track.validated_by = "user123"
track.validated_at = datetime.now()
```

Validation statuses:
- `"pending"` - Awaiting review (default)
- `"validated"` - Confirmed by human reviewer
- `"rejected"` - Marked as incorrect/invalid

## Processing Metadata

Track metadata for reproducibility and debugging:

```python
track = Track(
    # ... core fields ...
    detector="yolov8",           # Detection model used
    tracker="bytetrack",         # Tracking algorithm
    smoothing_applied=True,      # Whether smoothing was applied
    smoothing_method="kalman"    # Smoothing algorithm used
)
```

## Serialization

All models support JSON serialization for API responses and storage:

```python
# Serialize to JSON
json_str = track.model_dump_json()

# Deserialize from JSON
track = Track.model_validate_json(json_str)

# Convert to dictionary
track_dict = track.model_dump()
```

## Integration with Taxonomy Service

Tracks can be enriched with taxonomic information from typus taxonomy services:

```python
from typus import PostgresTaxonomyService

# Get taxonomy service
taxonomy = PostgresTaxonomyService(dsn)

# Enrich track with taxonomy
if track.taxon_id:
    taxon = await taxonomy.get_taxon(track.taxon_id)
    track.scientific_name = taxon.scientific_name
    track.common_name = taxon.vernacular.get("en", [None])[0]
```

## Backward Compatibility

The Track models are designed to be backward compatible with existing data formats from the distillation pipeline. Legacy data can be loaded directly:

```python
legacy_data = {
    "track_id": "legacy_001",
    "clip_id": "video_legacy",
    "detections": [...],
    "start_frame": 50,
    "end_frame": 100,
    "duration_frames": 51,
    "duration_seconds": 1.7,
    "confidence": 0.85
}

track = Track(**legacy_data)
# Optional fields will use defaults (validation_status="pending", etc.)
```

## API Response Format

Standard format for API responses:

```python
response = {
    "tracks": [track1.model_dump(), track2.model_dump()],
    "metadata": {
        "clip_id": "video_20240108",
        "total_tracks": 2,
        "processing_time": 1.23
    }
}
```

## Performance Considerations

- **Detections List**: For tracks with many detections (>1000), consider pagination or summarization
- **Validation**: Pydantic validation ensures data integrity but has a small performance cost
- **Serialization**: Use `model_dump()` with `exclude_none=True` to reduce payload size

## Migration from Legacy Formats

For existing artifacts using different formats, use adapters:

```python
def adapt_legacy_track(legacy_data):
    """Convert legacy format to Track model."""
    detections = [
        Detection(
            frame_number=d["frame"],
            bbox=d["box"],
            confidence=d.get("conf", 0.5)
        )
        for d in legacy_data["dets"]
    ]
    
    return Track.from_raw_detections(
        track_id=legacy_data["id"],
        clip_id=legacy_data["video"],
        detections=[d.model_dump() for d in detections],
        fps=legacy_data.get("fps", 30.0)
    )
```

## Best Practices

1. **Always validate input data** - Use the models to ensure data consistency
2. **Include processing metadata** - Record detector/tracker for reproducibility
3. **Use taxonomy IDs** - Store taxon_id for reliable taxonomy lookups
4. **Track validation status** - Maintain audit trail for human review
5. **Handle missing frames** - Use `is_continuous()` to detect gaps
6. **Compute statistics** - Use TrackStats for quality metrics

## Example: Complete Workflow

```python
from typus import Track, Detection, PostgresTaxonomyService
from datetime import datetime

# 1. Create track from detections
track = Track.from_raw_detections(
    track_id="bee_track_001",
    clip_id="hive_entrance_20240108",
    detections=raw_detections,
    fps=30.0,
    detector="yolov8",
    tracker="bytetrack"
)

# 2. Apply smoothing (in processing pipeline)
track.smoothing_applied = True
track.smoothing_method = "kalman"

# 3. Enrich with taxonomy
taxonomy = PostgresTaxonomyService(dsn)
taxon = await taxonomy.get_taxon(47219)
track.taxon_id = taxon.taxon_id
track.scientific_name = taxon.scientific_name

# 4. Human validation
track.validation_status = "validated"
track.validated_by = "bee_expert_user"
track.validated_at = datetime.now()

# 5. Serialize for API response
response_data = track.model_dump(exclude_none=True)
```