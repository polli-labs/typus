"""Tests for models using canonical bbox types (Detection, Track)."""

import pytest

from typus.models.geometry import BBoxXYWHNorm
from typus.models.tracks import Detection, Track


class TestDetectionCanonicalBbox:
    """Test Detection model with canonical bbox support."""

    def test_detection_with_canonical_bbox(self):
        """Test creating Detection with canonical bbox_norm."""
        bbox = BBoxXYWHNorm(x=0.1, y=0.2, w=0.3, h=0.4)
        detection = Detection(frame_number=100, bbox_norm=bbox, confidence=0.95)

        assert detection.frame_number == 100
        assert detection.bbox_norm == bbox
        assert detection.confidence == 0.95
        assert detection.bbox is None  # Legacy field not set

    def test_detection_with_legacy_bbox(self):
        """Test creating Detection with legacy bbox field."""
        detection = Detection(frame_number=50, bbox=[10.0, 20.0, 30.0, 40.0], confidence=0.85)

        assert detection.frame_number == 50
        assert detection.bbox == [10.0, 20.0, 30.0, 40.0]
        assert detection.bbox_norm is None  # Canonical field not set
        assert detection.confidence == 0.85

    def test_detection_with_both_bbox_fields(self):
        """Test Detection with both canonical and legacy bbox."""
        bbox = BBoxXYWHNorm(x=0.1, y=0.2, w=0.3, h=0.4)
        detection = Detection(
            frame_number=75, bbox_norm=bbox, bbox=[10.0, 20.0, 30.0, 40.0], confidence=0.90
        )

        assert detection.bbox_norm == bbox
        assert detection.bbox == [10.0, 20.0, 30.0, 40.0]

    def test_detection_bbox_validation_error(self):
        """Test that Detection requires at least one bbox field."""
        with pytest.raises(ValueError, match="Either bbox_norm or bbox must be provided"):
            Detection(
                frame_number=100,
                confidence=0.95,
                # No bbox_norm or bbox provided
            )

    def test_detection_from_raw_with_provider(self):
        """Test Detection.from_raw_detection with provider mapping."""
        # Mock raw detection with Gemini BR coordinates
        raw_data = {
            "frame_number": 100,
            "bbox": [50, 50, 80, 90],  # BR xyxy coordinates
            "confidence": 0.95,
            "taxon_id": 47219,
        }

        # Convert using Gemini mapper
        detection = Detection.from_raw_detection(
            raw_data, upload_w=100, upload_h=100, provider="gemini_br_xyxy"
        )

        # Should have both canonical and legacy bbox
        assert detection.bbox_norm is not None
        assert detection.bbox == [50, 50, 80, 90]  # Legacy preserved
        assert detection.frame_number == 100
        assert detection.confidence == 0.95

    def test_detection_from_raw_without_provider(self):
        """Test Detection.from_raw_detection without provider (direct construction)."""
        raw_data = {
            "frame_number": 100,
            "bbox_norm": {"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4},
            "confidence": 0.95,
        }

        detection = Detection.from_raw_detection(raw_data)

        assert detection.bbox_norm.x == 0.1
        assert detection.bbox_norm.y == 0.2
        assert detection.bbox_norm.w == 0.3
        assert detection.bbox_norm.h == 0.4

    def test_detection_from_raw_missing_dimensions(self):
        """Test error when provider requires but dimensions missing."""
        raw_data = {"frame_number": 100, "bbox": [50, 50, 80, 90], "confidence": 0.95}

        with pytest.raises(ValueError, match="upload_w and upload_h required"):
            Detection.from_raw_detection(raw_data, provider="gemini_br_xyxy")

    def test_detection_from_raw_bbox_disagreement(self):
        """Test error when bbox_norm and bbox disagree beyond tolerance."""
        raw_data = {
            "frame_number": 100,
            "bbox_norm": {
                "x": 0.1,
                "y": 0.2,
                "w": 0.3,
                "h": 0.4,
            },  # Would be ~(10,20,30,40) in 100x100
            "bbox": [50, 60, 30, 40],  # Completely different bbox
            "confidence": 0.95,
        }

        with pytest.raises(ValueError, match="bbox_norm and bbox disagree beyond tolerance"):
            Detection.from_raw_detection(raw_data, upload_w=100, upload_h=100)

    def test_detection_from_raw_ambiguous_legacy(self):
        """Test error when legacy bbox provided without provider hint."""
        raw_data = {
            "frame_number": 100,
            "bbox": [50, 50, 80, 90],  # Ambiguous format
            "confidence": 0.95,
        }

        with pytest.raises(ValueError, match="Ambiguous legacy bbox format.*specify 'provider'"):
            Detection.from_raw_detection(raw_data, upload_w=100, upload_h=100)

    def test_detection_from_raw_unknown_provider(self):
        """Test error when unknown provider specified."""
        raw_data = {"frame_number": 100, "bbox": [50, 50, 80, 90], "confidence": 0.95}

        with pytest.raises(KeyError, match="No bbox mapper registered for 'unknown_provider'"):
            Detection.from_raw_detection(
                raw_data, upload_w=100, upload_h=100, provider="unknown_provider"
            )

    def test_detection_smoothed_bbox_support(self):
        """Test that Detection supports smoothed canonical bbox."""
        bbox = BBoxXYWHNorm(x=0.1, y=0.2, w=0.3, h=0.4)
        smoothed_bbox = BBoxXYWHNorm(x=0.11, y=0.21, w=0.29, h=0.39)

        detection = Detection(
            frame_number=100, bbox_norm=bbox, smoothed_bbox_norm=smoothed_bbox, confidence=0.95
        )

        assert detection.bbox_norm == bbox
        assert detection.smoothed_bbox_norm == smoothed_bbox


class TestTrackWithCanonicalBbox:
    """Test Track model with canonical bbox in detections."""

    def test_track_with_canonical_detections(self):
        """Test creating Track with canonical bbox detections."""
        bbox1 = BBoxXYWHNorm(x=0.1, y=0.2, w=0.3, h=0.4)
        bbox2 = BBoxXYWHNorm(x=0.15, y=0.25, w=0.25, h=0.35)

        detection1 = Detection(frame_number=100, bbox_norm=bbox1, confidence=0.95)
        detection2 = Detection(frame_number=101, bbox_norm=bbox2, confidence=0.90)

        track = Track(
            track_id="track_001",
            clip_id="video_001",
            detections=[detection1, detection2],
            start_frame=100,
            end_frame=101,
            duration_frames=2,
            duration_seconds=0.067,  # 2 frames at 30fps
            confidence=0.925,
        )

        assert track.track_id == "track_001"
        assert len(track.detections) == 2
        assert track.detections[0].bbox_norm == bbox1
        assert track.detections[1].bbox_norm == bbox2

    def test_track_from_raw_detections(self):
        """Test Track.from_raw_detections factory method."""
        raw_detections = [
            {
                "frame_number": 100,
                "bbox_norm": {"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4},
                "confidence": 0.95,
            },
            {
                "frame_number": 101,
                "bbox_norm": {"x": 0.15, "y": 0.25, "w": 0.25, "h": 0.35},
                "confidence": 0.90,
            },
        ]

        track = Track.from_raw_detections(
            track_id="track_002", clip_id="video_002", detections=raw_detections, fps=30.0
        )

        assert track.track_id == "track_002"
        assert len(track.detections) == 2
        assert track.start_frame == 100
        assert track.end_frame == 101
        assert track.duration_frames == 2
        assert abs(track.duration_seconds - 2.0 / 30.0) < 1e-6

    def test_track_mixed_bbox_types(self):
        """Test Track with mix of canonical and legacy bbox detections."""
        # One detection with canonical bbox
        canonical_detection = Detection(
            frame_number=100, bbox_norm=BBoxXYWHNorm(x=0.1, y=0.2, w=0.3, h=0.4), confidence=0.95
        )

        # One detection with legacy bbox
        legacy_detection = Detection(
            frame_number=101, bbox=[10.0, 20.0, 30.0, 40.0], confidence=0.90
        )

        track = Track(
            track_id="track_mixed",
            clip_id="video_mixed",
            detections=[canonical_detection, legacy_detection],
            start_frame=100,
            end_frame=101,
            duration_frames=2,
            duration_seconds=0.067,
            confidence=0.925,
        )

        assert track.detections[0].bbox_norm is not None
        assert track.detections[0].bbox is None
        assert track.detections[1].bbox_norm is None
        assert track.detections[1].bbox is not None

    def test_track_json_serialization_with_canonical(self):
        """Test JSON serialization of Track with canonical bboxes."""
        detection = Detection(
            frame_number=100, bbox_norm=BBoxXYWHNorm(x=0.1, y=0.2, w=0.3, h=0.4), confidence=0.95
        )

        track = Track(
            track_id="track_json",
            clip_id="video_json",
            detections=[detection],
            start_frame=100,
            end_frame=100,
            duration_frames=1,
            duration_seconds=0.033,
            confidence=0.95,
        )

        # Should serialize successfully
        track_dict = track.model_dump()

        # Check that canonical bbox is in the output
        det_dict = track_dict["detections"][0]
        assert "bbox_norm" in det_dict
        assert det_dict["bbox_norm"]["x"] == 0.1
        assert det_dict["bbox_norm"]["y"] == 0.2

        # Should deserialize successfully
        track_restored = Track.model_validate(track_dict)
        assert track_restored.detections[0].bbox_norm.x == 0.1
