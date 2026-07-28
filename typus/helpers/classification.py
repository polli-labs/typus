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

_MODEL_RANK_DEPTHS = {
    40: 1.0,  # order
    30: 2.0,  # family
    20: 3.0,  # genus
    10: 4.0,  # species
}

_PHASE_D_RANK_WEIGHTS = {
    40: 0.5,
    30: 1.0,
    20: 2.0,
    10: 3.0,
}

SpecificityRewardShape = Literal["linear", "sqrt", "log"]


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


@dataclass(frozen=True)
class _UtilityCandidate:
    candidate: TaxonCandidate
    utility: float


@dataclass(frozen=True)
class TaxonomyCostMatrix:
    """Serializable v0 cost profile for hierarchy-aware Bayes-risk decisions.

    Rank depth is intentionally a configurable domain proxy rather than a raw
    graph edge count. The default model-rank depths are linear for the current
    order/family/genus/species heads, but minor ranks can be interpolated
    between them when callers provide subrank candidates.
    """

    profile_name: str
    specificity_reward_shape: SpecificityRewardShape = "sqrt"
    specificity_reward_scale: float = 1.0
    overclaim_cost_weight: float = 5.0
    wrong_branch_cost_weight: float = 1.0
    wrong_branch_exponent: float = 1.35
    rank_depths: Mapping[int, float] = field(default_factory=lambda: dict(_MODEL_RANK_DEPTHS))
    rank_weights: Mapping[int, float] = field(default_factory=lambda: dict(_PHASE_D_RANK_WEIGHTS))
    min_commit_utility: float = 0.0
    abstain_utility: float = 0.0

    def specificity_reward(self, rank_level: int) -> float:
        depth = self.rank_depth(rank_level)
        max_depth = self.max_rank_depth()
        if max_depth <= 0:
            return 0.0
        depth_fraction = max(depth / max_depth, 0.0)
        if self.specificity_reward_shape == "linear":
            shaped = depth_fraction
        elif self.specificity_reward_shape == "sqrt":
            shaped = math.sqrt(depth_fraction)
        else:
            shaped = math.log1p(depth) / math.log1p(max_depth)
        return self.specificity_reward_scale * self.rank_weight(rank_level) * shaped

    def overclaim_cost(self, rank_level: int) -> float:
        max_depth = self.max_rank_depth()
        if max_depth <= 0:
            return 0.0
        depth_fraction = max(self.rank_depth(rank_level) / max_depth, 0.0)
        return self.overclaim_cost_weight * depth_fraction

    def wrong_branch_cost(self, committed: TaxonCandidate, true_candidate: TaxonCandidate) -> float:
        if committed.taxon_id == true_candidate.taxon_id:
            return 0.0

        committed_lineage = _lineage_taxa_by_rank(committed)
        true_lineage = _lineage_taxa_by_rank(true_candidate)
        if committed.taxon_id in true_lineage.values():
            return 0.0
        if true_candidate.taxon_id in committed_lineage.values():
            return self.overclaim_cost(committed.rank_level)

        lca_depth = _lowest_common_ancestor_depth(
            committed_lineage,
            true_lineage,
            self,
        )
        deepest_compared = max(
            self.rank_depth(committed.rank_level),
            self.rank_depth(true_candidate.rank_level),
        )
        separation = max(deepest_compared - lca_depth, 0.0)
        return self.wrong_branch_cost_weight * (
            1.0 + math.pow(separation, self.wrong_branch_exponent)
        )

    def rank_depth(self, rank_level: int) -> float:
        if rank_level in self.rank_depths:
            return self.rank_depths[rank_level]

        known_levels = sorted(self.rank_depths)
        if not known_levels:
            return 1.0

        coarser_levels = [level for level in known_levels if level > rank_level]
        deeper_levels = [level for level in known_levels if level < rank_level]
        if coarser_levels and deeper_levels:
            coarser = min(coarser_levels)
            deeper = max(deeper_levels)
            span = coarser - deeper
            if span == 0:
                return self.rank_depths[coarser]
            fraction = (coarser - rank_level) / span
            return self.rank_depths[coarser] + fraction * (
                self.rank_depths[deeper] - self.rank_depths[coarser]
            )
        if coarser_levels:
            return max(self.rank_depths[min(coarser_levels)] - 1.0, 0.0)
        return self.rank_depths[max(deeper_levels)] + 1.0

    def max_rank_depth(self) -> float:
        if not self.rank_depths:
            return 1.0
        return max(self.rank_depths.values())

    def rank_weight(self, rank_level: int) -> float:
        if rank_level in self.rank_weights:
            return self.rank_weights[rank_level]
        return max(self.rank_depth(rank_level) / self.max_rank_depth(), 0.0)

    def to_policy_parameters(self) -> dict[str, Any]:
        return {
            "profile_name": self.profile_name,
            "specificity_reward_shape": self.specificity_reward_shape,
            "specificity_reward_scale": self.specificity_reward_scale,
            "overclaim_cost_weight": self.overclaim_cost_weight,
            "wrong_branch_cost_weight": self.wrong_branch_cost_weight,
            "wrong_branch_exponent": self.wrong_branch_exponent,
            "rank_depths": {str(rank): depth for rank, depth in self.rank_depths.items()},
            "rank_weights": {str(rank): weight for rank, weight in self.rank_weights.items()},
            "min_commit_utility": self.min_commit_utility,
            "abstain_utility": self.abstain_utility,
        }


def cost_matrix_v0_balanced() -> TaxonomyCostMatrix:
    return TaxonomyCostMatrix(profile_name="v0_balanced")


def cost_matrix_v0_conservative() -> TaxonomyCostMatrix:
    return TaxonomyCostMatrix(
        profile_name="v0_conservative",
        specificity_reward_shape="log",
        overclaim_cost_weight=7.5,
        wrong_branch_cost_weight=1.25,
        wrong_branch_exponent=1.5,
    )


def cost_matrix_v0_aggressive() -> TaxonomyCostMatrix:
    return TaxonomyCostMatrix(
        profile_name="v0_aggressive",
        specificity_reward_shape="linear",
        overclaim_cost_weight=3.0,
        wrong_branch_cost_weight=0.75,
        wrong_branch_exponent=1.15,
    )


def cost_matrix_v0_profiles() -> dict[str, TaxonomyCostMatrix]:
    profiles = [
        cost_matrix_v0_conservative(),
        cost_matrix_v0_balanced(),
        cost_matrix_v0_aggressive(),
    ]
    return {profile.profile_name: profile for profile in profiles}


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


def expected_utility_policy(
    result: ClassificationResult,
    costs: TaxonomyCostMatrix | None = None,
) -> ClassificationResult:
    """Apply the hierarchy-aware v0 expected-utility decision policy.

    The policy greedily walks from coarse to fine ranks. At each rank it picks
    the taxon candidate with the highest expected utility against the rank-local
    posterior, commits only when that utility beats abstention, and forces
    deeper commits to remain descendants of the previously committed parent.
    """

    matrix = costs or cost_matrix_v0_balanced()
    updated, policy = _append_policy(
        result,
        DecisionPolicyKind.COST_SENSITIVE_POLICY,
        parameters={
            "algorithm": "greedy_hierarchy_frontier",
            "selection_rule": "commit_when_expected_utility_exceeds_abstain",
            "cost_matrix": matrix.to_policy_parameters(),
        },
    )

    outcomes_by_rank: dict[int, DecisionOutcome] = {}
    committed_parent_id: int | None = None
    committed_parent_rank: int | None = None
    parent_abstained = False

    for rank in sorted(updated.ranks, key=lambda item: item.rank_level, reverse=True):
        utilities = _expected_utility_candidates(rank, matrix)
        natural = _best_utility_candidate(utilities)
        applied: ClassificationCandidate
        suppressed_from: ClassificationCandidate | None = None

        if natural is None:
            applied = _abstain_candidate(rank)
            decision = "abstain"
            reason = AdjustmentReason.ABSTAIN_MODEL_NATURAL
            decision_score = None
            parent_abstained = True
        elif parent_abstained:
            applied = _abstain_candidate(rank, fallback=natural.candidate)
            suppressed_from = natural.candidate if applied is not natural.candidate else None
            decision = "abstain"
            reason = AdjustmentReason.ABSTAIN_PARENT_ABSTAINED
            decision_score = natural.utility - matrix.abstain_utility
        elif committed_parent_id is not None and not _is_descendant_of(
            natural.candidate,
            parent_id=committed_parent_id,
            parent_rank_level=committed_parent_rank,
            taxonomy_tree={},
        ):
            descendant = _best_descendant_utility_candidate(
                utilities,
                parent_id=committed_parent_id,
                parent_rank_level=committed_parent_rank,
            )
            if descendant is not None and descendant.utility > matrix.min_commit_utility:
                applied = descendant.candidate
                suppressed_from = natural.candidate
                decision = "commit"
                reason = AdjustmentReason.COMMIT_AFTER_REPAIR
                decision_score = descendant.utility - matrix.abstain_utility
                committed_parent_id = descendant.candidate.taxon_id
                committed_parent_rank = descendant.candidate.rank_level
            else:
                applied = _abstain_candidate(rank, fallback=natural.candidate)
                suppressed_from = natural.candidate if applied is not natural.candidate else None
                decision = "abstain"
                reason = AdjustmentReason.ABSTAIN_HIERARCHY_CONFLICT
                decision_score = natural.utility - matrix.abstain_utility
                parent_abstained = True
        elif natural.utility > matrix.min_commit_utility:
            applied = natural.candidate
            decision = "commit"
            reason = AdjustmentReason.COMMIT_EXPECTED_UTILITY
            decision_score = natural.utility - matrix.abstain_utility
            committed_parent_id = natural.candidate.taxon_id
            committed_parent_rank = natural.candidate.rank_level
        else:
            applied = _abstain_candidate(rank, fallback=natural.candidate)
            suppressed_from = natural.candidate if applied is not natural.candidate else None
            decision = "abstain"
            reason = AdjustmentReason.ABSTAIN_EXPECTED_UTILITY
            decision_score = natural.utility - matrix.abstain_utility
            parent_abstained = True

        outcomes_by_rank[rank.rank_level] = _outcome(
            rank=rank,
            candidate=applied,
            policy_id=policy.id,
            decision=decision,
            reason=reason,
            suppressed_from=suppressed_from,
            decision_score=decision_score,
            decision_score_semantics=DecisionScoreSemantics.POLICY_CONFIDENCE
            if decision_score is not None
            else None,
        )

    updated.outcomes = [outcomes_by_rank[rank.rank_level] for rank in updated.ranks]
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


def _expected_utility_candidates(
    rank: RankBelief,
    matrix: TaxonomyCostMatrix,
) -> list[_UtilityCandidate]:
    probability_candidates = [
        (candidate, probability)
        for candidate in rank.candidates
        if (probability := as_probability(candidate)) is not None
    ]
    if not probability_candidates:
        raise ValueError(f"rank {rank.rank_level} has no probability-bearing candidates")

    missing_probability = max(
        1.0 - sum(probability for _, probability in probability_candidates),
        0.0,
    )
    utilities: list[_UtilityCandidate] = []
    for committed, committed_probability in probability_candidates:
        if not isinstance(committed, TaxonCandidate):
            continue

        utility = committed_probability * matrix.specificity_reward(committed.rank_level)
        utility -= missing_probability * matrix.overclaim_cost(committed.rank_level)
        for true_candidate, true_probability in probability_candidates:
            if true_candidate is committed:
                continue
            if isinstance(true_candidate, TaxonCandidate):
                utility -= true_probability * matrix.wrong_branch_cost(
                    committed,
                    true_candidate,
                )
            else:
                utility -= true_probability * matrix.overclaim_cost(committed.rank_level)
        utilities.append(_UtilityCandidate(candidate=committed, utility=utility))
    return utilities


def _best_utility_candidate(
    utilities: list[_UtilityCandidate],
) -> _UtilityCandidate | None:
    if not utilities:
        return None
    return max(utilities, key=lambda item: (item.utility, item.candidate.score))


def _best_descendant_utility_candidate(
    utilities: list[_UtilityCandidate],
    *,
    parent_id: int,
    parent_rank_level: int | None,
) -> _UtilityCandidate | None:
    descendants = [
        item
        for item in utilities
        if _is_descendant_of(
            item.candidate,
            parent_id=parent_id,
            parent_rank_level=parent_rank_level,
            taxonomy_tree={},
        )
    ]
    return _best_utility_candidate(descendants)


def _abstain_candidate(
    rank: RankBelief,
    fallback: ClassificationCandidate | None = None,
) -> ClassificationCandidate:
    rank_null = _rank_null_candidate(rank)
    if rank_null is not None:
        return rank_null
    residual = _top_residual_candidate(rank)
    if residual is not None:
        return residual
    if fallback is not None:
        return fallback
    return _top_candidate(rank)


def _rank_null_candidate(rank: RankBelief) -> RankNullCandidate | None:
    for candidate in rank.candidates:
        if isinstance(candidate, RankNullCandidate):
            return candidate
    return None


def _top_residual_candidate(rank: RankBelief) -> ResidualBelowTaxonCandidate | None:
    residual_candidates = [
        candidate
        for candidate in rank.candidates
        if isinstance(candidate, ResidualBelowTaxonCandidate)
    ]
    if not residual_candidates:
        return None
    return max(residual_candidates, key=lambda candidate: candidate.score)


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


def _lineage_taxa_by_rank(candidate: TaxonCandidate) -> dict[int, int]:
    lineage: dict[int, int] = {}
    if candidate.ancestor_taxon_ids_by_rank is not None:
        lineage.update(
            {
                int(rank_level): int(taxon_id)
                for rank_level, taxon_id in candidate.ancestor_taxon_ids_by_rank.items()
            }
        )
    if candidate.taxon_snapshot is not None:
        lineage.update(
            {
                int(rank_level): int(taxon_id)
                for rank_level, taxon_id in (
                    candidate.taxon_snapshot.ancestor_taxon_ids_by_rank.items()
                )
            }
        )
    lineage[int(candidate.rank_level)] = int(candidate.taxon_id)
    return lineage


def _lowest_common_ancestor_depth(
    left_lineage: Mapping[int, int],
    right_lineage: Mapping[int, int],
    matrix: TaxonomyCostMatrix,
) -> float:
    common_depth = 0.0
    for rank_level, taxon_id in left_lineage.items():
        if right_lineage.get(rank_level) == taxon_id:
            common_depth = max(common_depth, matrix.rank_depth(rank_level))
    return common_depth


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
