# Ops Helpers

Lightweight utilities for common geometry operations. These are
pure-Python helpers — importing `typus.ops` pulls in no dependency beyond
pydantic (no sqlalchemy, rapidfuzz, or DB driver) — and are designed to complement
the canonical geometry in `typus.models.geometry`.

## Bounding Boxes (`typus.ops.bbox`)

- `iou_xyxy(a, b) -> float` – IoU for pixel `xyxy` boxes. Returns `0.0` when
  boxes are disjoint or just touching.
- `area_xyxy(b) -> float` – Area in pixel^2; clamps negative extents to `0`.
- `intersect_xyxy(a, b) -> tuple | None` – Intersection `xyxy` or `None` if no overlap.
- `union_xyxy(*boxes) -> tuple` – Smallest `xyxy` enclosing one or more boxes. A
  union always exists, so unlike `intersect_xyxy` this never returns `None`;
  raises `ValueError` when called with no boxes.
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

## Design Principles

- No heavy deps: no numpy, and `import typus.ops` does not load sqlalchemy,
  rapidfuzz, or any DB driver (enforced by `tests/test_import_purity.py`).
- Return tuples for simple geometry to keep the surface area minimal.
- Canonical model geometry is normalized TL‑`xywh`.
- Pixel helpers are convenience utilities; they mirror semantics of
  `typus.models.geometry` converters.
