"""Compare v0 expected-utility cost profiles on pilot-derived smoke beliefs.

The iNat pilot does not contain Linnaeus logits, so this is not a model eval.
It builds deterministic synthetic calibrated beliefs from each record's
expert-consensus depth and supported-rank lineage, then reports whether each
profile stops at the same model-supported safe depth.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from typus.helpers.classification import cost_matrix_v0_profiles, expected_utility_policy
from typus.models.classification import (
    AggregationStage,
    AttributionGranularity,
    CalibrationMethod,
    CalibrationProvenance,
    ClassificationConsistency,
    ClassificationInputContext,
    ClassificationProvenance,
    ClassificationResult,
    ClassificationSourceKind,
    EvidenceShape,
    InputAggregation,
    InputAttribution,
    RankBelief,
    RankNullCandidate,
    ScoreSemantics,
    TaxonCandidate,
    TaxonomyContext,
)

MODEL_RANKS = [40, 30, 20, 10]
RANK_NAMES = {40: "order", 30: "family", 20: "genus", 10: "species"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pilot-jsonl",
        type=Path,
        default=Path(
            "/Users/carbon/dev/ibrida/dev/tools/inat_identification_history/output/"
            "pilot_n200_v1.jsonl"
        ),
    )
    args = parser.parse_args()

    records = _read_jsonl(args.pilot_jsonl)
    print(
        "profile,records,comparable,depth_match_rate,overcommit_rate,"
        "undercommit_rate,null_records,terminal_depths"
    )
    for profile_name, cost_matrix in cost_matrix_v0_profiles().items():
        comparable = 0
        matches = 0
        overcommits = 0
        undercommits = 0
        null_records = 0
        terminal_depths: Counter[str] = Counter()
        for record in records:
            expected_rank = _safe_model_rank(record.get("expert_consensus_depth"))
            result = expected_utility_policy(_pilot_belief(record), cost_matrix)
            terminal_rank = _terminal_rank(result)
            terminal_depths[str(terminal_rank)] += 1
            if expected_rank is None:
                null_records += 1
                continue
            comparable += 1
            if terminal_rank == expected_rank:
                matches += 1
            elif terminal_rank is not None and terminal_rank < expected_rank:
                overcommits += 1
            else:
                undercommits += 1

        print(
            ",".join(
                [
                    profile_name,
                    str(len(records)),
                    str(comparable),
                    _rate(matches, comparable),
                    _rate(overcommits, comparable),
                    _rate(undercommits, comparable),
                    str(null_records),
                    json.dumps(dict(sorted(terminal_depths.items()))),
                ]
            )
        )
    print()
    print("boundary_profile,target_rank,min_true_probability,wrong_branch_probability")
    for profile_name in cost_matrix_v0_profiles():
        for target_rank in [20, 10]:
            print(
                ",".join(
                    [
                        profile_name,
                        str(target_rank),
                        _first_commit_probability(profile_name, target_rank),
                        "0.08",
                    ]
                )
            )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


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
        ranks.append(_rank_belief(rank_level, taxon_id, lineage, true_score, wrong_score))
    return _classification_result(ranks)


def _boundary_belief(target_rank: int, target_score: float) -> ClassificationResult:
    lineage = {
        40: 4000,
        30: 3000,
        20: 2000,
        10: 1000,
    }
    ranks = []
    for rank_level in MODEL_RANKS:
        if rank_level > target_rank:
            true_score, wrong_score = _safe_rank_scores(rank_level)
            taxon_id = lineage[rank_level]
        elif rank_level == target_rank:
            true_score, wrong_score = target_score, 0.08
            taxon_id = lineage[rank_level]
        else:
            true_score, wrong_score = _overclaim_rank_scores(rank_level)
            taxon_id = _synthetic_child_taxon_id(lineage, rank_level)
        ranks.append(_rank_belief(rank_level, taxon_id, lineage, true_score, wrong_score))
    return _classification_result(ranks)


def _first_commit_probability(profile_name: str, target_rank: int) -> str:
    cost_matrix = cost_matrix_v0_profiles()[profile_name]
    for probability_step in range(5, 93):
        probability = probability_step / 100
        result = expected_utility_policy(_boundary_belief(target_rank, probability), cost_matrix)
        if _terminal_rank(result) == target_rank:
            return f"{probability:.2f}"
    return "none"


def _classification_result(ranks: list[RankBelief]) -> ClassificationResult:
    return ClassificationResult(
        taxonomy_context=TaxonomyContext(
            null_taxon_ids_by_rank={rank: -rank for rank in MODEL_RANKS}
        ),
        provenance=ClassificationProvenance(
            source_kind=ClassificationSourceKind.MODEL_INFERENCE,
            producer="scripts.compare_cost_sensitive_policy_profiles",
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
                taxon_id=taxon_id + 900000,
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
    for signal in record.get("trusted_identifier_signals", []):
        lineage = {
            int(node["rank_level"]): int(node["taxon_id"])
            for node in signal.get("suggested_lineage", [])
            if int(node["rank_level"]) in MODEL_RANKS
        }
        if lineage:
            return lineage
    return {}


def _safe_model_rank(expert_depth: Any) -> int | None:
    if expert_depth is None:
        return None
    depth = int(expert_depth)
    safe_ranks = [rank for rank in MODEL_RANKS if rank >= depth]
    if not safe_ranks:
        return None
    return min(safe_ranks)


def _terminal_rank(result: ClassificationResult) -> int | None:
    if result.outcomes is None:
        return None
    committed = [outcome.rank_level for outcome in result.outcomes if outcome.decision == "commit"]
    if not committed:
        return None
    return min(committed)


def _rate(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "nan"
    return f"{numerator / denominator:.3f}"


if __name__ == "__main__":
    main()
