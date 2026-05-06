import pytest
from pydantic import ValidationError

from typus.constants import RankLevel
from typus.helpers.classification import (
    apply_argmax,
    apply_chow_threshold,
    apply_hierarchy_repair,
    apply_temperature_scaling,
    as_probability,
    derive_lineage,
)
from typus.models.classification import (
    AdjustmentReason,
    AggregationStage,
    AttributionGranularity,
    CandidateRef,
    ClassificationConsistency,
    ClassificationInputContext,
    ClassificationProvenance,
    ClassificationResult,
    ClassificationSourceKind,
    DecisionOutcome,
    DecisionPolicy,
    DecisionPolicyKind,
    EvidenceShape,
    HierarchicalClassificationResult,
    InputAggregation,
    InputAttribution,
    OutcomeAdjustment,
    RankBelief,
    RankNullCandidate,
    ResidualBelowTaxonCandidate,
    ResidualBelowTaxonCandidateMatch,
    ScoreSemantics,
    TaskPrediction,
    TaxonCandidate,
    TaxonomyContext,
)


def test_serialise_roundtrip():
    with pytest.warns(DeprecationWarning):
        tp = TaskPrediction(
            rank_level=RankLevel.L40,
            temperature=0.7,
            predictions=[(123, 0.9), (456, 0.1)],
        )
    with pytest.warns(DeprecationWarning):
        res = HierarchicalClassificationResult(
            taxonomy_context=TaxonomyContext(), tasks=[tp], subtree_roots={123}
        )
    js = res.to_json(indent=None)
    back = HierarchicalClassificationResult.model_validate_json(js)
    assert back == res


def test_hierarchical_classification_result_converter():
    tp = TaskPrediction(
        rank_level=RankLevel.L30,
        temperature=1.0,
        predictions=[(300, 0.8), (301, 0.2)],
    )
    res = HierarchicalClassificationResult(
        taxonomy_context=TaxonomyContext(null_taxon_ids_by_rank={30: -30}),
        tasks=[tp],
    )

    canonical = res.to_classification_result()

    assert canonical.provenance.source_kind is ClassificationSourceKind.MODEL_INFERENCE
    assert canonical.provenance.decision_policies == []
    assert canonical.outcomes is None
    assert canonical.ranks[0].candidates[0].score_semantics is (
        ScoreSemantics.RANK_SOFTMAX_PROBABILITY
    )


def test_discriminated_candidate_union_roundtrip():
    result = _raw_result(
        [
            TaxonCandidate(
                rank_level=30,
                rank_name="family",
                score=0.6,
                score_semantics=ScoreSemantics.RANK_SOFTMAX_PROBABILITY,
                taxon_id=300,
            ),
            RankNullCandidate(
                rank_level=30,
                rank_name="family",
                score=0.3,
                score_semantics=ScoreSemantics.RANK_SOFTMAX_PROBABILITY,
                null_taxon_id=-30,
            ),
            ResidualBelowTaxonCandidate(
                rank_level=30,
                rank_name="family",
                score=0.1,
                score_semantics=ScoreSemantics.RANK_SOFTMAX_PROBABILITY,
                parent_taxon_id=400,
                target_rank_level=30,
            ),
        ]
    )

    back = ClassificationResult.model_validate_json(result.to_json())

    assert isinstance(back.ranks[0].candidates[0], TaxonCandidate)
    assert isinstance(back.ranks[0].candidates[1], RankNullCandidate)
    assert isinstance(back.ranks[0].candidates[2], ResidualBelowTaxonCandidate)


def test_outcomes_required_when_decision_policies_exist():
    result = _raw_result([_taxon(300, 0.8), _null(0.2)])
    payload = result.model_dump(mode="python")
    payload["provenance"]["decision_policies"] = [
        DecisionPolicy(id="p0", kind=DecisionPolicyKind.ARGMAX, chain_order=0)
    ]

    with pytest.raises(ValidationError, match="outcomes must be present"):
        ClassificationResult.model_validate(payload)


def test_outcome_rank_order_must_match_ranks():
    result = apply_argmax(_raw_result([_taxon(300, 0.8), _null(0.2)]))
    payload = result.model_dump(mode="python")
    payload["outcomes"][0]["rank_level"] = 20

    with pytest.raises(ValidationError, match="outcomes rank order"):
        ClassificationResult.model_validate(payload)


def test_outcome_policy_id_must_resolve():
    result = apply_argmax(_raw_result([_taxon(300, 0.8), _null(0.2)]))
    payload = result.model_dump(mode="python")
    payload["outcomes"][0]["derived_from_policy_id"] = "missing"

    with pytest.raises(ValidationError, match="derived_from_policy_id"):
        ClassificationResult.model_validate(payload)


def test_outcome_refs_must_resolve():
    result = apply_argmax(_raw_result([_taxon(300, 0.8), _null(0.2)]))
    payload = result.model_dump(mode="python")
    payload["outcomes"][0]["adjustment"]["applied_candidate"]["match"]["taxon_id"] = 999

    with pytest.raises(ValidationError, match="applied_candidate"):
        ClassificationResult.model_validate(payload)


def test_curated_cards_reject_probability_semantics():
    payload = _raw_result([_taxon(300, 1.0)]).model_dump(mode="python")
    payload["provenance"]["source_kind"] = ClassificationSourceKind.CURATED_TAXON_CARD
    payload["input_context"]["entity_type"] = "card"
    payload["input_context"]["evidence_shape"] = EvidenceShape.AUTHORED_CARD

    with pytest.raises(ValidationError, match="curated_taxon_card"):
        ClassificationResult.model_validate(payload)


def test_as_probability_is_semantics_gated():
    probability_candidate = _taxon(300, 0.8)
    authored_candidate = TaxonCandidate(
        rank_level=30,
        rank_name="family",
        score=1.0,
        score_semantics=ScoreSemantics.AUTHORED_ASSERTION_WEIGHT,
        taxon_id=300,
    )

    assert as_probability(probability_candidate) == 0.8
    assert as_probability(authored_candidate) is None


def test_decision_helpers_emit_valid_outcomes():
    raw = ClassificationResult(
        taxonomy_context=TaxonomyContext(null_taxon_ids_by_rank={40: -40, 30: -30}),
        provenance=ClassificationProvenance(
            source_kind=ClassificationSourceKind.MODEL_INFERENCE,
            producer="linnaeus@test",
            decision_policies=[],
        ),
        input_context=_input_context(),
        consistency=ClassificationConsistency(hierarchy_checked=False, is_consistent=True),
        ranks=[
            RankBelief(
                rank_level=40, rank_name="order", candidates=[_taxon(400, 0.9, 40), _null(0.1, 40)]
            ),
            RankBelief(
                rank_level=30,
                rank_name="family",
                candidates=[
                    _taxon(301, 0.7, 30, parent_taxon_id=401),
                    _taxon(300, 0.6, 30, parent_taxon_id=400),
                    _null(0.1, 30),
                ],
            ),
        ],
    )

    scaled = apply_temperature_scaling(raw, T=2.0)
    assert all(
        candidate.score_semantics is ScoreSemantics.TEMPERATURE_SCALED_RANK_PROBABILITY
        for rank in scaled.ranks
        for candidate in rank.candidates
    )

    chow = apply_chow_threshold(scaled, {40: 0.5, 30: 0.5})
    assert chow.outcomes is not None
    assert chow.outcomes[0].adjustment.reason is AdjustmentReason.COMMIT_THRESHOLDED

    repaired = apply_hierarchy_repair(raw, taxonomy_tree={300: 400, 301: 401})
    assert repaired.outcomes is not None
    assert repaired.outcomes[1].adjustment.reason is AdjustmentReason.COMMIT_AFTER_REPAIR
    assert derive_lineage(repaired)[-1].taxon_id == 300


def test_ref_to_residual_candidate_resolves():
    residual = ResidualBelowTaxonCandidate(
        rank_level=10,
        rank_name="species",
        score=0.4,
        score_semantics=ScoreSemantics.CONFORMAL_SET_MEMBERSHIP,
        parent_taxon_id=200,
        target_rank_level=10,
    )
    result = ClassificationResult(
        taxonomy_context=TaxonomyContext(null_taxon_ids_by_rank={10: -10}),
        provenance=ClassificationProvenance(
            source_kind=ClassificationSourceKind.MODEL_INFERENCE,
            producer="linnaeus@test",
            decision_policies=[],
        ),
        input_context=_input_context(),
        consistency=ClassificationConsistency(hierarchy_checked=False, is_consistent=True),
        ranks=[RankBelief(rank_level=10, rank_name="species", candidates=[residual])],
        outcomes=None,
    )
    payload = result.model_dump(mode="python")
    payload["provenance"]["decision_policies"] = [
        DecisionPolicy(
            id="p0",
            kind=DecisionPolicyKind.CONFORMAL_FRONTIER,
            chain_order=0,
        )
    ]
    payload["outcomes"] = [
        DecisionOutcome(
            rank_level=10,
            decision="abstain",
            resolved_to=CandidateRef(
                rank_level=10,
                match=ResidualBelowTaxonCandidateMatch(parent_taxon_id=200),
            ),
            derived_from_policy_id="p0",
            adjustment=OutcomeAdjustment(
                reason=AdjustmentReason.ABSTAIN_CONFORMAL_SET_OPEN,
                applied_candidate=CandidateRef(
                    rank_level=10,
                    match=ResidualBelowTaxonCandidateMatch(parent_taxon_id=200),
                ),
            ),
        )
    ]

    assert ClassificationResult.model_validate(payload).outcomes is not None


def _raw_result(candidates):
    return ClassificationResult(
        taxonomy_context=TaxonomyContext(null_taxon_ids_by_rank={30: -30}),
        provenance=ClassificationProvenance(
            source_kind=ClassificationSourceKind.MODEL_INFERENCE,
            producer="linnaeus@test",
            decision_policies=[],
        ),
        input_context=_input_context(),
        consistency=ClassificationConsistency(hierarchy_checked=False, is_consistent=True),
        ranks=[RankBelief(rank_level=30, rank_name="family", candidates=candidates)],
        outcomes=None,
    )


def _input_context():
    return ClassificationInputContext(
        entity_type="image",
        evidence_shape=EvidenceShape.SINGLE_IMAGE,
        unit_count=1,
        aggregation=InputAggregation(stage=AggregationStage.NONE),
        attribution=InputAttribution(granularity=AttributionGranularity.NONE),
    )


def _taxon(taxon_id, score, rank_level=30, parent_taxon_id=None):
    return TaxonCandidate(
        rank_level=rank_level,
        rank_name="family" if rank_level == 30 else "order",
        score=score,
        score_semantics=ScoreSemantics.RANK_SOFTMAX_PROBABILITY,
        taxon_id=taxon_id,
        parent_taxon_id=parent_taxon_id,
        ancestor_taxon_ids_by_rank={40: parent_taxon_id} if parent_taxon_id is not None else None,
    )


def _null(score, rank_level=30):
    return RankNullCandidate(
        rank_level=rank_level,
        rank_name="family" if rank_level == 30 else "order",
        score=score,
        score_semantics=ScoreSemantics.RANK_SOFTMAX_PROBABILITY,
        null_taxon_id=-rank_level,
    )
