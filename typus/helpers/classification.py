from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from typus.models.classification import (
    AdjustmentReason,
    CalibrationMethod,
    CalibrationProvenance,
    CandidateRef,
    ClassificationCandidate,
    ClassificationResult,
    DecisionOutcome,
    DecisionPolicy,
    DecisionPolicyKind,
    DecisionScoreSemantics,
    OutcomeAdjustment,
    RankBelief,
    RankNullCandidate,
    RankNullCandidateMatch,
    ResidualBelowTaxonCandidate,
    ResidualBelowTaxonCandidateMatch,
    ScoreSemantics,
    TaxonCandidate,
    TaxonCandidateMatch,
    TaxonSnapshot,
)

_PROBABILITY_SEMANTICS = {
    ScoreSemantics.RANK_SOFTMAX_PROBABILITY,
    ScoreSemantics.TEMPERATURE_SCALED_RANK_PROBABILITY,
    ScoreSemantics.CALIBRATED_RANK_PROBABILITY,
}


@dataclass
class LineageNode:
    rank_level: int
    rank_name: str
    taxon_id: int
    score: float
    score_semantics: ScoreSemantics
    taxon_snapshot: TaxonSnapshot | None = None


@dataclass
class TreeNode:
    kind: str
    rank_level: int
    rank_name: str
    score: float
    score_semantics: ScoreSemantics
    taxon_id: int | None = None
    parent_taxon_id: int | None = None
    taxon_snapshot: TaxonSnapshot | None = None
    children: list["TreeNode"] = field(default_factory=list)


def derive_lineage(result: ClassificationResult) -> list[LineageNode]:
    outcome_by_rank = {outcome.rank_level: outcome for outcome in result.outcomes or []}
    lineage = []
    for rank in sorted(result.ranks, key=lambda item: item.rank_level, reverse=True):
        candidate = None
        outcome = outcome_by_rank.get(rank.rank_level)
        if outcome is not None and outcome.decision == "commit" and outcome.resolved_to is not None:
            candidate = _taxon_candidate_for_ref(rank, outcome.resolved_to)
        elif outcome is None:
            candidate = _top_taxon_candidate(rank)

        if candidate is not None:
            lineage.append(
                LineageNode(
                    rank_level=candidate.rank_level,
                    rank_name=candidate.rank_name,
                    taxon_id=candidate.taxon_id,
                    score=candidate.score,
                    score_semantics=candidate.score_semantics,
                    taxon_snapshot=candidate.taxon_snapshot,
                )
            )
    return lineage


def derive_tree(result: ClassificationResult) -> list[TreeNode]:
    nodes_by_taxon: dict[int, TreeNode] = {}
    roots: list[TreeNode] = []
    pending_children: dict[int, list[TreeNode]] = {}

    for rank in result.ranks:
        for candidate in rank.candidates:
            node = _candidate_to_tree_node(candidate)
            if isinstance(candidate, TaxonCandidate):
                nodes_by_taxon[candidate.taxon_id] = node
                node.children.extend(pending_children.pop(candidate.taxon_id, []))
                parent_id = candidate.parent_taxon_id
            elif isinstance(candidate, ResidualBelowTaxonCandidate):
                parent_id = candidate.parent_taxon_id
            else:
                parent_id = None

            if parent_id is not None:
                parent = nodes_by_taxon.get(parent_id)
                if parent is None:
                    pending_children.setdefault(parent_id, []).append(node)
                else:
                    parent.children.append(node)
            else:
                roots.append(node)

    for orphaned in pending_children.values():
        roots.extend(orphaned)
    return roots


def apply_argmax(result: ClassificationResult) -> ClassificationResult:
    updated, policy = _append_policy(result, DecisionPolicyKind.ARGMAX)
    outcomes = []
    for rank in updated.ranks:
        candidate = _top_taxon_candidate(rank) or _top_candidate(rank)
        decision = "commit" if isinstance(candidate, TaxonCandidate) else "abstain"
        reason = (
            AdjustmentReason.COMMIT_TOP_CANDIDATE
            if isinstance(candidate, TaxonCandidate)
            else AdjustmentReason.ABSTAIN_MODEL_NATURAL
        )
        outcomes.append(
            _outcome(
                rank=rank,
                candidate=candidate,
                policy_id=policy.id,
                decision=decision,
                reason=reason,
                decision_score=candidate.score,
                decision_score_semantics=DecisionScoreSemantics.SELECTED_CANDIDATE_SCORE,
            )
        )
    updated.outcomes = outcomes
    return _validate(updated)


def apply_chow_threshold(
    result: ClassificationResult, taus: dict[int, float]
) -> ClassificationResult:
    updated, policy = _append_policy(
        result,
        DecisionPolicyKind.MAX_PROBABILITY_THRESHOLD,
        parameters={"tau_by_rank": taus},
    )
    outcomes = []
    for rank in updated.ranks:
        candidate, probability = _top_probability_candidate(rank)
        tau = taus.get(rank.rank_level, 0.0)
        margin = probability - tau
        if isinstance(candidate, TaxonCandidate) and probability > tau:
            decision = "commit"
            reason = AdjustmentReason.COMMIT_THRESHOLDED
        elif probability > tau:
            decision = "abstain"
            reason = AdjustmentReason.ABSTAIN_MODEL_NATURAL
        else:
            decision = "abstain"
            reason = AdjustmentReason.ABSTAIN_THRESHOLD_NOT_MET
        outcomes.append(
            _outcome(
                rank=rank,
                candidate=candidate,
                policy_id=policy.id,
                decision=decision,
                reason=reason,
                decision_score=margin,
                decision_score_semantics=DecisionScoreSemantics.THRESHOLD_MARGIN,
            )
        )
    updated.outcomes = outcomes
    return _validate(updated)


def apply_hierarchy_repair(
    result: ClassificationResult,
    taxonomy_tree: Any,
) -> ClassificationResult:
    updated, policy = _append_policy(result, DecisionPolicyKind.HIERARCHY_REPAIR)

    outcomes_by_rank: dict[int, DecisionOutcome] = {}
    committed_parent_id: int | None = None
    committed_parent_rank: int | None = None
    parent_abstained = False

    for rank in sorted(updated.ranks, key=lambda item: item.rank_level, reverse=True):
        natural = _top_candidate(rank)
        applied = natural
        suppressed_from: ClassificationCandidate | None = None

        if parent_abstained:
            applied = _rank_null_candidate(rank) or natural
            suppressed_from = natural if applied is not natural else None
            decision = "abstain"
            reason = AdjustmentReason.ABSTAIN_PARENT_ABSTAINED
        elif isinstance(natural, TaxonCandidate):
            if committed_parent_id is None or _is_descendant_of(
                natural,
                parent_id=committed_parent_id,
                parent_rank_level=committed_parent_rank,
                taxonomy_tree=taxonomy_tree,
            ):
                decision = "commit"
                reason = AdjustmentReason.COMMIT_TOP_CANDIDATE
                committed_parent_id = natural.taxon_id
                committed_parent_rank = natural.rank_level
            else:
                descendant = _top_descendant_candidate(
                    rank,
                    parent_id=committed_parent_id,
                    parent_rank_level=committed_parent_rank,
                    taxonomy_tree=taxonomy_tree,
                )
                if descendant is not None:
                    applied = descendant
                    suppressed_from = natural
                    decision = "commit"
                    reason = AdjustmentReason.COMMIT_AFTER_REPAIR
                    committed_parent_id = descendant.taxon_id
                    committed_parent_rank = descendant.rank_level
                else:
                    applied = _rank_null_candidate(rank) or natural
                    suppressed_from = natural if applied is not natural else None
                    decision = "abstain"
                    reason = AdjustmentReason.ABSTAIN_HIERARCHY_CONFLICT
                    parent_abstained = True
        else:
            decision = "abstain"
            reason = AdjustmentReason.ABSTAIN_MODEL_NATURAL
            parent_abstained = True

        outcomes_by_rank[rank.rank_level] = _outcome(
            rank=rank,
            candidate=applied,
            policy_id=policy.id,
            decision=decision,
            reason=reason,
            suppressed_from=suppressed_from,
            decision_score=applied.score,
            decision_score_semantics=DecisionScoreSemantics.SELECTED_CANDIDATE_SCORE,
        )

    updated.outcomes = [outcomes_by_rank[rank.rank_level] for rank in updated.ranks]
    return _validate(updated)


def apply_temperature_scaling(result: ClassificationResult, T: float) -> ClassificationResult:
    if T <= 0:
        raise ValueError("T must be > 0")

    updated = result.model_copy(deep=True)
    updated.provenance.calibration = CalibrationProvenance(
        method=CalibrationMethod.TEMPERATURE_SCALING,
        parameters={"T": T},
    )
    for rank in updated.ranks:
        scaled_scores = _temperature_scale_scores(
            [candidate.score for candidate in rank.candidates], T
        )
        for candidate, scaled_score in zip(rank.candidates, scaled_scores):
            candidate.score = scaled_score
            candidate.score_semantics = ScoreSemantics.TEMPERATURE_SCALED_RANK_PROBABILITY
    return _validate(updated)


def apply_conformal_calibration(
    result: ClassificationResult,
    calibration_set_id: str,
    target_coverage: float,
) -> ClassificationResult:
    raise NotImplementedError(
        "TODO(POL-980): conformal calibration requires a calibrated nonconformity "
        "score implementation before Typus can rewrite candidate sets. "
        f"Received calibration_set_id={calibration_set_id!r}, "
        f"target_coverage={target_coverage!r}."
    )


def as_probability(candidate: ClassificationCandidate) -> float | None:
    if candidate.score_semantics in _PROBABILITY_SEMANTICS:
        return candidate.score
    return None


def _append_policy(
    result: ClassificationResult,
    kind: DecisionPolicyKind,
    *,
    parameters: dict[str, Any] | None = None,
) -> tuple[ClassificationResult, DecisionPolicy]:
    updated = result.model_copy(deep=True)
    policy = DecisionPolicy(
        id=f"p{len(updated.provenance.decision_policies)}",
        kind=kind,
        parameters=parameters,
        chain_order=len(updated.provenance.decision_policies),
    )
    updated.provenance.decision_policies = [*updated.provenance.decision_policies, policy]
    return updated, policy


def _candidate_to_tree_node(candidate: ClassificationCandidate) -> TreeNode:
    if isinstance(candidate, TaxonCandidate):
        return TreeNode(
            kind=candidate.kind,
            rank_level=candidate.rank_level,
            rank_name=candidate.rank_name,
            score=candidate.score,
            score_semantics=candidate.score_semantics,
            taxon_id=candidate.taxon_id,
            parent_taxon_id=candidate.parent_taxon_id,
            taxon_snapshot=candidate.taxon_snapshot,
        )
    if isinstance(candidate, ResidualBelowTaxonCandidate):
        return TreeNode(
            kind=candidate.kind,
            rank_level=candidate.rank_level,
            rank_name=candidate.rank_name,
            score=candidate.score,
            score_semantics=candidate.score_semantics,
            parent_taxon_id=candidate.parent_taxon_id,
        )
    return TreeNode(
        kind=candidate.kind,
        rank_level=candidate.rank_level,
        rank_name=candidate.rank_name,
        score=candidate.score,
        score_semantics=candidate.score_semantics,
    )


def _candidate_ref(candidate: ClassificationCandidate) -> CandidateRef:
    if isinstance(candidate, TaxonCandidate):
        match = TaxonCandidateMatch(taxon_id=candidate.taxon_id)
    elif isinstance(candidate, RankNullCandidate):
        match = RankNullCandidateMatch()
    else:
        match = ResidualBelowTaxonCandidateMatch(parent_taxon_id=candidate.parent_taxon_id)
    return CandidateRef(rank_level=candidate.rank_level, match=match)


def _outcome(
    *,
    rank: RankBelief,
    candidate: ClassificationCandidate,
    policy_id: str,
    decision: Literal["commit", "abstain"],
    reason: AdjustmentReason,
    suppressed_from: ClassificationCandidate | None = None,
    decision_score: float | None = None,
    decision_score_semantics: DecisionScoreSemantics | None = None,
) -> DecisionOutcome:
    candidate_ref = _candidate_ref(candidate)
    return DecisionOutcome(
        rank_level=rank.rank_level,
        decision=decision,
        resolved_to=candidate_ref,
        decision_score=decision_score,
        decision_score_semantics=decision_score_semantics,
        derived_from_policy_id=policy_id,
        adjustment=OutcomeAdjustment(
            reason=reason,
            applied_candidate=candidate_ref,
            suppressed_from=_candidate_ref(suppressed_from)
            if suppressed_from is not None
            else None,
        ),
    )


def _rank_null_candidate(rank: RankBelief) -> RankNullCandidate | None:
    for candidate in rank.candidates:
        if isinstance(candidate, RankNullCandidate):
            return candidate
    return None


def _top_candidate(rank: RankBelief) -> ClassificationCandidate:
    return max(rank.candidates, key=lambda candidate: candidate.score)


def _top_taxon_candidate(rank: RankBelief) -> TaxonCandidate | None:
    taxon_candidates = [
        candidate for candidate in rank.candidates if isinstance(candidate, TaxonCandidate)
    ]
    if not taxon_candidates:
        return None
    return max(taxon_candidates, key=lambda candidate: candidate.score)


def _top_probability_candidate(rank: RankBelief) -> tuple[ClassificationCandidate, float]:
    probability_candidates = [
        (candidate, probability)
        for candidate in rank.candidates
        if (probability := as_probability(candidate)) is not None
    ]
    if not probability_candidates:
        raise ValueError(f"rank {rank.rank_level} has no probability-bearing candidates")
    return max(probability_candidates, key=lambda item: item[1])


def _taxon_candidate_for_ref(rank: RankBelief, ref: CandidateRef) -> TaxonCandidate | None:
    if not isinstance(ref.match, TaxonCandidateMatch):
        return None
    for candidate in rank.candidates:
        if isinstance(candidate, TaxonCandidate) and candidate.taxon_id == ref.match.taxon_id:
            return candidate
    return None


def _top_descendant_candidate(
    rank: RankBelief,
    *,
    parent_id: int,
    parent_rank_level: int | None,
    taxonomy_tree: Any,
) -> TaxonCandidate | None:
    descendants = [
        candidate
        for candidate in rank.candidates
        if isinstance(candidate, TaxonCandidate)
        and _is_descendant_of(
            candidate,
            parent_id=parent_id,
            parent_rank_level=parent_rank_level,
            taxonomy_tree=taxonomy_tree,
        )
    ]
    if not descendants:
        return None
    return max(descendants, key=lambda candidate: candidate.score)


def _is_descendant_of(
    candidate: TaxonCandidate,
    *,
    parent_id: int,
    parent_rank_level: int | None,
    taxonomy_tree: Any,
) -> bool:
    if candidate.parent_taxon_id == parent_id:
        return True
    if candidate.ancestor_taxon_ids_by_rank is not None:
        if parent_id in candidate.ancestor_taxon_ids_by_rank.values():
            return True
        if (
            parent_rank_level is not None
            and candidate.ancestor_taxon_ids_by_rank.get(parent_rank_level) == parent_id
        ):
            return True
    if candidate.taxon_snapshot is not None:
        if parent_id in candidate.taxon_snapshot.ancestor_taxon_ids_by_rank.values():
            return True
    if hasattr(taxonomy_tree, "is_descendant"):
        try:
            return bool(taxonomy_tree.is_descendant(candidate.taxon_id, parent_id))
        except TypeError:
            pass
    if isinstance(taxonomy_tree, Mapping):
        return _mapping_contains_parent(taxonomy_tree, candidate.taxon_id, parent_id)
    return False


def _mapping_contains_parent(
    taxonomy_tree: Mapping[Any, Any],
    taxon_id: int,
    parent_id: int,
) -> bool:
    current = taxon_id
    seen: set[int] = set()
    while current not in seen:
        seen.add(current)
        parent = taxonomy_tree.get(current)
        if parent == parent_id:
            return True
        if parent is None:
            return False
        if not isinstance(parent, int):
            return False
        current = parent
    return False


def _temperature_scale_scores(scores: list[float], T: float) -> list[float]:
    positive_scores = [max(score, 0.0) for score in scores]
    if not positive_scores or sum(positive_scores) == 0:
        return positive_scores
    scaled = [math.pow(score, 1.0 / T) if score > 0 else 0.0 for score in positive_scores]
    denominator = sum(scaled)
    if denominator == 0:
        return scaled
    return [score / denominator for score in scaled]


def _validate(result: ClassificationResult) -> ClassificationResult:
    return ClassificationResult.model_validate(result.model_dump(mode="python"))
