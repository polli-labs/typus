from typing import List
from pydantic import Field, ConfigDict
from ..serialise import CompactJsonMixin
from .geometry import BBox, EncodedMask
from .classification import HierarchicalClassificationResult, TaxonomyContext

class InstancePrediction(CompactJsonMixin):
    instance_id: int = Field(ge=0)
    bbox: BBox
    mask: EncodedMask | None = None
    score: float = Field(gt=0, le=1)

    # Labelling
    taxon_id: int | None = None
    classification: HierarchicalClassificationResult | None = None

    model_config = ConfigDict(frozen=True, json_schema_extra=True)

class ImageDetectionResult(CompactJsonMixin):
    width: int
    height: int
    instances: List[InstancePrediction]
    taxonomy_context: TaxonomyContext | None = None

    model_config = ConfigDict(json_schema_extra=True)
