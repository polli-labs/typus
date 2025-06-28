import enum
from typing import List, Tuple

from pydantic import ConfigDict

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
