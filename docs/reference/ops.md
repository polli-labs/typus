# Ops Helpers

Lightweight utilities for common geometry and tracking operations. These are
pure-Python helpers with no heavy dependencies and are designed to complement
the canonical geometry in `typus.models.geometry` and the tracking models in
`typus.models.tracks`.

## Bounding Boxes (`typus.ops.bbox`)

- `iou_xyxy(a, b) -> float` – IoU for pixel `xyxy` boxes. Returns `0.0` when
  boxes are disjoint or just touching.
- `area_xyxy(b) -> float` – Area in pixel^2; clamps negative extents to `0`.
- `intersect_xyxy(a, b) -> tuple | None` – Intersection `xyxy` or `None` if no overlap.
- `clamp_xyxy(b, W, H) -> tuple` – Clamp to `[0,W] × [0,H]`, preserving ordering.
- `to_xywh_px(bbox_norm, W, H) -> tuple` – Convert normalized TL‑`xywh` to pixel TL‑`xywh`.
- `from_xywh_px(x, y, w, h, W, H) -> BBoxXYWHNorm` – Convert pixel TL‑`xywh` to normalized.
- `xyxy_to_xywh((x1,y1,x2,y2)) -> (x, y, w, h)` – Pixel‑space conversion.
- `xywh_to_xyxy((x,y,w,h)) -> (x1, y1, x2, y2)` – Pixel‑space conversion.

Example:

```python
from typus.models.geometry import BBoxXYWHNorm
from typus.ops import iou_xyxy, to_xywh_px, from_xywh_px

b = BBoxXYWHNorm(x=0.1, y=0.2, w=0.3, h=0.4)
xywh_px = to_xywh_px(b, 640, 480)  # (64.0, 96.0, 192.0, 192.0)
b2 = from_xywh_px(*xywh_px, 640, 480)
assert b2 == b

IoU = iou_xyxy((0,0,10,10), (5,5,15,15))
```

## Tracking (`typus.ops.tracks`)

- `group_detections_by_frame(dets) -> dict[int, list[Detection]]` – Group by
  `frame_number` with sorted keys; per‑frame order preserved.
- `detection_xyxy_px(det, W, H) -> tuple` – Pixel `xyxy` for a `Detection`.
  Prefers canonical `bbox_norm`; falls back to legacy pixel `bbox` when present.

Example:

```python
from typus.models.geometry import BBoxXYWHNorm
from typus.models.tracks import Detection
from typus.ops import detection_xyxy_px, group_detections_by_frame

d = Detection(frame_number=10, bbox_norm=BBoxXYWHNorm(x=0.1,y=0.2,w=0.4,h=0.5), confidence=0.9)
xyxy = detection_xyxy_px(d, 1920, 1080)

grouped = group_detections_by_frame([d])
```

## Design Principles

- No heavy deps (no numpy in core helpers).
- Return tuples for simple geometry to keep the surface area minimal.
- Canonical model geometry is normalized TL‑`xywh`.
- Pixel helpers are convenience utilities; they mirror semantics of
  `typus.models.geometry` converters.
