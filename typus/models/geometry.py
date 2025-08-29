from __future__ import annotations

import enum
import math
from typing import Callable, Dict, List, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .serialise import CompactJsonMixin


class BBoxFormat(str, enum.Enum):
    XYXY_REL = "xyxyRel"
    XYXY_ABS = "xyxyAbs"
    CXCYWH_REL = "cxcywhRel"
    CXCYWH_ABS = "cxcywhAbs"


class MaskEncoding(str, enum.Enum):
    RLE_COCO = "rleCoco"
    POLYGON = "polygon"
    PNG_BASE64 = "pngBase64"


class BBox(CompactJsonMixin):
    coords: Tuple[float, float, float, float]
    fmt: BBoxFormat = BBoxFormat.XYXY_REL
    model_config = ConfigDict(frozen=True)


class EncodedMask(CompactJsonMixin):
    data: str | List[List[float]]
    encoding: MaskEncoding
    bbox_hint: BBox | None = None
    model_config = ConfigDict(frozen=True)


# Canonical geometry types for v0.3.0+
EPS = 1e-9


def _round_half_up(x: float) -> int:
    """Round to nearest integer with ties away from zero.

    For non-negative inputs (our case), this is equivalent to ties-away-from-zero
    as documented in the geometry contract.
    """
    return int(math.floor(x + 0.5))


class BBoxXYWHNorm(BaseModel):
    """Canonical TL-normalized bbox: [x, y, w, h] with invariants."""

    x: float = Field(ge=0.0, le=1.0, description="Left coordinate (0-1, normalized)")
    y: float = Field(ge=0.0, le=1.0, description="Top coordinate (0-1, normalized)")
    w: float = Field(gt=0.0, le=1.0, description="Width (0-1, normalized)")
    h: float = Field(gt=0.0, le=1.0, description="Height (0-1, normalized)")

    model_config = ConfigDict(frozen=True)

    @field_validator("x", "y", "w", "h")
    @classmethod
    def _finite(cls, v: float) -> float:
        if v != v or v in (float("inf"), float("-inf")):
            raise ValueError("non-finite coordinate")
        return v

    @model_validator(mode="after")
    def _validate_bounds(self) -> "BBoxXYWHNorm":
        """Validate that bbox stays within [0,1] bounds."""
        if self.x + self.w > 1.0 + EPS:
            raise ValueError("x + w exceeds 1")
        if self.y + self.h > 1.0 + EPS:
            raise ValueError("y + h exceeds 1")
        return self


def to_xyxy_px(b: BBoxXYWHNorm, W: int, H: int) -> Tuple[int, int, int, int]:
    """Convert canonical bbox to pixel XYXY coordinates."""
    x1 = _round_half_up(b.x * W)
    y1 = _round_half_up(b.y * H)
    x2 = _round_half_up((b.x + b.w) * W)
    y2 = _round_half_up((b.y + b.h) * H)
    return x1, y1, x2, y2


def from_xyxy_px(x1: float, y1: float, x2: float, y2: float, W: int, H: int) -> BBoxXYWHNorm:
    """Convert pixel XYXY coordinates to canonical bbox."""
    if x2 <= x1 or y2 <= y1:
        raise ValueError("xyxy invalid: x2<=x1 or y2<=y1")
    x = max(0.0, x1 / W)
    y = max(0.0, y1 / H)
    w = (x2 - x1) / W
    h = (y2 - y1) / H

    # Clamp to [0,1] to avoid pathological float precision cases
    x = min(1.0, max(0.0, x))
    y = min(1.0, max(0.0, y))
    w = min(1.0, max(EPS, w))
    h = min(1.0, max(EPS, h))

    return BBoxXYWHNorm(x=x, y=y, w=w, h=h)


class BBoxMapper:
    """Registry for provider-specific bbox mapping functions."""

    _REG: Dict[str, Callable[..., BBoxXYWHNorm]] = {}

    @classmethod
    def register(cls, name: str, fn: Callable[..., BBoxXYWHNorm], *, replace: bool = False) -> None:
        """Register a bbox mapping function.

        Args:
            name: Provider name identifier
            fn: Mapping function that returns BBoxXYWHNorm
            replace: If True, allows overwriting existing mappings

        Raises:
            KeyError: If name already exists and replace=False
        """
        if name in cls._REG and not replace:
            raise KeyError(f"Bbox mapper '{name}' already exists; pass replace=True to overwrite")
        cls._REG[name] = fn

    @classmethod
    def get(cls, name: str) -> Callable[..., BBoxXYWHNorm]:
        """Get a registered bbox mapping function."""
        if name not in cls._REG:
            raise KeyError(f"No bbox mapper registered for '{name}'")
        return cls._REG[name]

    @classmethod
    def list_providers(cls) -> List[str]:
        """List all registered provider names."""
        return list(cls._REG.keys())


def _gemini_br_xyxy_to_norm(
    x1_br: float, y1_br: float, x2_br: float, y2_br: float, W: int, H: int
) -> BBoxXYWHNorm:
    """Convert Gemini bottom-right origin XYXY to canonical TL-normalized XYWH.

    Gemini uses bottom-right origin where (0,0) is at bottom-right corner.
    We convert to top-left pixel coordinates then normalize.

    Args:
        x1_br, y1_br, x2_br, y2_br: Bottom-right origin pixel coordinates
        W, H: Image dimensions in pixels

    Returns:
        Canonical top-left normalized XYWH bbox
    """
    # Convert BR-origin coords to TL-origin pixel xyxy
    # BR origin means (0,0) at bottom-right; TL pixel coords are:
    tl_x1 = W - x2_br
    tl_y1 = H - y2_br
    tl_x2 = W - x1_br
    tl_y2 = H - y1_br
    return from_xyxy_px(tl_x1, tl_y1, tl_x2, tl_y2, W, H)


# Register the Gemini BR->TL mapper
BBoxMapper.register("gemini_br_xyxy", _gemini_br_xyxy_to_norm)


def infer_from_raw(
    raw: Sequence[float] | dict, upload_w: int, upload_h: int, *, prefer: str = "tl_xywh_norm"
) -> BBoxXYWHNorm:
    """Infer canonical bbox from raw data with strict validation.

    Only accepts obviously canonical TL-normalized xywh without provider hints.
    For ambiguous formats, explicit provider mapping must be used.

    Args:
        raw: Raw bbox data (list/tuple of 4 floats or dict)
        upload_w, upload_h: Image dimensions (currently unused but kept for API consistency)
        prefer: Preferred format hint (currently unused)

    Returns:
        Canonical BBoxXYWHNorm

    Raises:
        ValueError: If bbox format is ambiguous or invalid
    """
    if isinstance(raw, (list, tuple)) and len(raw) == 4:
        x, y, w, h = raw
        try:
            return BBoxXYWHNorm(x=x, y=y, w=w, h=h)
        except Exception:
            pass
    raise ValueError("Ambiguous bbox; specify provider or pass canonical TL-normalized xywh")
