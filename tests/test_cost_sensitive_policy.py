import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from typus.helpers.classification import (
    cost_matrix_v0_balanced,
    cost_matrix_v0_profiles,
    expected_utility_policy,
)
from typus.models.classification import (
    AdjustmentReason,
    AggregationStage,
    AttributionGranularity,
    CalibrationMethod,
    CalibrationProvenance,
    ClassificationConsistency,
    ClassificationInputContext,
    ClassificationProvenance,
    ClassificationResult,
    ClassificationSourceKind,
    DecisionPolicyKind,
    DecisionScoreSemantics,
    EvidenceShape,
    InputAggregation,
    InputAttribution,
    RankBelief,
    RankNullCandidate,
    ScoreSemantics,
    TaxonCandidate,
    TaxonomyContext,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "classification"
SCHEMA_PATH = Path(__file__).parents[1] / "typus" / "schemas" / "ClassificationResult.json"
PILOT_SUBSET_PATH = FIXTURE_DIR / "pilot_n200_v1_subset.jsonl"
MODEL_RANKS = [40, 30, 20, 10]
RANK_NAMES = {40: "order", 30: "family", 20: "genus", 10: "species"}


def test_expected_utility_policy_round_trips_against_schema():
    result = expected_utility_policy(_synthetic_belief(species_probability=0.86))
    serialized = json.loads(result.to_json(indent=2))

    Draft202012Validator(json.loads(SCHEMA_PATH.read_text())).validate(serialized)
    assert ClassificationResult.model_validate_json(json.dumps(serialized)) == result
    assert result.provenance.decision_policies[-1].kind is (
        DecisionPolicyKind.COST_SENSITIVE_POLICY
    )
    assert result.provenance.decision_policies[-1].parameters is not None
    assert (
        result.provenance.decision_policies[-1].parameters["cost_matrix"]["profile_name"]
        == "v0_balanced"
    )
    assert result.outcomes is not None
    assert result.outcomes[-1].decision == "commit"
    assert result.outcomes[-1].adjustment.reason is AdjustmentReason.COMMIT_EXPECTED_UTILITY
    assert result.outcomes[-1].decision_score_semantics is (
        DecisionScoreSemantics.POLICY_CONFIDENCE
    )


def test_expected_utility_policy_commits_species_when_evidence_is_strong():
    result = expected_utility_policy(_synthetic_belief(species_probability=0.86))

    assert _terminal_rank(result) == 10
    assert result.outcomes is not None
    assert [outcome.decision for outcome in result.outcomes] == [
        "commit",
        "commit",
        "commit",
        "commit",
    ]


def test_expected_utility_policy_stops_at_genus_when_species_overclaim_risk_is_high():
    result = expected_utility_policy(_synthetic_belief(species_probability=0.46))

    assert _terminal_rank(result) == 20
    assert result.outcomes is not None
    assert result.outcomes[-2].decision == "commit"
    assert result.outcomes[-1].decision == "abstain"
    assert result.outcomes[-1].adjustment.reason is AdjustmentReason.ABSTAIN_EXPECTED_UTILITY


def test_pilot_subset_depth_match_is_reasonable_for_balanced_profile():
    records = _pilot_records()
    matches = 0
    comparable = 0
    overcommits = 0

    for record in records:
        expected_rank = _safe_model_rank(record.get("expert_consensus_depth"))
        result = expected_utility_policy(_pilot_belief(record), cost_matrix_v0_balanced())
        terminal_rank = _terminal_rank(result)
        if expected_rank is None:
            assert terminal_rank is None
            continue
        comparable += 1
        if terminal_rank == expected_rank:
            matches += 1
        if terminal_rank is not None and terminal_rank < expected_rank:
            overcommits += 1

    assert comparable == 9
    assert matches / comparable >= 0.8
    assert overcommits == 0


def test_v0_profiles_make_conservatism_order_explicit():
    profiles = cost_matrix_v0_profiles()
    assert list(profiles) == ["v0_conservative", "v0_balanced", "v0_aggressive"]
    species = 10
    assert profiles["v0_conservative"].overclaim_cost(species) > profiles[
        "v0_balanced"
    ].overclaim_cost(species)
    assert profiles["v0_aggressive"].overclaim_cost(species) < profiles[
        "v0_balanced"
    ].overclaim_cost(species)


def _synthetic_belief(species_probability: float) -> ClassificationResult:
    lineage = {
        40: 4000,
        30: 3000,
        20: 2000,
        10: 1000,
    }
    scores_by_rank = {
        40: (0.95, 0.03),
        30: (0.92, 0.04),
        20: (0.88, 0.05),
        10: (species_probability, 0.08),
    }
    ranks = [
        _rank_belief(
            rank_level,
            lineage[rank_level],
            lineage,
            true_score,
            wrong_score,
        )
        for rank_level, (true_score, wrong_score) in scores_by_rank.items()
    ]
    return _classification_result(ranks)


def _pilot_belief(record: dict[str, Any]) -> ClassificationResult:
    expected_rank = _safe_model_rank(record.get("expert_consensus_depth"))
    lineage = _record_lineage(record)
    ranks = []
    for rank_level in MODEL_RANKS:
        if expected_rank is None or rank_level not in lineage:
            ranks.append(_null_only_rank(rank_level))
            continue

        if rank_level >= expected_rank:
            true_score, wrong_score = _safe_rank_scores(rank_level)
            taxon_id = lineage[rank_level]
        else:
            true_score, wrong_score = _overclaim_rank_scores(rank_level)
            taxon_id = _synthetic_child_taxon_id(lineage, rank_level)

        ranks.append(
            _rank_belief(
                rank_level,
                taxon_id,
                lineage,
                true_score,
                wrong_score,
            )
        )
    return _classification_result(ranks)


def _classification_result(ranks: list[RankBelief]) -> ClassificationResult:
    return ClassificationResult(
        taxonomy_context=TaxonomyContext(
            null_taxon_ids_by_rank={rank: -rank for rank in MODEL_RANKS}
        ),
        provenance=ClassificationProvenance(
            source_kind=ClassificationSourceKind.MODEL_INFERENCE,
            producer="typus@test",
            calibration=CalibrationProvenance(
                method=CalibrationMethod.TEMPERATURE_SCALING,
                parameters={"T": 1.0},
            ),
            decision_policies=[],
        ),
        input_context=ClassificationInputContext(
            entity_type="image",
            evidence_shape=EvidenceShape.SINGLE_IMAGE,
            unit_count=1,
            aggregation=InputAggregation(stage=AggregationStage.NONE),
            attribution=InputAttribution(granularity=AttributionGranularity.NONE),
        ),
        consistency=ClassificationConsistency(hierarchy_checked=False, is_consistent=True),
        ranks=ranks,
        outcomes=None,
    )


def _rank_belief(
    rank_level: int,
    taxon_id: int,
    lineage: dict[int, int],
    true_score: float,
    wrong_score: float,
) -> RankBelief:
    null_score = max(1.0 - true_score - wrong_score, 0.0)
    rank_name = RANK_NAMES[rank_level]
    parent_taxon_id = _parent_taxon_id(lineage, rank_level)
    ancestors = {
        ancestor_rank: ancestor_taxon_id
        for ancestor_rank, ancestor_taxon_id in lineage.items()
        if ancestor_rank > rank_level
    }
    wrong_taxon_id = taxon_id + 900000
    return RankBelief(
        rank_level=rank_level,
        rank_name=rank_name,
        candidates=[
            TaxonCandidate(
                rank_level=rank_level,
                rank_name=rank_name,
                score=true_score,
                score_semantics=ScoreSemantics.TEMPERATURE_SCALED_RANK_PROBABILITY,
                taxon_id=taxon_id,
                parent_taxon_id=parent_taxon_id,
                ancestor_taxon_ids_by_rank=ancestors or None,
            ),
            TaxonCandidate(
                rank_level=rank_level,
                rank_name=rank_name,
                score=wrong_score,
                score_semantics=ScoreSemantics.TEMPERATURE_SCALED_RANK_PROBABILITY,
                taxon_id=wrong_taxon_id,
                parent_taxon_id=parent_taxon_id,
                ancestor_taxon_ids_by_rank=ancestors or None,
            ),
            RankNullCandidate(
                rank_level=rank_level,
                rank_name=rank_name,
                score=null_score,
                score_semantics=ScoreSemantics.TEMPERATURE_SCALED_RANK_PROBABILITY,
                null_taxon_id=-rank_level,
            ),
        ],
    )


def _null_only_rank(rank_level: int) -> RankBelief:
    rank_name = RANK_NAMES[rank_level]
    return RankBelief(
        rank_level=rank_level,
        rank_name=rank_name,
        candidates=[
            RankNullCandidate(
                rank_level=rank_level,
                rank_name=rank_name,
                score=1.0,
                score_semantics=ScoreSemantics.TEMPERATURE_SCALED_RANK_PROBABILITY,
                null_taxon_id=-rank_level,
            )
        ],
    )


def _safe_rank_scores(rank_level: int) -> tuple[float, float]:
    if rank_level == 10:
        return 0.74, 0.08
    if rank_level == 20:
        return 0.78, 0.06
    if rank_level == 30:
        return 0.9, 0.04
    return 0.96, 0.02


def _overclaim_rank_scores(rank_level: int) -> tuple[float, float]:
    if rank_level == 10:
        return 0.38, 0.12
    if rank_level == 20:
        return 0.4, 0.12
    return 0.42, 0.1


def _parent_taxon_id(lineage: dict[int, int], rank_level: int) -> int | None:
    parent_ranks = [rank for rank in MODEL_RANKS if rank > rank_level and rank in lineage]
    if parent_ranks:
        return lineage[min(parent_ranks)]
    return None


def _synthetic_child_taxon_id(lineage: dict[int, int], rank_level: int) -> int:
    parent_id = _parent_taxon_id(lineage, rank_level)
    if parent_id is None:
        return 800000 + rank_level
    return parent_id * 10 + rank_level


def _record_lineage(record: dict[str, Any]) -> dict[int, int]:
    signals = record.get("trusted_identifier_signals", [])
    if not signals:
        return {}
    lineage_nodes = signals[0].get("suggested_lineage", [])
    return {
        int(node["rank_level"]): int(node["taxon_id"])
        for node in lineage_nodes
        if int(node["rank_level"]) in MODEL_RANKS
    }


def _safe_model_rank(expert_depth: Any) -> int | None:
    if expert_depth is None:
        return None
    depth = int(expert_depth)
    safe_ranks = [rank for rank in MODEL_RANKS if rank >= depth]
    if not safe_ranks:
        return None
    return min(safe_ranks)


def _terminal_rank(result: ClassificationResult) -> int | None:
    assert result.outcomes is not None
    committed = [outcome.rank_level for outcome in result.outcomes if outcome.decision == "commit"]
    if not committed:
        return None
    return min(committed)


def _pilot_records() -> list[dict[str, Any]]:
    return [json.loads(line) for line in PILOT_SUBSET_PATH.read_text().splitlines() if line.strip()]
