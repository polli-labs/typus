from __future__ import annotations

import warnings
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator, model_validator

from ..constants import RANK_CANON, RankLevel
from .serialise import CompactJsonMixin


def _warn_deprecated(name: str) -> None:
    warnings.warn(
        (
            f"{name} is deprecated for one Typus release window. "
            "Use ClassificationResult v1.2.1 instead; see POL-980."
        ),
        DeprecationWarning,
        stacklevel=3,
    )


def _rank_name(rank_level: int) -> str:
    try:
        return RANK_CANON[RankLevel(rank_level)]
    except (KeyError, ValueError):
        return str(rank_level)


class ClassificationSourceKind(str, Enum):
    MODEL_INFERENCE = "model_inference"
    CURATED_TAXON_CARD = "curated_taxon_card"
    SYNTHETIC_DEMO = "synthetic_demo"
    CACHE_REPLAY = "cache_replay"
    TEST_FIXTURE = "test_fixture"


class ScoreSemantics(str, Enum):
    RANK_SOFTMAX_PROBABILITY = "rank_softmax_probability"
    TEMPERATURE_SCALED_RANK_PROBABILITY = "temperature_scaled_rank_probability"
    CALIBRATED_RANK_PROBABILITY = "calibrated_rank_probability"
    AUTHORED_ASSERTION_WEIGHT = "authored_assertion_weight"
    SYNTHETIC_DEMO_WEIGHT = "synthetic_demo_weight"
    CONFORMAL_SET_MEMBERSHIP = "conformal_set_membership"
    DISPLAY_WEIGHT = "display_weight"


class EvidenceShape(str, Enum):
    SINGLE_IMAGE = "single_image"
    MULTI_VIEW_OBSERVATION = "multi_view_observation"
    TEMPORAL_SEQUENCE = "temporal_sequence"
    AUTHORED_CARD = "authored_card"


class AggregationStage(str, Enum):
    NONE = "none"
    POOLED_BEFORE_HEADS = "pooled_before_heads"
    AGGREGATED_AFTER_HEADS = "aggregated_after_heads"
    UNKNOWN = "unknown"


class PoolingMode(str, Enum):
    MEAN = "mean"
    LOGSUMEXP = "logsumexp"
    ATTENTION = "attention"
    OTHER = "other"


class AttributionGranularity(str, Enum):
    NONE = "none"
    VIEW = "view"
    FRAME = "frame"
    PATCH = "patch"
    SEGMENT = "segment"
    TRACKLET = "tracklet"


class AttributionSemantics(str, Enum):
    ATTENTION_WEIGHT = "attention_weight"
    PER_UNIT_LOGITS = "per_unit_logits"
    GRADIENT = "gradient"
    HEURISTIC = "heuristic"


class RoutingStrategy(str, Enum):
    SOFT = "soft"
    HARD = "hard"
    GUMBEL = "gumbel"


class DecisionPolicyKind(str, Enum):
    ARGMAX = "argmax"
    RANK_NULL_ARGMAX = "rank_null_argmax"
    MAX_PROBABILITY_THRESHOLD = "max_probability_threshold"
    HIERARCHY_REPAIR = "hierarchy_repair"
    CONFORMAL_FRONTIER = "conformal_frontier"
    COST_SENSITIVE_POLICY = "cost_sensitive_policy"
    DEMO_PROJECTION = "demo_projection"


class AdjustmentReason(str, Enum):
    COMMIT_TOP_CANDIDATE = "commit_top_candidate"
    COMMIT_THRESHOLDED = "commit_thresholded"
    COMMIT_AFTER_REPAIR = "commit_after_repair"
    ABSTAIN_MODEL_NATURAL = "abstain_model_natural"
    ABSTAIN_THRESHOLD_NOT_MET = "abstain_threshold_not_met"
    ABSTAIN_PARENT_ABSTAINED = "abstain_parent_abstained"
    ABSTAIN_HIERARCHY_CONFLICT = "abstain_hierarchy_conflict"
    ABSTAIN_UNMAPPED_TAXON = "abstain_unmapped_taxon"
    ABSTAIN_CONFORMAL_SET_OPEN = "abstain_conformal_set_open"
    CURATED_AUTHORED = "curated_authored"


class CalibrationMethod(str, Enum):
    TEMPERATURE_SCALING = "temperature_scaling"
    ISOTONIC = "isotonic"
    PLATT = "platt"
    CONFORMAL = "conformal"


class DecisionScoreSemantics(str, Enum):
    SELECTED_CANDIDATE_SCORE = "selected_candidate_score"
    THRESHOLD_MARGIN = "threshold_margin"
    POLICY_CONFIDENCE = "policy_confidence"
    COVERAGE_TARGET = "coverage_target"
    DISPLAY_WEIGHT = "display_weight"


class TaxonomyContext(CompactJsonMixin):
    source: str = "CoL2024"
    version: str | None = None
    root_taxon_ids: list[int] = Field(default_factory=list)
    null_taxon_ids_by_rank: dict[int, int] = Field(default_factory=dict)


class TaxonSnapshot(CompactJsonMixin):
    scientific_name: str
    common_name: str | None = None
    rank_level: int
    rank_name: str
    parent_taxon_id: int | None = None
    ancestor_taxon_ids_by_rank: dict[int, int] = Field(default_factory=dict)
    taxonomy_version: str


class BaseCandidate(CompactJsonMixin):
    rank_level: int
    rank_name: str
    score: float
    score_semantics: ScoreSemantics


class TaxonCandidate(BaseCandidate):
    kind: Literal["taxon"] = "taxon"
    taxon_id: int
    parent_taxon_id: int | None = None
    ancestor_taxon_ids_by_rank: dict[int, int] | None = None
    taxon_snapshot: TaxonSnapshot | None = None


class RankNullCandidate(BaseCandidate):
    kind: Literal["rank_null"] = "rank_null"
    null_taxon_id: int | None = None


class ResidualBelowTaxonCandidate(BaseCandidate):
    kind: Literal["residual_below_taxon"] = "residual_below_taxon"
    parent_taxon_id: int
    target_rank_level: int


ClassificationCandidate = Annotated[
    TaxonCandidate | RankNullCandidate | ResidualBelowTaxonCandidate,
    Field(discriminator="kind"),
]


class RankBelief(CompactJsonMixin):
    rank_level: int
    rank_name: str
    candidates: list[ClassificationCandidate]

    @model_validator(mode="after")
    def _validate_candidate_ranks(self) -> "RankBelief":
        for candidate in self.candidates:
            if candidate.rank_level != self.rank_level:
                raise ValueError("candidate rank_level must match RankBelief rank_level")
        return self


class TaxonCandidateMatch(CompactJsonMixin):
    kind: Literal["taxon"] = "taxon"
    taxon_id: int


class RankNullCandidateMatch(CompactJsonMixin):
    kind: Literal["rank_null"] = "rank_null"


class ResidualBelowTaxonCandidateMatch(CompactJsonMixin):
    kind: Literal["residual_below_taxon"] = "residual_below_taxon"
    parent_taxon_id: int


CandidateMatch = Annotated[
    TaxonCandidateMatch | RankNullCandidateMatch | ResidualBelowTaxonCandidateMatch,
    Field(discriminator="kind"),
]


class CandidateRef(CompactJsonMixin):
    rank_level: int
    match: CandidateMatch


class OutcomeAdjustment(CompactJsonMixin):
    reason: AdjustmentReason
    applied_candidate: CandidateRef
    suppressed_from: CandidateRef | None = None


class DecisionOutcome(CompactJsonMixin):
    rank_level: int
    decision: Literal["commit", "abstain"]
    resolved_to: CandidateRef | None = None
    decision_score: float | None = None
    decision_score_semantics: DecisionScoreSemantics | None = None
    derived_from_policy_id: str
    adjustment: OutcomeAdjustment


class InputAggregation(CompactJsonMixin):
    stage: AggregationStage
    pooling_mode: PoolingMode | None = None
    pooling_temperature: float | None = None
    selection_strategy: str | None = None


class InputAttribution(CompactJsonMixin):
    granularity: AttributionGranularity
    semantics: AttributionSemantics | None = None


class ClassificationInputContext(CompactJsonMixin):
    entity_type: Literal["image", "crop", "detection", "track", "observation", "card"]
    evidence_shape: EvidenceShape
    unit_count: int
    unit_ids: list[str] | None = None
    aggregation: InputAggregation | None = None
    attribution: InputAttribution | None = None


class RoutingProvenance(CompactJsonMixin):
    strategy: RoutingStrategy
    temperature: float
    hierarchy_matrix_applied: bool


class ModelEvidenceProvenance(CompactJsonMixin):
    head_kind: (
        Literal[
            "conditional_classifier",
            "hierarchical_softmax",
            "other",
        ]
        | None
    ) = None
    routing: RoutingProvenance | None = None
    abstention_signal_kind: (
        Literal[
            "rank_null_candidate",
            "selector_head",
            "evidential_dirichlet",
            "rl_action_head",
            "gambler_class",
            "none",
        ]
        | None
    ) = None


class CalibrationProvenance(CompactJsonMixin):
    method: CalibrationMethod
    calibration_set_id: str | None = None
    parameters: dict[str, Any] | None = None
    target_coverage: float | None = None


class DecisionPolicy(CompactJsonMixin):
    id: str
    kind: DecisionPolicyKind
    parameters: dict[str, Any] | None = None
    chain_order: int


class ClassificationProvenance(CompactJsonMixin):
    source_kind: ClassificationSourceKind
    producer: str
    model_name: str | None = None
    model_version: str | None = None
    checkpoint_uri: str | None = None
    checkpoint_sha: str | None = None
    inference_timestamp: str | None = None
    requested_top_k: int | None = None
    handler_version: str | None = None
    model_evidence: ModelEvidenceProvenance | None = None
    calibration: CalibrationProvenance | None = None
    decision_policies: list[DecisionPolicy]


class ClassificationConsistency(CompactJsonMixin):
    hierarchy_checked: bool
    is_consistent: bool


class ClassificationResult(CompactJsonMixin):
    schema_version: Literal["classification-result.v1"] = "classification-result.v1"
    taxonomy_context: TaxonomyContext
    provenance: ClassificationProvenance
    input_context: ClassificationInputContext
    consistency: ClassificationConsistency
    ranks: list[RankBelief]
    outcomes: list[DecisionOutcome] | None = None

    @model_validator(mode="after")
    def _validate_result_contract(self) -> "ClassificationResult":
        policies = self.provenance.decision_policies
        has_outcomes = self.outcomes is not None
        if bool(policies) != has_outcomes:
            raise ValueError(
                "outcomes must be present iff provenance.decision_policies is non-empty"
            )

        if self.provenance.source_kind is ClassificationSourceKind.CURATED_TAXON_CARD:
            for rank in self.ranks:
                for candidate in rank.candidates:
                    if candidate.score_semantics is not ScoreSemantics.AUTHORED_ASSERTION_WEIGHT:
                        raise ValueError(
                            "curated_taxon_card candidates must use "
                            "authored_assertion_weight score semantics"
                        )

        if self.outcomes is None:
            return self

        if len(self.outcomes) != len(self.ranks):
            raise ValueError("outcomes length must match ranks length")

        policy_ids = {policy.id for policy in policies}
        for rank, outcome in zip(self.ranks, self.outcomes):
            if outcome.rank_level != rank.rank_level:
                raise ValueError("outcomes rank order must match ranks")
            if outcome.derived_from_policy_id not in policy_ids:
                raise ValueError("outcome derived_from_policy_id does not resolve")
            if outcome.resolved_to is not None and not _ref_resolves(
                outcome.resolved_to, rank.candidates
            ):
                raise ValueError("outcome resolved_to does not resolve into rank candidates")
            if not _ref_resolves(outcome.adjustment.applied_candidate, rank.candidates):
                raise ValueError(
                    "outcome adjustment applied_candidate does not resolve into rank candidates"
                )
            if (
                outcome.resolved_to is not None
                and outcome.resolved_to != outcome.adjustment.applied_candidate
            ):
                raise ValueError("outcome resolved_to must match adjustment applied_candidate")
            suppressed_from = outcome.adjustment.suppressed_from
            if suppressed_from is not None and not _ref_resolves(suppressed_from, rank.candidates):
                raise ValueError(
                    "outcome adjustment suppressed_from does not resolve into rank candidates"
                )
        return self


def _ref_resolves(
    ref: CandidateRef,
    candidates: list[ClassificationCandidate],
) -> bool:
    for candidate in candidates:
        if candidate.rank_level != ref.rank_level:
            continue
        match = ref.match
        if isinstance(candidate, TaxonCandidate) and isinstance(match, TaxonCandidateMatch):
            if candidate.taxon_id == match.taxon_id:
                return True
        elif isinstance(candidate, RankNullCandidate) and isinstance(match, RankNullCandidateMatch):
            return True
        elif isinstance(candidate, ResidualBelowTaxonCandidate) and isinstance(
            match, ResidualBelowTaxonCandidateMatch
        ):
            if candidate.parent_taxon_id == match.parent_taxon_id:
                return True
    return False


class TaskPrediction(CompactJsonMixin):
    """Deprecated per-rank top-k legacy DTO; use `RankBelief` instead."""

    rank_level: RankLevel
    temperature: float = Field(gt=0)
    predictions: list[tuple[int, float]]

    def __init__(self, **data: Any) -> None:
        _warn_deprecated("TaskPrediction")
        super().__init__(**data)

    @field_validator("predictions")
    @classmethod
    def _prob_sum(cls, value: list[tuple[int, float]]) -> list[tuple[int, float]]:
        if sum(probability for _, probability in value) > 1.0 + 1e-6:
            raise ValueError("probabilities sum > 1")
        return value


class HierarchicalClassificationResult(CompactJsonMixin):
    """Deprecated POL-980 alias kept for one release window.

    Use `ClassificationResult` v1.2.1 for new producers. This model remains
    importable while linnaeus, ibrida, and polli migrate onto the canonical
    Typus contract.
    """

    taxonomy_context: TaxonomyContext
    tasks: list[TaskPrediction]
    subtree_roots: set[int] | None = None

    def __init__(self, **data: Any) -> None:
        _warn_deprecated("HierarchicalClassificationResult")
        super().__init__(**data)

    def to_classification_result(self) -> ClassificationResult:
        ranks = []
        for task in self.tasks:
            rank_level = int(task.rank_level)
            rank_name = _rank_name(rank_level)
            ranks.append(
                RankBelief(
                    rank_level=rank_level,
                    rank_name=rank_name,
                    candidates=[
                        TaxonCandidate(
                            rank_level=rank_level,
                            rank_name=rank_name,
                            score=probability,
                            score_semantics=ScoreSemantics.RANK_SOFTMAX_PROBABILITY,
                            taxon_id=taxon_id,
                        )
                        for taxon_id, probability in task.predictions
                    ],
                )
            )

        return ClassificationResult(
            taxonomy_context=self.taxonomy_context,
            provenance=ClassificationProvenance(
                source_kind=ClassificationSourceKind.MODEL_INFERENCE,
                producer="typus.legacy_hierarchical_classification_result",
                calibration=None,
                decision_policies=[],
            ),
            input_context=ClassificationInputContext(
                entity_type="image",
                evidence_shape=EvidenceShape.SINGLE_IMAGE,
                unit_count=1,
                aggregation=InputAggregation(stage=AggregationStage.NONE),
                attribution=InputAttribution(granularity=AttributionGranularity.NONE),
            ),
            consistency=ClassificationConsistency(
                hierarchy_checked=False,
                is_consistent=True,
            ),
            ranks=ranks,
            outcomes=None,
        )
