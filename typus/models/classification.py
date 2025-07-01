from __future__ import annotations

from typing import List, Set, Tuple

from pydantic import Field, field_validator

from ..constants import RankLevel
from .serialise import CompactJsonMixin


class TaskPrediction(CompactJsonMixin):
    """Top‑k probabilities for one rank level."""

    rank_level: RankLevel
    temperature: float = Field(gt=0)
    predictions: List[Tuple[int, float]]  # (taxon_id, p)

    @field_validator("predictions")
    def _prob_sum(cls, v):
        if sum(p for _, p in v) > 1.0 + 1e-6:
            raise ValueError("probabilities sum > 1")
        return v


class TaxonomyContext(CompactJsonMixin):
    source: str = "CoL2024"
    version: str | None = None


class HierarchicalClassificationResult(CompactJsonMixin):
    taxonomy_context: TaxonomyContext
    tasks: List[TaskPrediction]
    subtree_roots: Set[int] | None = None
