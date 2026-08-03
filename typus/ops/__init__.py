"""Lightweight geometry helpers.

These functions provide portable, dependency-light utilities that complement
the canonical geometry types under `typus.models.geometry`.

Import convenience:

    from typus.ops import (
        iou_xyxy,
        area_xyxy,
        intersect_xyxy,
        union_xyxy,
        clamp_xyxy,
        to_xywh_px,
        from_xywh_px,
    )
"""

from .bbox import (
    area_xyxy,
    clamp_xyxy,
    from_xywh_px,
    intersect_xyxy,
    iou_xyxy,
    to_xywh_px,
    union_xyxy,
    xywh_to_xyxy,
    xyxy_to_xywh,
)

__all__ = [
    "iou_xyxy",
    "area_xyxy",
    "intersect_xyxy",
    "union_xyxy",
    "clamp_xyxy",
    "to_xywh_px",
    "from_xywh_px",
    "xyxy_to_xywh",
    "xywh_to_xyxy",
]
