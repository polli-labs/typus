from typing import List

from pydantic import ConfigDict, Field

from .classification import HierarchicalClassificationResult, TaxonomyContext
from .geometry import BBox, EncodedMask
from .serialise import CompactJsonMixin


class InstancePrediction(CompactJsonMixin):
    instance_id: int = Field(ge=0)
    bbox: BBox
    mask: EncodedMask | None = None
    score: float = Field(gt=0, le=1)

    # Labelling
    taxon_id: int | None = None
    classification: HierarchicalClassificationResult | None = None

    model_config = ConfigDict(frozen=True)


class ImageDetectionResult(CompactJsonMixin):
    width: int
    height: int
    instances: List[InstancePrediction]
    taxonomy_context: TaxonomyContext | None = None
