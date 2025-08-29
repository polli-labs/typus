"""Track models for object tracking in video analysis.

This module provides standardized data models for representing tracks
(object trajectories through video), including individual detections,
statistical summaries, and validation metadata.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

from .geometry import BBoxMapper, BBoxXYWHNorm


class Detection(BaseModel):
    """Single detection within a track.

    Represents one observation of an object at a specific frame,
    including its bounding box, confidence score, and optional
    taxonomic identification.
    """

    frame_number: int = Field(..., ge=0, description="Frame number in the video")

    # Canonical bbox (preferred)
    bbox_norm: BBoxXYWHNorm | None = Field(
        None, description="Canonical bounding box [x, y, w, h] - top-left origin, normalized [0,1]"
    )

    # Legacy bbox field (deprecated)
    bbox: list[float] | None = Field(
        None,
        min_length=4,
        max_length=4,
        description="Legacy pixel bbox [x, y, width, height] - DEPRECATED, use bbox_norm",
    )

    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence score")

    # Optional taxonomy info (may be enriched post-detection)
    taxon_id: Optional[int] = Field(None, description="Taxonomic ID from taxonomy service")
    scientific_name: Optional[str] = Field(None, description="Scientific name of detected organism")
    common_name: Optional[str] = Field(None, description="Common name of detected organism")

    # Optional smoothed/processed values
    smoothed_bbox: Optional[list[float]] = Field(
        None, min_length=4, max_length=4, description="Smoothed bounding box after post-processing"
    )
    smoothed_bbox_norm: Optional[BBoxXYWHNorm] = Field(
        None, description="Smoothed canonical bbox after post-processing"
    )
    velocity: Optional[list[float]] = Field(
        None, min_length=2, max_length=2, description="Velocity [vx, vy] in pixels/frame"
    )

    @model_validator(mode="after")
    def validate_bbox_fields(self) -> "Detection":
        """Ensure at least one bbox field is provided."""
        if self.bbox_norm is None and self.bbox is None:
            raise ValueError("Either bbox_norm or bbox must be provided")
        return self

    @classmethod
    def from_raw_detection(
        cls,
        raw: dict,
        *,
        upload_w: int | None = None,
        upload_h: int | None = None,
        provider: str | None = None,
    ) -> "Detection":
        """Create Detection from raw bbox data with optional provider mapping.

        When both bbox_norm (canonical) and bbox (legacy pixel) are present, this method
        validates they agree within a 1.0 pixel tolerance. This accounts for rounding
        differences due to the half-up rounding policy at pixel boundaries.

        Args:
            raw: Raw detection dictionary
            upload_w, upload_h: Image dimensions for provider mapping
            provider: Provider hint for bbox format conversion (e.g., 'gemini_br_xyxy')

        Returns:
            Detection instance with canonical bbox_norm

        Raises:
            ValueError: If provider mapping fails, dimensions missing, or bbox disagreement
        """
        detection_data = raw.copy()

        # Handle bbox conversion if provider is specified
        provider_mapping_used = False
        if "bbox" in raw and provider is not None:
            if upload_w is None or upload_h is None:
                raise ValueError("upload_w and upload_h required for provider mapping")

            mapper_fn = BBoxMapper.get(provider)
            bbox_data = raw["bbox"]
            if len(bbox_data) == 4:
                canonical_bbox = mapper_fn(*bbox_data, upload_w, upload_h)
                detection_data["bbox_norm"] = canonical_bbox
                # Keep legacy bbox for compatibility
                detection_data["bbox"] = bbox_data
                provider_mapping_used = True

        # Validate agreement if both bbox_norm and bbox are present with dimensions
        # BUT skip validation if provider mapping was used (bbox is in provider format)
        if (
            "bbox_norm" in detection_data
            and "bbox" in detection_data
            and upload_w is not None
            and upload_h is not None
            and not provider_mapping_used
        ):
            bbox_norm = detection_data["bbox_norm"]
            if not isinstance(bbox_norm, BBoxXYWHNorm):
                bbox_norm = BBoxXYWHNorm(**bbox_norm) if isinstance(bbox_norm, dict) else bbox_norm

            # Convert canonical to pixel xywh for comparison
            from .geometry import to_xyxy_px

            x1, y1, x2, y2 = to_xyxy_px(bbox_norm, upload_w, upload_h)
            canonical_as_xywh = [x1, y1, x2 - x1, y2 - y1]

            legacy_bbox = detection_data["bbox"]
            if len(legacy_bbox) == 4:
                # Allow 1-pixel tolerance for rounding differences
                tolerance = 1.0
                diffs = [abs(canonical_as_xywh[i] - legacy_bbox[i]) for i in range(4)]
                if any(diff > tolerance for diff in diffs):
                    raise ValueError(
                        f"bbox_norm and bbox disagree beyond tolerance (≤{tolerance}px): "
                        f"canonical_as_xywh={canonical_as_xywh}, legacy={legacy_bbox}, "
                        f"diffs={diffs}"
                    )

        # Require provider hint for ambiguous legacy bbox
        if (
            "bbox" in raw
            and "bbox_norm" not in raw
            and provider is None
            and upload_w is not None
            and upload_h is not None
        ):
            raise ValueError(
                "Ambiguous legacy bbox format detected. Please specify 'provider' parameter "
                "(e.g., 'gemini_br_xyxy') or provide 'bbox_norm' directly for clarity."
            )

        return cls(**detection_data)

    model_config = {
        "json_schema_extra": {
            "example": {
                "frame_number": 100,
                "bbox_norm": {"x": 0.1, "y": 0.2, "w": 0.5, "h": 0.6},
                "confidence": 0.95,
                "taxon_id": 47219,
                "scientific_name": "Apis mellifera",
                "common_name": "Western honey bee",
            }
        }
    }


class TrackStats(BaseModel):
    """Statistical summary of track metrics.

    Provides aggregate statistics about a track's confidence scores
    and optionally other metrics like bounding box stability.
    """

    confidence_mean: float = Field(
        ..., ge=0.0, le=1.0, description="Mean confidence across all detections"
    )
    confidence_std: float = Field(
        ..., ge=0.0, description="Standard deviation of confidence scores"
    )
    confidence_min: float = Field(
        ..., ge=0.0, le=1.0, description="Minimum confidence score in track"
    )
    confidence_max: float = Field(
        ..., ge=0.0, le=1.0, description="Maximum confidence score in track"
    )
    bbox_stability: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Measure of bounding box consistency (0=unstable, 1=stable)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "confidence_mean": 0.92,
                "confidence_std": 0.05,
                "confidence_min": 0.85,
                "confidence_max": 0.98,
                "bbox_stability": 0.88,
            }
        }
    }


class Track(BaseModel):
    """Complete track representing an object's journey through a video.

    A track consists of multiple detections linked across frames,
    representing the same object as it moves through the video.
    Includes aggregate metrics, taxonomic consensus, and validation metadata.
    """

    track_id: str = Field(..., description="Unique identifier for this track")
    clip_id: str = Field(..., description="ID of the video clip containing this track")

    # Core tracking data
    detections: list[Detection] = Field(
        ..., min_length=1, description="List of detections forming this track"
    )
    start_frame: int = Field(..., ge=0, description="First frame of the track")
    end_frame: int = Field(..., ge=0, description="Last frame of the track")
    duration_frames: int = Field(..., ge=1, description="Total frames in track")
    duration_seconds: float = Field(..., gt=0, description="Duration in seconds")

    # Aggregate metrics
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall track confidence score")
    stats: Optional[TrackStats] = Field(None, description="Statistical summary of track metrics")

    # Taxonomy (consensus or most confident)
    taxon_id: Optional[int] = Field(None, description="Consensus taxonomic ID for the track")
    scientific_name: Optional[str] = Field(None, description="Consensus scientific name")
    common_name: Optional[str] = Field(None, description="Consensus common name")

    # Validation
    validation_status: Optional[Literal["pending", "validated", "rejected"]] = Field(
        "pending", description="Human validation status"
    )
    validation_notes: Optional[str] = Field(None, description="Notes from validation process")
    validated_by: Optional[str] = Field(None, description="Username/ID of validator")
    validated_at: Optional[datetime] = Field(None, description="Timestamp of validation")

    # Processing metadata
    detector: Optional[str] = Field(
        None, description="Detection model used (e.g., 'yolov8', 'clip21')"
    )
    tracker: Optional[str] = Field(
        None, description="Tracking algorithm used (e.g., 'sort', 'bytetrack')"
    )
    smoothing_applied: bool = Field(
        False, description="Whether smoothing was applied to detections"
    )
    smoothing_method: Optional[str] = Field(
        None, description="Smoothing method used (e.g., 'kalman', 'spline')"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "track_id": "track_001",
                "clip_id": "video_20240108_1234",
                "detections": [
                    {
                        "frame_number": 100,
                        "bbox_norm": {"x": 0.1, "y": 0.2, "w": 0.5, "h": 0.6},
                        "confidence": 0.95,
                        "taxon_id": 47219,
                    }
                ],
                "start_frame": 100,
                "end_frame": 250,
                "duration_frames": 150,
                "duration_seconds": 5.0,
                "confidence": 0.92,
                "taxon_id": 47219,
                "scientific_name": "Apis mellifera",
                "common_name": "Western honey bee",
                "validation_status": "validated",
                "detector": "yolov8",
                "tracker": "bytetrack",
            }
        }
    }

    def model_post_init(self, __context) -> None:
        """Perform validation and compute derived fields after initialization."""
        # Ensure start_frame and end_frame are consistent with detections
        if self.detections:
            actual_start = min(d.frame_number for d in self.detections)
            actual_end = max(d.frame_number for d in self.detections)

            if self.start_frame != actual_start:
                self.start_frame = actual_start
            if self.end_frame != actual_end:
                self.end_frame = actual_end

            # Ensure duration_frames is consistent
            expected_duration = self.end_frame - self.start_frame + 1
            if self.duration_frames != expected_duration:
                self.duration_frames = expected_duration

    @classmethod
    def from_raw_detections(
        cls, track_id: str, clip_id: str, detections: list[dict], fps: float = 30.0, **kwargs
    ) -> Track:
        """Create a Track from raw detection dictionaries.

        Args:
            track_id: Unique identifier for the track
            clip_id: ID of the video clip
            detections: List of detection dictionaries
            fps: Frames per second for duration calculation
            **kwargs: Additional fields for the Track

        Returns:
            Track instance with computed metrics
        """
        # Convert raw detections to Detection objects
        detection_objs = [Detection(**d) for d in detections]

        # Compute frame range
        frame_numbers = [d.frame_number for d in detection_objs]
        start_frame = min(frame_numbers)
        end_frame = max(frame_numbers)
        duration_frames = end_frame - start_frame + 1
        duration_seconds = duration_frames / fps

        # Compute confidence statistics
        confidences = [d.confidence for d in detection_objs]
        confidence_mean = sum(confidences) / len(confidences)

        # Build stats if not provided
        if "stats" not in kwargs:
            import statistics

            kwargs["stats"] = TrackStats(
                confidence_mean=confidence_mean,
                confidence_std=statistics.stdev(confidences) if len(confidences) > 1 else 0.0,
                confidence_min=min(confidences),
                confidence_max=max(confidences),
            )

        # Use mean confidence if not provided
        if "confidence" not in kwargs:
            kwargs["confidence"] = confidence_mean

        return cls(
            track_id=track_id,
            clip_id=clip_id,
            detections=detection_objs,
            start_frame=start_frame,
            end_frame=end_frame,
            duration_frames=duration_frames,
            duration_seconds=duration_seconds,
            **kwargs,
        )

    def get_detection_at_frame(self, frame_number: int) -> Optional[Detection]:
        """Get detection at a specific frame number.

        Args:
            frame_number: The frame number to query

        Returns:
            Detection at that frame, or None if not found
        """
        for detection in self.detections:
            if detection.frame_number == frame_number:
                return detection
        return None

    def get_frame_numbers(self) -> list[int]:
        """Get sorted list of all frame numbers in this track.

        Returns:
            Sorted list of frame numbers
        """
        return sorted(d.frame_number for d in self.detections)

    def is_continuous(self, max_gap: int = 1) -> bool:
        """Check if track is continuous (no large gaps between detections).

        Args:
            max_gap: Maximum allowed gap between consecutive detections

        Returns:
            True if track has no gaps larger than max_gap
        """
        frame_numbers = self.get_frame_numbers()
        if len(frame_numbers) <= 1:
            return True

        for i in range(1, len(frame_numbers)):
            gap = frame_numbers[i] - frame_numbers[i - 1] - 1
            if gap > max_gap:
                return False
        return True

    @property
    def duration(self) -> float:
        """Alias for duration_seconds for API compatibility.

        Returns:
            Duration in seconds
        """
        return self.duration_seconds

    def frame_to_time(self, frame_number: int, fps: float = 30.0) -> float:
        """Convert frame number to time in seconds relative to track start.

        Args:
            frame_number: The frame number to convert
            fps: Frames per second (default: 30.0)

        Returns:
            Time in seconds from start of track

        Raises:
            ValueError: If frame_number is outside track range
        """
        if frame_number < self.start_frame or frame_number > self.end_frame:
            raise ValueError(
                f"Frame {frame_number} outside track range [{self.start_frame}, {self.end_frame}]"
            )
        return (frame_number - self.start_frame) / fps

    @classmethod
    def merge_tracks(
        cls, tracks: list["Track"], new_track_id: str, gap_threshold: int = 10
    ) -> "Track":
        """Merge multiple tracks into one continuous track.

        This is useful for re-connecting tracks that were incorrectly split
        by the tracking algorithm.

        Args:
            tracks: List of tracks to merge (must be from same clip)
            new_track_id: ID for the merged track
            gap_threshold: Maximum frame gap to allow between tracks

        Returns:
            Merged track with combined detections

        Raises:
            ValueError: If tracks are from different clips or have large gaps
        """
        if not tracks:
            raise ValueError("Cannot merge empty track list")

        if len(tracks) == 1:
            # Single track, just return copy with new ID
            track = tracks[0].model_copy()
            track.track_id = new_track_id
            return track

        # Verify all tracks are from same clip
        clip_ids = {t.clip_id for t in tracks}
        if len(clip_ids) > 1:
            raise ValueError(f"Cannot merge tracks from different clips: {clip_ids}")

        # Sort tracks by start frame
        sorted_tracks = sorted(tracks, key=lambda t: t.start_frame)

        # Check for overlaps or large gaps
        for i in range(1, len(sorted_tracks)):
            prev_track = sorted_tracks[i - 1]
            curr_track = sorted_tracks[i]

            # Check for overlap
            if prev_track.end_frame >= curr_track.start_frame:
                raise ValueError(
                    f"Tracks overlap: {prev_track.track_id} ends at {prev_track.end_frame}, "
                    f"{curr_track.track_id} starts at {curr_track.start_frame}"
                )

            # Check gap size
            gap = curr_track.start_frame - prev_track.end_frame - 1
            if gap > gap_threshold:
                raise ValueError(
                    f"Gap of {gap} frames between tracks exceeds threshold {gap_threshold}"
                )

        # Merge detections
        all_detections = []
        for track in sorted_tracks:
            all_detections.extend(track.detections)

        # Sort detections by frame number
        all_detections.sort(key=lambda d: d.frame_number)

        # Compute merged track properties
        first_track = sorted_tracks[0]
        last_track = sorted_tracks[-1]

        start_frame = first_track.start_frame
        end_frame = last_track.end_frame
        duration_frames = end_frame - start_frame + 1

        # Estimate duration based on first track's fps
        if first_track.duration_seconds > 0 and first_track.duration_frames > 0:
            fps = first_track.duration_frames / first_track.duration_seconds
            duration_seconds = duration_frames / fps
        else:
            duration_seconds = duration_frames / 30.0  # Default to 30 fps

        # Compute overall confidence
        all_confidences = [d.confidence for d in all_detections]
        overall_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0

        # Merge taxonomy (use most common or highest confidence)
        taxon_counts = {}
        for track in sorted_tracks:
            if track.taxon_id:
                taxon_counts[track.taxon_id] = taxon_counts.get(track.taxon_id, 0) + len(
                    track.detections
                )

        merged_taxon_id = None
        merged_scientific_name = None
        merged_common_name = None

        if taxon_counts:
            # Use taxon with most detections
            merged_taxon_id = max(taxon_counts, key=taxon_counts.get)
            # Find the track with this taxon to get names
            for track in sorted_tracks:
                if track.taxon_id == merged_taxon_id:
                    merged_scientific_name = track.scientific_name
                    merged_common_name = track.common_name
                    break

        # Merge processing metadata (use first track's metadata)
        detector = first_track.detector
        tracker = first_track.tracker

        # Check if any track had smoothing
        smoothing_applied = any(t.smoothing_applied for t in sorted_tracks)
        smoothing_methods = {t.smoothing_method for t in sorted_tracks if t.smoothing_method}
        smoothing_method = ", ".join(smoothing_methods) if smoothing_methods else None

        # Create merged track
        merged_track = cls(
            track_id=new_track_id,
            clip_id=first_track.clip_id,
            detections=all_detections,
            start_frame=start_frame,
            end_frame=end_frame,
            duration_frames=duration_frames,
            duration_seconds=duration_seconds,
            confidence=overall_confidence,
            taxon_id=merged_taxon_id,
            scientific_name=merged_scientific_name,
            common_name=merged_common_name,
            validation_status="pending",  # Reset validation for merged track
            detector=detector,
            tracker=tracker,
            smoothing_applied=smoothing_applied,
            smoothing_method=smoothing_method,
        )

        # Compute stats for merged track
        if all_confidences:
            import statistics

            merged_track.stats = TrackStats(
                confidence_mean=overall_confidence,
                confidence_std=statistics.stdev(all_confidences)
                if len(all_confidences) > 1
                else 0.0,
                confidence_min=min(all_confidences),
                confidence_max=max(all_confidences),
            )

        return merged_track
