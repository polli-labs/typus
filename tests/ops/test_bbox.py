import math

import pytest

from typus.models.geometry import BBoxXYWHNorm, to_xyxy_px
from typus.ops import (
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


def test_iou_xyxy_basic_cases():
    a = (0.0, 0.0, 10.0, 10.0)

    # No overlap
    b = (20.0, 20.0, 30.0, 30.0)
    assert iou_xyxy(a, b) == 0.0

    # Edge-touching => no overlap
    b = (10.0, 0.0, 20.0, 10.0)
    assert iou_xyxy(a, b) == 0.0

    # Partial overlap
    b = (5.0, 5.0, 15.0, 15.0)
    # inter area = 5*5 = 25; union = 100 + 100 - 25 = 175
    assert math.isclose(iou_xyxy(a, b), 25.0 / 175.0)

    # Containment
    b_small = (2.0, 2.0, 8.0, 8.0)  # area 36
    assert math.isclose(iou_xyxy(a, b_small), 36.0 / 100.0)

    # Identical
    assert iou_xyxy(a, a) == 1.0


def test_intersect_xyxy():
    a = (0.0, 0.0, 10.0, 10.0)
    b = (5.0, 5.0, 15.0, 15.0)
    assert intersect_xyxy(a, b) == (5.0, 5.0, 10.0, 10.0)

    # Disjoint
    b = (20.0, 20.0, 30.0, 30.0)
    assert intersect_xyxy(a, b) is None

    # Edge-touching
    b = (10.0, 0.0, 20.0, 10.0)
    assert intersect_xyxy(a, b) is None


def test_union_xyxy():
    a = (0.0, 0.0, 10.0, 10.0)

    # Overlapping
    b = (5.0, 5.0, 15.0, 15.0)
    assert union_xyxy(a, b) == (0.0, 0.0, 15.0, 15.0)

    # Disjoint => enclosing rectangle, never None
    b = (20.0, 20.0, 30.0, 30.0)
    assert union_xyxy(a, b) == (0.0, 0.0, 30.0, 30.0)

    # Containment
    b_small = (2.0, 2.0, 8.0, 8.0)
    assert union_xyxy(a, b_small) == a

    # Identical
    assert union_xyxy(a, a) == a

    # Degenerate (zero-area) box still contributes its coordinates
    point = (12.0, 3.0, 12.0, 3.0)
    assert union_xyxy(a, point) == (0.0, 0.0, 12.0, 10.0)

    # More than two boxes
    assert union_xyxy(a, b, b_small) == (0.0, 0.0, 30.0, 30.0)

    # Single box is its own union
    assert union_xyxy(a) == a


def test_union_xyxy_empty_raises():
    with pytest.raises(ValueError, match="at least one box"):
        union_xyxy()


def test_clamp_xyxy():
    # Clamp negatives and overflows
    clamped = clamp_xyxy((-5.0, -5.0, 12.0, 14.0), 10, 12)
    assert clamped == (0.0, 0.0, 10.0, 12.0)

    # Preserve ordering when inputs inverted
    clamped2 = clamp_xyxy((10.0, 10.0, 5.0, 5.0), 20, 20)
    assert clamped2 == (5.0, 5.0, 10.0, 10.0)


def test_area_xyxy():
    assert area_xyxy((0.0, 0.0, 10.0, 10.0)) == 100.0


def test_xyxy_xywh_converters():
    xyxy = (10.0, 20.0, 40.0, 60.0)
    xywh = xyxy_to_xywh(xyxy)
    assert xywh == (10.0, 20.0, 30.0, 40.0)
    assert xywh_to_xyxy(xywh) == xyxy


def test_xywh_px_roundtrip_and_consistency():
    W, H = 640, 480
    b = BBoxXYWHNorm(x=0.1, y=0.2, w=0.3, h=0.4)

    # Round trip via xywh px
    x, y, w, h = to_xywh_px(b, W, H)
    b_rt = from_xywh_px(x, y, w, h, W, H)
    assert math.isclose(b.x, b_rt.x, rel_tol=0, abs_tol=1e-9)
    assert math.isclose(b.y, b_rt.y, rel_tol=0, abs_tol=1e-9)
    assert math.isclose(b.w, b_rt.w, rel_tol=0, abs_tol=1e-9)
    assert math.isclose(b.h, b_rt.h, rel_tol=0, abs_tol=1e-9)

    # Consistency with existing xyxy converters
    xyxy_direct = to_xyxy_px(b, W, H)
    xyxy_via_rt = to_xyxy_px(b_rt, W, H)
    assert xyxy_direct == xyxy_via_rt


def test_union_xyxy_does_not_reorder_inverted_input() -> None:
    """Pins the non-repairing posture: an inverted box is passed through, not fixed.

    `clamp_xyxy` deliberately re-orders inverted input; the pure math ops do not.
    If someone later adds "helpful" reordering here, this test makes that a
    deliberate semantic change rather than a silent one.
    """
    assert union_xyxy((10.0, 10.0, 0.0, 0.0)) == (10.0, 10.0, 0.0, 0.0)
