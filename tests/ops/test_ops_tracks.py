from __future__ import annotations

from typus.models.geometry import BBoxXYWHNorm, to_xyxy_px
from typus.models.tracks import Detection
from typus.ops import detection_xyxy_px, group_detections_by_frame


def _det(frame: int, x: float, y: float, w: float, h: float, conf: float) -> Detection:
    return Detection(
        frame_number=frame,
        bbox_norm=BBoxXYWHNorm(x=x, y=y, w=w, h=h),
        confidence=conf,
    )


def test_group_detections_by_frame_unsorted_input_preserves_order_and_sorting():
    dets = [
        _det(2, 0.1, 0.1, 0.2, 0.2, 0.9),
        _det(1, 0.2, 0.2, 0.2, 0.2, 0.8),
        _det(2, 0.3, 0.3, 0.2, 0.2, 0.7),
        _det(1, 0.4, 0.4, 0.2, 0.2, 0.6),
        _det(3, 0.5, 0.5, 0.2, 0.2, 0.5),
    ]

    grouped = group_detections_by_frame(dets)
    assert list(grouped.keys()) == [1, 2, 3]
    # Per-frame order preserved
    assert grouped[1][0] is dets[1]
    assert grouped[1][1] is dets[3]
    assert grouped[2][0] is dets[0]
    assert grouped[2][1] is dets[2]
    assert grouped[3][0] is dets[4]


def test_detection_xyxy_px_matches_geometry_converter():
    W, H = 1920, 1080
    d = _det(10, 0.1, 0.2, 0.4, 0.5, 0.95)

    xyxy_from_ops = detection_xyxy_px(d, W, H)
    xyxy_from_geom = to_xyxy_px(d.bbox_norm, W, H)  # type: ignore[arg-type]
    assert tuple(xyxy_from_geom) == xyxy_from_ops


def test_detection_xyxy_px_legacy_bbox_fallback():
    # Detection with only legacy pixel bbox (xywh)
    d = Detection(frame_number=5, bbox=[10, 20, 30, 40], confidence=0.7)
    assert detection_xyxy_px(d, 100, 100) == (10, 20, 40, 60)
