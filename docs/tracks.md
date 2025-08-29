# Track Models Documentation

## Overview

The `typus.models.tracks` module provides standardized data models for representing object tracks in video analysis. These models are designed to support the complete lifecycle of tracking data, from raw detections through smoothing, enrichment with taxonomic information, and human validation.

**As of v0.3.0**, track models use [canonical geometry](geometry.md) for all bounding box coordinates, ensuring consistent coordinate systems across all Polli-Labs repositories.

## Core Models

### Detection

Represents a single detection of an object at a specific frame in a video.

```python
from typus.models.tracks import Detection
from typus import BBoxXYWHNorm

# Preferred: Use canonical normalized bbox
detection = Detection(
    frame_number=100,
    bbox_norm=BBoxXYWHNorm(x=0.1, y=0.2, w=0.5, h=0.6),  # Canonical format
    confidence=0.95,
    taxon_id=47219,  # Optional
    scientific_name="Apis mellifera",  # Optional
    common_name="Western honey bee"  # Optional
)

# Legacy support (deprecated)
detection_legacy = Detection(
    frame_number=100,
    bbox=[10.5, 20.5, 50.0, 60.0],  # Pixel coordinates - DEPRECATED
    confidence=0.95
)
```

**Key Features:**
- **Canonical bbox support** - Use `bbox_norm` with `BBoxXYWHNorm` type
- **Legacy compatibility** - Still accepts pixel `bbox` field (deprecated) 
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
# Using canonical normalized bboxes
raw_detections = [
    {
        "frame_number": 100, 
        "bbox_norm": {"x": 0.1, "y": 0.2, "w": 0.5, "h": 0.6}, 
        "confidence": 0.90
    },
    {
        "frame_number": 101, 
        "bbox_norm": {"x": 0.11, "y": 0.21, "w": 0.5, "h": 0.6}, 
        "confidence": 0.92
    },
    {
        "frame_number": 102, 
        "bbox_norm": {"x": 0.12, "y": 0.22, "w": 0.5, "h": 0.6}, 
        "confidence": 0.95
    },
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

### Converting from Provider-Specific Formats

When working with different vision APIs (like Gemini), use the factory method with provider mapping:

```python  
from typus.models.tracks import Detection

# Raw detection from Gemini API (bottom-right origin)
gemini_detection = {
    "frame_number": 100,
    "bbox": [50, 50, 80, 90],  # Gemini BR coordinates
    "confidence": 0.95
}

# Convert to canonical format
detection = Detection.from_raw_detection(
    gemini_detection,
    upload_w=100, upload_h=100,
    provider="gemini_br_xyxy"  # Converts BR->TL and normalizes
)

# Now has canonical bbox_norm and preserves original bbox
assert detection.bbox_norm is not None  # Canonical format
assert detection.bbox == [50, 50, 80, 90]  # Original preserved
```

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

### Convenience Properties and Methods

```python
# Duration property (alias for duration_seconds)
duration = track.duration  # Same as track.duration_seconds

# Convert frame number to time relative to track start
time_at_frame = track.frame_to_time(101, fps=30.0)  # Returns seconds from track start
```

## Merging Tracks

The `merge_tracks()` class method allows you to reconnect tracks that were incorrectly split by the tracking algorithm:

```python
# Merge multiple tracks into one
merged_track = Track.merge_tracks(
    tracks=[track1, track2, track3],
    new_track_id="merged_001",
    gap_threshold=10  # Maximum allowed gap between tracks (default: 10 frames)
)
```

Key features of track merging:
- **Validation**: Ensures tracks are from the same clip and don't overlap
- **Gap handling**: Configurable threshold for acceptable gaps between tracks
- **Taxonomy consensus**: Uses the most common taxon_id across all detections
- **Metadata preservation**: Maintains processing metadata from source tracks
- **Statistics recomputation**: Recalculates confidence stats for the merged track

Example with error handling:

```python
try:
    merged = Track.merge_tracks([track1, track2], "merged_001", gap_threshold=5)
except ValueError as e:
    if "exceeds threshold" in str(e):
        # Gap between tracks is too large
        print(f"Tracks have too large a gap: {e}")
    elif "overlap" in str(e):
        # Tracks overlap in time
        print(f"Tracks overlap: {e}")
    elif "different clips" in str(e):
        # Tracks are from different video clips
        print(f"Cannot merge tracks from different clips: {e}")
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