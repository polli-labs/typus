from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Tuple

from typus.models.geometry import BBoxXYWHNorm, to_xyxy_px
from typus.models.tracks import Detection


def group_detections_by_frame(dets: Iterable[Detection]) -> Dict[int, List[Detection]]:
    """Group detections by `frame_number` preserving per-frame order.

    Returns a dict with integer keys sorted in ascending order.
    """
    tmp: Dict[int, List[Detection]] = defaultdict(list)
    for d in dets:
        # Detection.frame_number is required by the model; be robust to unexpected None
        if d is None:  # type: ignore[unreachable]
            continue
        fn = int(getattr(d, "frame_number", 0))
        tmp[fn].append(d)

    return dict(sorted(tmp.items(), key=lambda kv: kv[0]))


def detection_xyxy_px(det: Detection, W: int, H: int) -> Tuple[float, float, float, float]:
    """Return pixel `xyxy` tuple for a `Detection` using image dimensions.

    Prefers the canonical `bbox_norm` if present. If only the legacy `bbox`
    (pixel `xywh`) is provided, falls back to converting that to `xyxy`.
    """
    if isinstance(det.bbox_norm, BBoxXYWHNorm):
        return tuple(to_xyxy_px(det.bbox_norm, W, H))  # type: ignore[return-value]

    if det.bbox and len(det.bbox) == 4:
        x, y, w, h = det.bbox
        return (x, y, x + w, y + h)

    raise ValueError("Detection has neither bbox_norm nor legacy bbox")
