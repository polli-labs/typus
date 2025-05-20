from typus.constants import RankLevel
from typus.models.classification import (
    HierarchicalClassificationResult,
    TaskPrediction,
    TaxonomyContext,
)


def test_serialise_roundtrip():
    tp = TaskPrediction(
        rank_level=RankLevel.L40, temperature=0.7, predictions=[(123, 0.9), (456, 0.1)]
    )
    res = HierarchicalClassificationResult(
        taxonomy_context=TaxonomyContext(), tasks=[tp], subtree_roots={123}
    )
    js = res.to_json(indent=None)
    back = HierarchicalClassificationResult.model_validate_json(js)
    assert back == res
