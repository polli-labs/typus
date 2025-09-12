"""Lightweight geometry and tracking helpers.

These functions provide portable, dependency-light utilities that complement
the canonical geometry types under `typus.models.geometry` and the
tracking models under `typus.models.tracks`.

Import convenience:

    from typus.ops import (
        iou_xyxy,
        area_xyxy,
        intersect_xyxy,
        clamp_xyxy,
        to_xywh_px,
        from_xywh_px,
        group_detections_by_frame,
        detection_xyxy_px,
    )
"""

from .bbox import (
    area_xyxy,
    clamp_xyxy,
    from_xywh_px,
    intersect_xyxy,
    iou_xyxy,
    to_xywh_px,
    xywh_to_xyxy,
    xyxy_to_xywh,
)
from .tracks import detection_xyxy_px, group_detections_by_frame

__all__ = [
    "iou_xyxy",
    "area_xyxy",
    "intersect_xyxy",
    "clamp_xyxy",
    "to_xywh_px",
    "from_xywh_px",
    "xyxy_to_xywh",
    "xywh_to_xyxy",
    "group_detections_by_frame",
    "detection_xyxy_px",
]
