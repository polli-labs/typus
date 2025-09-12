from __future__ import annotations

from typing import Tuple

from typus.models.geometry import EPS, BBoxXYWHNorm


def area_xyxy(b: Tuple[float, float, float, float]) -> float:
    """Area of a pixel-space `xyxy` rectangle.

    Negative extents are clamped to zero to be robust to degenerate inputs.
    """
    x1, y1, x2, y2 = b
    w = max(0.0, x2 - x1)
    h = max(0.0, y2 - y1)
    return w * h


def intersect_xyxy(
    a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]
) -> Tuple[float, float, float, float] | None:
    """Intersection rectangle of two `xyxy` boxes or `None` if disjoint/touching."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b

    x1 = max(ax1, bx1)
    y1 = max(ay1, by1)
    x2 = min(ax2, bx2)
    y2 = min(ay2, by2)

    if x2 <= x1 or y2 <= y1:
        return None
    return (x1, y1, x2, y2)


def iou_xyxy(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
    """Intersection over Union for two `xyxy` pixel-space boxes.

    Returns 0.0 when there is no overlap (including edge-touching).
    """
    inter = intersect_xyxy(a, b)
    if inter is None:
        return 0.0

    inter_area = area_xyxy(inter)
    if inter_area <= 0.0:
        return 0.0

    a_area = area_xyxy(a)
    b_area = area_xyxy(b)
    union = a_area + b_area - inter_area
    if union <= 0.0:
        return 0.0
    return inter_area / union


def clamp_xyxy(
    b: Tuple[float, float, float, float], W: int, H: int
) -> Tuple[float, float, float, float]:
    """Clamp an `xyxy` box to image bounds `[0,W] x [0,H]`.

    Ordering is preserved so that the output always has `x1 <= x2` and `y1 <= y2`.
    """
    x1, y1, x2, y2 = b
    x1 = min(max(0.0, x1), float(W))
    y1 = min(max(0.0, y1), float(H))
    x2 = min(max(0.0, x2), float(W))
    y2 = min(max(0.0, y2), float(H))

    # Ensure ordering in case the input was inverted
    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1
    return (x1, y1, x2, y2)


def to_xywh_px(bbox_norm: BBoxXYWHNorm, W: int, H: int) -> Tuple[float, float, float, float]:
    """Convert normalized TL-`xywh` to pixel TL-`xywh` using image dimensions.

    Uses simple scaling without rounding to preserve fractional pixel information.
    """
    return (
        bbox_norm.x * W,
        bbox_norm.y * H,
        bbox_norm.w * W,
        bbox_norm.h * H,
    )


def from_xywh_px(x: float, y: float, w: float, h: float, W: int, H: int) -> BBoxXYWHNorm:
    """Convert pixel TL-`xywh` to normalized TL-`xywh` using image dimensions.

    Values are clamped to `[0,1]` to avoid float precision edge cases, with a
    minimal positive width/height enforced by the `BBoxXYWHNorm` model.
    """
    if w <= 0 or h <= 0:
        raise ValueError("xywh invalid: non-positive width/height")

    xn = max(0.0, x / W)
    yn = max(0.0, y / H)
    wn = w / W
    hn = h / H

    # Clamp to [0,1]
    xn = min(1.0, max(0.0, xn))
    yn = min(1.0, max(0.0, yn))
    # Enforce minimal positive extents (mirror geometry.from_xyxy_px policy)
    wn = min(1.0, max(EPS, wn))
    hn = min(1.0, max(EPS, hn))

    return BBoxXYWHNorm(x=xn, y=yn, w=wn, h=hn)


def xyxy_to_xywh(b: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
    """Convert pixel-space `xyxy` → pixel TL-`xywh` (no clamping)."""
    x1, y1, x2, y2 = b
    return (x1, y1, x2 - x1, y2 - y1)


def xywh_to_xyxy(b: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
    """Convert pixel TL-`xywh` → pixel-space `xyxy` (no clamping)."""
    x, y, w, h = b
    return (x, y, x + w, y + h)
