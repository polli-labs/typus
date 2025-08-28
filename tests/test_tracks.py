"""Tests for Track models."""

import json
from datetime import datetime

import pytest
from pydantic import ValidationError

from typus.models.tracks import Detection, Track, TrackStats


class TestDetection:
    """Tests for Detection model."""

    def test_detection_basic(self):
        """Test basic Detection creation."""
        det = Detection(frame_number=100, bbox=[10.5, 20.5, 50.0, 60.0], confidence=0.95)
        assert det.frame_number == 100
        assert det.bbox == [10.5, 20.5, 50.0, 60.0]
        assert det.confidence == 0.95
        assert det.taxon_id is None
        assert det.scientific_name is None

    def test_detection_with_taxonomy(self):
        """Test Detection with taxonomy information."""
        det = Detection(
            frame_number=100,
            bbox=[10, 20, 50, 60],
            confidence=0.95,
            taxon_id=47219,
            scientific_name="Apis mellifera",
            common_name="Western honey bee",
        )
        assert det.taxon_id == 47219
        assert det.scientific_name == "Apis mellifera"
        assert det.common_name == "Western honey bee"

    def test_detection_with_smoothing(self):
        """Test Detection with smoothed values."""
        det = Detection(
            frame_number=100,
            bbox=[10, 20, 50, 60],
            confidence=0.95,
            smoothed_bbox=[11, 21, 49, 59],
            velocity=[2.5, -1.0],
        )
        assert det.smoothed_bbox == [11, 21, 49, 59]
        assert det.velocity == [2.5, -1.0]

    def test_detection_validation_errors(self):
        """Test Detection validation errors."""
        # Invalid confidence (> 1.0)
        with pytest.raises(ValidationError) as exc_info:
            Detection(frame_number=100, bbox=[10, 20, 50, 60], confidence=1.5)
        assert "less than or equal to 1" in str(exc_info.value)

        # Invalid bbox (wrong length)
        with pytest.raises(ValidationError) as exc_info:
            Detection(
                frame_number=100,
                bbox=[10, 20, 50],  # Only 3 elements
                confidence=0.95,
            )
        assert "at least 4 items" in str(exc_info.value)

        # Negative frame number
        with pytest.raises(ValidationError) as exc_info:
            Detection(frame_number=-1, bbox=[10, 20, 50, 60], confidence=0.95)
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_detection_json_serialization(self):
        """Test Detection JSON serialization."""
        det = Detection(
            frame_number=100, bbox=[10.5, 20.5, 50.0, 60.0], confidence=0.95, taxon_id=47219
        )
        json_str = det.model_dump_json()
        data = json.loads(json_str)
        assert data["frame_number"] == 100
        assert data["bbox"] == [10.5, 20.5, 50.0, 60.0]
        assert data["confidence"] == 0.95
        assert data["taxon_id"] == 47219

        # Deserialize back
        det2 = Detection.model_validate_json(json_str)
        assert det2 == det


class TestTrackStats:
    """Tests for TrackStats model."""

    def test_track_stats_basic(self):
        """Test basic TrackStats creation."""
        stats = TrackStats(
            confidence_mean=0.92, confidence_std=0.05, confidence_min=0.85, confidence_max=0.98
        )
        assert stats.confidence_mean == 0.92
        assert stats.confidence_std == 0.05
        assert stats.confidence_min == 0.85
        assert stats.confidence_max == 0.98
        assert stats.bbox_stability is None

    def test_track_stats_with_stability(self):
        """Test TrackStats with bbox stability."""
        stats = TrackStats(
            confidence_mean=0.92,
            confidence_std=0.05,
            confidence_min=0.85,
            confidence_max=0.98,
            bbox_stability=0.88,
        )
        assert stats.bbox_stability == 0.88

    def test_track_stats_validation_errors(self):
        """Test TrackStats validation errors."""
        # Invalid confidence values
        with pytest.raises(ValidationError):
            TrackStats(
                confidence_mean=1.5,  # > 1.0
                confidence_std=0.05,
                confidence_min=0.85,
                confidence_max=0.98,
            )

        # Negative std deviation
        with pytest.raises(ValidationError):
            TrackStats(
                confidence_mean=0.92,
                confidence_std=-0.05,  # Negative
                confidence_min=0.85,
                confidence_max=0.98,
            )


class TestTrack:
    """Tests for Track model."""

    @pytest.fixture
    def sample_detections(self):
        """Create sample detections for testing."""
        return [
            Detection(frame_number=100, bbox=[10, 20, 50, 60], confidence=0.90),
            Detection(frame_number=101, bbox=[11, 21, 50, 60], confidence=0.92),
            Detection(frame_number=102, bbox=[12, 22, 50, 60], confidence=0.95),
        ]

    @pytest.fixture
    def sample_stats(self):
        """Create sample stats for testing."""
        return TrackStats(
            confidence_mean=0.92, confidence_std=0.025, confidence_min=0.90, confidence_max=0.95
        )

    def test_track_basic(self, sample_detections, sample_stats):
        """Test basic Track creation."""
        track = Track(
            track_id="track_001",
            clip_id="video_20240108",
            detections=sample_detections,
            start_frame=100,
            end_frame=102,
            duration_frames=3,
            duration_seconds=0.1,
            confidence=0.92,
            stats=sample_stats,
        )
        assert track.track_id == "track_001"
        assert track.clip_id == "video_20240108"
        assert len(track.detections) == 3
        assert track.start_frame == 100
        assert track.end_frame == 102
        assert track.duration_frames == 3
        assert track.confidence == 0.92

    def test_track_with_taxonomy(self, sample_detections):
        """Test Track with taxonomy information."""
        track = Track(
            track_id="track_001",
            clip_id="video_20240108",
            detections=sample_detections,
            start_frame=100,
            end_frame=102,
            duration_frames=3,
            duration_seconds=0.1,
            confidence=0.92,
            taxon_id=47219,
            scientific_name="Apis mellifera",
            common_name="Western honey bee",
        )
        assert track.taxon_id == 47219
        assert track.scientific_name == "Apis mellifera"
        assert track.common_name == "Western honey bee"

    def test_track_with_validation(self, sample_detections):
        """Test Track with validation metadata."""
        validated_at = datetime.now()
        track = Track(
            track_id="track_001",
            clip_id="video_20240108",
            detections=sample_detections,
            start_frame=100,
            end_frame=102,
            duration_frames=3,
            duration_seconds=0.1,
            confidence=0.92,
            validation_status="validated",
            validation_notes="Clear bee identification",
            validated_by="user123",
            validated_at=validated_at,
        )
        assert track.validation_status == "validated"
        assert track.validation_notes == "Clear bee identification"
        assert track.validated_by == "user123"
        assert track.validated_at == validated_at

    def test_track_with_processing_metadata(self, sample_detections):
        """Test Track with processing metadata."""
        track = Track(
            track_id="track_001",
            clip_id="video_20240108",
            detections=sample_detections,
            start_frame=100,
            end_frame=102,
            duration_frames=3,
            duration_seconds=0.1,
            confidence=0.92,
            detector="yolov8",
            tracker="bytetrack",
            smoothing_applied=True,
            smoothing_method="kalman",
        )
        assert track.detector == "yolov8"
        assert track.tracker == "bytetrack"
        assert track.smoothing_applied is True
        assert track.smoothing_method == "kalman"

    def test_track_post_init_corrections(self):
        """Test that post_init corrects frame ranges."""
        detections = [
            Detection(frame_number=105, bbox=[10, 20, 50, 60], confidence=0.90),
            Detection(frame_number=110, bbox=[11, 21, 50, 60], confidence=0.92),
            Detection(frame_number=115, bbox=[12, 22, 50, 60], confidence=0.95),
        ]

        # Create track with incorrect frame ranges
        track = Track(
            track_id="track_001",
            clip_id="video_20240108",
            detections=detections,
            start_frame=100,  # Wrong
            end_frame=120,  # Wrong
            duration_frames=21,  # Wrong
            duration_seconds=0.7,
            confidence=0.92,
        )

        # post_init should correct these
        assert track.start_frame == 105
        assert track.end_frame == 115
        assert track.duration_frames == 11

    def test_track_from_raw_detections(self):
        """Test creating Track from raw detection dictionaries."""
        raw_detections = [
            {"frame_number": 100, "bbox": [10, 20, 50, 60], "confidence": 0.90},
            {"frame_number": 101, "bbox": [11, 21, 50, 60], "confidence": 0.92},
            {"frame_number": 102, "bbox": [12, 22, 50, 60], "confidence": 0.95},
            {"frame_number": 103, "bbox": [13, 23, 50, 60], "confidence": 0.93},
        ]

        track = Track.from_raw_detections(
            track_id="track_002",
            clip_id="video_20240109",
            detections=raw_detections,
            fps=30.0,
            detector="yolov8",
        )

        assert track.track_id == "track_002"
        assert track.clip_id == "video_20240109"
        assert len(track.detections) == 4
        assert track.start_frame == 100
        assert track.end_frame == 103
        assert track.duration_frames == 4
        assert track.duration_seconds == pytest.approx(4 / 30.0)
        assert track.detector == "yolov8"
        assert track.stats is not None
        assert track.stats.confidence_mean == pytest.approx(0.925)
        assert track.confidence == pytest.approx(0.925)

    def test_get_detection_at_frame(self, sample_detections):
        """Test getting detection at specific frame."""
        track = Track(
            track_id="track_001",
            clip_id="video_20240108",
            detections=sample_detections,
            start_frame=100,
            end_frame=102,
            duration_frames=3,
            duration_seconds=0.1,
            confidence=0.92,
        )

        det = track.get_detection_at_frame(101)
        assert det is not None
        assert det.frame_number == 101
        assert det.confidence == 0.92

        # Non-existent frame
        det = track.get_detection_at_frame(105)
        assert det is None

    def test_get_frame_numbers(self):
        """Test getting sorted frame numbers."""
        # Create detections out of order
        detections = [
            Detection(frame_number=105, bbox=[10, 20, 50, 60], confidence=0.90),
            Detection(frame_number=100, bbox=[11, 21, 50, 60], confidence=0.92),
            Detection(frame_number=110, bbox=[12, 22, 50, 60], confidence=0.95),
        ]

        track = Track(
            track_id="track_001",
            clip_id="video_20240108",
            detections=detections,
            start_frame=100,
            end_frame=110,
            duration_frames=11,
            duration_seconds=0.37,
            confidence=0.92,
        )

        frame_numbers = track.get_frame_numbers()
        assert frame_numbers == [100, 105, 110]

    def test_is_continuous(self):
        """Test checking track continuity."""
        # Continuous track (no gaps)
        detections = [
            Detection(frame_number=100, bbox=[10, 20, 50, 60], confidence=0.90),
            Detection(frame_number=101, bbox=[11, 21, 50, 60], confidence=0.92),
            Detection(frame_number=102, bbox=[12, 22, 50, 60], confidence=0.95),
        ]
        track = Track(
            track_id="track_001",
            clip_id="video_20240108",
            detections=detections,
            start_frame=100,
            end_frame=102,
            duration_frames=3,
            duration_seconds=0.1,
            confidence=0.92,
        )
        assert track.is_continuous(max_gap=0) is True
        assert track.is_continuous(max_gap=1) is True

        # Track with small gap
        detections = [
            Detection(frame_number=100, bbox=[10, 20, 50, 60], confidence=0.90),
            Detection(frame_number=102, bbox=[11, 21, 50, 60], confidence=0.92),  # Gap of 1
            Detection(frame_number=103, bbox=[12, 22, 50, 60], confidence=0.95),
        ]
        track = Track(
            track_id="track_002",
            clip_id="video_20240108",
            detections=detections,
            start_frame=100,
            end_frame=103,
            duration_frames=4,
            duration_seconds=0.13,
            confidence=0.92,
        )
        assert track.is_continuous(max_gap=0) is False
        assert track.is_continuous(max_gap=1) is True

        # Track with large gap
        detections = [
            Detection(frame_number=100, bbox=[10, 20, 50, 60], confidence=0.90),
            Detection(frame_number=110, bbox=[11, 21, 50, 60], confidence=0.92),  # Gap of 9
        ]
        track = Track(
            track_id="track_003",
            clip_id="video_20240108",
            detections=detections,
            start_frame=100,
            end_frame=110,
            duration_frames=11,
            duration_seconds=0.37,
            confidence=0.91,
        )
        assert track.is_continuous(max_gap=5) is False
        assert track.is_continuous(max_gap=10) is True

    def test_track_validation_errors(self):
        """Test Track validation errors."""
        # Empty detections list
        with pytest.raises(ValidationError) as exc_info:
            Track(
                track_id="track_001",
                clip_id="video_20240108",
                detections=[],  # Empty
                start_frame=100,
                end_frame=102,
                duration_frames=3,
                duration_seconds=0.1,
                confidence=0.92,
            )
        assert "at least 1 item" in str(exc_info.value)

        # Invalid validation status
        with pytest.raises(ValidationError):
            Track(
                track_id="track_001",
                clip_id="video_20240108",
                detections=[Detection(frame_number=100, bbox=[10, 20, 50, 60], confidence=0.90)],
                start_frame=100,
                end_frame=100,
                duration_frames=1,
                duration_seconds=0.03,
                confidence=0.90,
                validation_status="invalid_status",  # Not in allowed values
            )

    def test_track_json_serialization(self, sample_detections):
        """Test Track JSON serialization."""
        track = Track(
            track_id="track_001",
            clip_id="video_20240108",
            detections=sample_detections,
            start_frame=100,
            end_frame=102,
            duration_frames=3,
            duration_seconds=0.1,
            confidence=0.92,
            taxon_id=47219,
            detector="yolov8",
        )

        json_str = track.model_dump_json()
        data = json.loads(json_str)

        assert data["track_id"] == "track_001"
        assert data["clip_id"] == "video_20240108"
        assert len(data["detections"]) == 3
        assert data["taxon_id"] == 47219
        assert data["detector"] == "yolov8"

        # Deserialize back
        track2 = Track.model_validate_json(json_str)
        assert track2.track_id == track.track_id
        assert len(track2.detections) == len(track.detections)

    def test_backward_compatibility(self):
        """Test that Track can handle legacy data formats."""
        # Simulate legacy format from distillation pipeline
        legacy_data = {
            "track_id": "legacy_001",
            "clip_id": "video_legacy",
            "detections": [{"frame_number": 50, "bbox": [100, 200, 50, 60], "confidence": 0.85}],
            "start_frame": 50,
            "end_frame": 50,
            "duration_frames": 1,
            "duration_seconds": 0.033,
            "confidence": 0.85,
        }

        # Should be able to create Track from legacy data
        track = Track(**legacy_data)
        assert track.track_id == "legacy_001"
        assert track.validation_status == "pending"  # Default value
        assert track.smoothing_applied is False  # Default value

    def test_duration_property(self, sample_detections):
        """Test the duration property alias."""
        track = Track(
            track_id="track_001",
            clip_id="video_20240108",
            detections=sample_detections,
            start_frame=100,
            end_frame=102,
            duration_frames=3,
            duration_seconds=0.1,
            confidence=0.92,
        )
        assert track.duration == 0.1
        assert track.duration == track.duration_seconds

    def test_frame_to_time(self, sample_detections):
        """Test frame to time conversion."""
        track = Track(
            track_id="track_001",
            clip_id="video_20240108",
            detections=sample_detections,
            start_frame=100,
            end_frame=102,
            duration_frames=3,
            duration_seconds=0.1,
            confidence=0.92,
        )

        # Test conversion at different frames
        assert track.frame_to_time(100, fps=30) == 0.0  # Start frame
        assert track.frame_to_time(101, fps=30) == pytest.approx(1 / 30)
        assert track.frame_to_time(102, fps=30) == pytest.approx(2 / 30)

        # Test with different fps
        assert track.frame_to_time(102, fps=60) == pytest.approx(2 / 60)

        # Test outside range
        with pytest.raises(ValueError) as exc_info:
            track.frame_to_time(99, fps=30)
        assert "outside track range" in str(exc_info.value)

        with pytest.raises(ValueError):
            track.frame_to_time(103, fps=30)

    def test_merge_tracks_basic(self):
        """Test basic track merging."""
        # Create two sequential tracks
        track1 = Track(
            track_id="track_001",
            clip_id="video_20240108",
            detections=[
                Detection(frame_number=100, bbox=[10, 20, 50, 60], confidence=0.90),
                Detection(frame_number=101, bbox=[11, 21, 50, 60], confidence=0.92),
            ],
            start_frame=100,
            end_frame=101,
            duration_frames=2,
            duration_seconds=0.067,
            confidence=0.91,
            taxon_id=47219,
            scientific_name="Apis mellifera",
        )

        track2 = Track(
            track_id="track_002",
            clip_id="video_20240108",
            detections=[
                Detection(frame_number=103, bbox=[13, 23, 50, 60], confidence=0.93),
                Detection(frame_number=104, bbox=[14, 24, 50, 60], confidence=0.94),
            ],
            start_frame=103,
            end_frame=104,
            duration_frames=2,
            duration_seconds=0.067,
            confidence=0.935,
            taxon_id=47219,
            scientific_name="Apis mellifera",
        )

        # Merge tracks
        merged = Track.merge_tracks([track1, track2], "merged_001")

        assert merged.track_id == "merged_001"
        assert merged.clip_id == "video_20240108"
        assert len(merged.detections) == 4
        assert merged.start_frame == 100
        assert merged.end_frame == 104
        assert merged.duration_frames == 5
        assert merged.taxon_id == 47219
        assert merged.scientific_name == "Apis mellifera"
        assert merged.validation_status == "pending"

    def test_merge_tracks_with_gap(self):
        """Test merging tracks with acceptable gap."""
        track1 = Track(
            track_id="track_001",
            clip_id="video_20240108",
            detections=[
                Detection(frame_number=100, bbox=[10, 20, 50, 60], confidence=0.90),
            ],
            start_frame=100,
            end_frame=100,
            duration_frames=1,
            duration_seconds=0.033,
            confidence=0.90,
        )

        track2 = Track(
            track_id="track_002",
            clip_id="video_20240108",
            detections=[
                Detection(frame_number=105, bbox=[15, 25, 50, 60], confidence=0.95),
            ],
            start_frame=105,
            end_frame=105,
            duration_frames=1,
            duration_seconds=0.033,
            confidence=0.95,
        )

        # Should succeed with gap of 4 frames (default threshold is 10)
        merged = Track.merge_tracks([track1, track2], "merged_001")
        assert merged.start_frame == 100
        assert merged.end_frame == 105
        assert len(merged.detections) == 2

    def test_merge_tracks_large_gap_fails(self):
        """Test that merging with large gap fails."""
        track1 = Track(
            track_id="track_001",
            clip_id="video_20240108",
            detections=[
                Detection(frame_number=100, bbox=[10, 20, 50, 60], confidence=0.90),
            ],
            start_frame=100,
            end_frame=100,
            duration_frames=1,
            duration_seconds=0.033,
            confidence=0.90,
        )

        track2 = Track(
            track_id="track_002",
            clip_id="video_20240108",
            detections=[
                Detection(frame_number=115, bbox=[15, 25, 50, 60], confidence=0.95),
            ],
            start_frame=115,
            end_frame=115,
            duration_frames=1,
            duration_seconds=0.033,
            confidence=0.95,
        )

        # Should fail with gap of 14 frames (> default threshold of 10)
        with pytest.raises(ValueError) as exc_info:
            Track.merge_tracks([track1, track2], "merged_001")
        assert "exceeds threshold" in str(exc_info.value)

        # Should succeed with higher threshold
        merged = Track.merge_tracks([track1, track2], "merged_001", gap_threshold=15)
        assert merged.start_frame == 100
        assert merged.end_frame == 115

    def test_merge_tracks_overlap_fails(self):
        """Test that merging overlapping tracks fails."""
        track1 = Track(
            track_id="track_001",
            clip_id="video_20240108",
            detections=[
                Detection(frame_number=100, bbox=[10, 20, 50, 60], confidence=0.90),
                Detection(frame_number=101, bbox=[11, 21, 50, 60], confidence=0.91),
            ],
            start_frame=100,
            end_frame=101,
            duration_frames=2,
            duration_seconds=0.067,
            confidence=0.905,
        )

        track2 = Track(
            track_id="track_002",
            clip_id="video_20240108",
            detections=[
                Detection(frame_number=101, bbox=[11, 21, 50, 60], confidence=0.92),  # Overlaps!
                Detection(frame_number=102, bbox=[12, 22, 50, 60], confidence=0.93),
            ],
            start_frame=101,
            end_frame=102,
            duration_frames=2,
            duration_seconds=0.067,
            confidence=0.925,
        )

        with pytest.raises(ValueError) as exc_info:
            Track.merge_tracks([track1, track2], "merged_001")
        assert "overlap" in str(exc_info.value).lower()

    def test_merge_tracks_different_clips_fails(self):
        """Test that merging tracks from different clips fails."""
        track1 = Track(
            track_id="track_001",
            clip_id="video_001",
            detections=[
                Detection(frame_number=100, bbox=[10, 20, 50, 60], confidence=0.90),
            ],
            start_frame=100,
            end_frame=100,
            duration_frames=1,
            duration_seconds=0.033,
            confidence=0.90,
        )

        track2 = Track(
            track_id="track_002",
            clip_id="video_002",  # Different clip!
            detections=[
                Detection(frame_number=101, bbox=[11, 21, 50, 60], confidence=0.91),
            ],
            start_frame=101,
            end_frame=101,
            duration_frames=1,
            duration_seconds=0.033,
            confidence=0.91,
        )

        with pytest.raises(ValueError) as exc_info:
            Track.merge_tracks([track1, track2], "merged_001")
        assert "different clips" in str(exc_info.value)

    def test_merge_tracks_single_track(self):
        """Test merging a single track returns copy with new ID."""
        track = Track(
            track_id="track_001",
            clip_id="video_20240108",
            detections=[
                Detection(frame_number=100, bbox=[10, 20, 50, 60], confidence=0.90),
            ],
            start_frame=100,
            end_frame=100,
            duration_frames=1,
            duration_seconds=0.033,
            confidence=0.90,
        )

        merged = Track.merge_tracks([track], "new_id")
        assert merged.track_id == "new_id"
        assert merged.clip_id == track.clip_id
        assert len(merged.detections) == 1

    def test_merge_tracks_empty_list_fails(self):
        """Test that merging empty list fails."""
        with pytest.raises(ValueError) as exc_info:
            Track.merge_tracks([], "merged_001")
        assert "empty track list" in str(exc_info.value).lower()

    def test_merge_tracks_taxonomy_consensus(self):
        """Test that merged track uses most common taxonomy."""
        track1 = Track(
            track_id="track_001",
            clip_id="video_20240108",
            detections=[
                Detection(frame_number=100, bbox=[10, 20, 50, 60], confidence=0.90),
                Detection(frame_number=101, bbox=[11, 21, 50, 60], confidence=0.91),
            ],
            start_frame=100,
            end_frame=101,
            duration_frames=2,
            duration_seconds=0.067,
            confidence=0.905,
            taxon_id=47219,
            scientific_name="Apis mellifera",
        )

        track2 = Track(
            track_id="track_002",
            clip_id="video_20240108",
            detections=[
                Detection(frame_number=102, bbox=[12, 22, 50, 60], confidence=0.92),
            ],
            start_frame=102,
            end_frame=102,
            duration_frames=1,
            duration_seconds=0.033,
            confidence=0.92,
            taxon_id=54327,  # Different taxon
            scientific_name="Vespa crabro",
        )

        track3 = Track(
            track_id="track_003",
            clip_id="video_20240108",
            detections=[
                Detection(frame_number=103, bbox=[13, 23, 50, 60], confidence=0.93),
                Detection(frame_number=104, bbox=[14, 24, 50, 60], confidence=0.94),
            ],
            start_frame=103,
            end_frame=104,
            duration_frames=2,
            duration_seconds=0.067,
            confidence=0.935,
            taxon_id=47219,  # Same as track1
            scientific_name="Apis mellifera",
        )

        # Merge - should use taxon 47219 (appears in 4 detections vs 1)
        merged = Track.merge_tracks([track1, track2, track3], "merged_001")
        assert merged.taxon_id == 47219
        assert merged.scientific_name == "Apis mellifera"

    def test_merge_tracks_processing_metadata(self):
        """Test that merged track preserves processing metadata."""
        track1 = Track(
            track_id="track_001",
            clip_id="video_20240108",
            detections=[
                Detection(frame_number=100, bbox=[10, 20, 50, 60], confidence=0.90),
            ],
            start_frame=100,
            end_frame=100,
            duration_frames=1,
            duration_seconds=0.033,
            confidence=0.90,
            detector="yolov8",
            tracker="bytetrack",
            smoothing_applied=False,
        )

        track2 = Track(
            track_id="track_002",
            clip_id="video_20240108",
            detections=[
                Detection(frame_number=101, bbox=[11, 21, 50, 60], confidence=0.91),
            ],
            start_frame=101,
            end_frame=101,
            duration_frames=1,
            duration_seconds=0.033,
            confidence=0.91,
            detector="yolov8",
            tracker="bytetrack",
            smoothing_applied=True,
            smoothing_method="kalman",
        )

        merged = Track.merge_tracks([track1, track2], "merged_001")
        assert merged.detector == "yolov8"
        assert merged.tracker == "bytetrack"
        assert merged.smoothing_applied is True  # Any track had smoothing
        assert merged.smoothing_method == "kalman"
