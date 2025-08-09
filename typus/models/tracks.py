"""Track models for object tracking in video analysis.

This module provides standardized data models for representing tracks
(object trajectories through video), including individual detections,
statistical summaries, and validation metadata.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Detection(BaseModel):
    """Single detection within a track.
    
    Represents one observation of an object at a specific frame,
    including its bounding box, confidence score, and optional
    taxonomic identification.
    """
    
    frame_number: int = Field(..., ge=0, description="Frame number in the video")
    bbox: list[float] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Bounding box [x, y, width, height] in pixels"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Detection confidence score"
    )
    
    # Optional taxonomy info (may be enriched post-detection)
    taxon_id: Optional[int] = Field(
        None,
        description="Taxonomic ID from taxonomy service"
    )
    scientific_name: Optional[str] = Field(
        None,
        description="Scientific name of detected organism"
    )
    common_name: Optional[str] = Field(
        None,
        description="Common name of detected organism"
    )
    
    # Optional smoothed/processed values
    smoothed_bbox: Optional[list[float]] = Field(
        None,
        min_length=4,
        max_length=4,
        description="Smoothed bounding box after post-processing"
    )
    velocity: Optional[list[float]] = Field(
        None,
        min_length=2,
        max_length=2,
        description="Velocity [vx, vy] in pixels/frame"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "frame_number": 100,
                "bbox": [10.5, 20.5, 50.0, 60.0],
                "confidence": 0.95,
                "taxon_id": 47219,
                "scientific_name": "Apis mellifera",
                "common_name": "Western honey bee"
            }
        }
    }


class TrackStats(BaseModel):
    """Statistical summary of track metrics.
    
    Provides aggregate statistics about a track's confidence scores
    and optionally other metrics like bounding box stability.
    """
    
    confidence_mean: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Mean confidence across all detections"
    )
    confidence_std: float = Field(
        ...,
        ge=0.0,
        description="Standard deviation of confidence scores"
    )
    confidence_min: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Minimum confidence score in track"
    )
    confidence_max: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Maximum confidence score in track"
    )
    bbox_stability: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Measure of bounding box consistency (0=unstable, 1=stable)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "confidence_mean": 0.92,
                "confidence_std": 0.05,
                "confidence_min": 0.85,
                "confidence_max": 0.98,
                "bbox_stability": 0.88
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
        ...,
        min_length=1,
        description="List of detections forming this track"
    )
    start_frame: int = Field(..., ge=0, description="First frame of the track")
    end_frame: int = Field(..., ge=0, description="Last frame of the track")
    duration_frames: int = Field(..., ge=1, description="Total frames in track")
    duration_seconds: float = Field(..., gt=0, description="Duration in seconds")
    
    # Aggregate metrics
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall track confidence score"
    )
    stats: Optional[TrackStats] = Field(
        None,
        description="Statistical summary of track metrics"
    )
    
    # Taxonomy (consensus or most confident)
    taxon_id: Optional[int] = Field(
        None,
        description="Consensus taxonomic ID for the track"
    )
    scientific_name: Optional[str] = Field(
        None,
        description="Consensus scientific name"
    )
    common_name: Optional[str] = Field(
        None,
        description="Consensus common name"
    )
    
    # Validation
    validation_status: Optional[Literal['pending', 'validated', 'rejected']] = Field(
        'pending',
        description="Human validation status"
    )
    validation_notes: Optional[str] = Field(
        None,
        description="Notes from validation process"
    )
    validated_by: Optional[str] = Field(
        None,
        description="Username/ID of validator"
    )
    validated_at: Optional[datetime] = Field(
        None,
        description="Timestamp of validation"
    )
    
    # Processing metadata
    detector: Optional[str] = Field(
        None,
        description="Detection model used (e.g., 'yolov8', 'clip21')"
    )
    tracker: Optional[str] = Field(
        None,
        description="Tracking algorithm used (e.g., 'sort', 'bytetrack')"
    )
    smoothing_applied: bool = Field(
        False,
        description="Whether smoothing was applied to detections"
    )
    smoothing_method: Optional[str] = Field(
        None,
        description="Smoothing method used (e.g., 'kalman', 'spline')"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "track_id": "track_001",
                "clip_id": "video_20240108_1234",
                "detections": [
                    {
                        "frame_number": 100,
                        "bbox": [10, 20, 50, 60],
                        "confidence": 0.95,
                        "taxon_id": 47219
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
                "tracker": "bytetrack"
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
        cls,
        track_id: str,
        clip_id: str,
        detections: list[dict],
        fps: float = 30.0,
        **kwargs
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
        if 'stats' not in kwargs:
            import statistics
            kwargs['stats'] = TrackStats(
                confidence_mean=confidence_mean,
                confidence_std=statistics.stdev(confidences) if len(confidences) > 1 else 0.0,
                confidence_min=min(confidences),
                confidence_max=max(confidences)
            )
        
        # Use mean confidence if not provided
        if 'confidence' not in kwargs:
            kwargs['confidence'] = confidence_mean
        
        return cls(
            track_id=track_id,
            clip_id=clip_id,
            detections=detection_objs,
            start_frame=start_frame,
            end_frame=end_frame,
            duration_frames=duration_frames,
            duration_seconds=duration_seconds,
            **kwargs
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
            gap = frame_numbers[i] - frame_numbers[i-1] - 1
            if gap > max_gap:
                return False
        return True