"""Public re‑exports for the Typus package."""

# ClassificationResult v1.2.1 is the canonical classification contract. The
# legacy HierarchicalClassificationResult and TaskPrediction exports are kept
# only for the POL-980 one-release deprecation window.

from importlib.metadata import version as _v
from typing import TYPE_CHECKING

from .constants import RANK_CANON, RankLevel, infer_rank
from .helpers.classification import (
    TaxonomyCostMatrix,
    cost_matrix_v0_aggressive,
    cost_matrix_v0_balanced,
    cost_matrix_v0_conservative,
    cost_matrix_v0_profiles,
    derive_lineage,
    expected_utility_policy,
)
from .models.clade import Clade
from .models.classification import (
    AdjustmentReason,
    AggregationStage,
    AttributionGranularity,
    AttributionSemantics,
    BaseCandidate,
    CalibrationMethod,
    CalibrationProvenance,
    CandidateMatch,
    CandidateRef,
    ClassificationCandidate,
    ClassificationConsistency,
    ClassificationInputContext,
    ClassificationProvenance,
    ClassificationResult,
    ClassificationSourceKind,
    DecisionOutcome,
    DecisionPolicy,
    DecisionPolicyKind,
    DecisionScoreSemantics,
    EvidenceShape,
    HierarchicalClassificationResult,
    InputAggregation,
    InputAttribution,
    ModelEvidenceProvenance,
    OutcomeAdjustment,
    PoolingMode,
    RankBelief,
    RankNullCandidate,
    RankNullCandidateMatch,
    ResidualBelowTaxonCandidate,
    ResidualBelowTaxonCandidateMatch,
    RoutingProvenance,
    RoutingStrategy,
    ScoreSemantics,
    TaskPrediction,
    TaxonCandidate,
    TaxonCandidateMatch,
    TaxonomyContext,
    TaxonSnapshot,
)
from .models.detection import ImageDetectionResult, InstancePrediction
from .models.geometry import (
    BBox,
    BBoxFormat,
    BBoxMapper,
    BBoxXYWHNorm,
    EncodedMask,
    MaskEncoding,
    from_xyxy_px,
    to_xyxy_px,
)
from .models.lineage import LineageMap
from .models.summary import TaxonSummary, TaxonTrailNode
from .models.taxon import Taxon
from .models.tracks import Detection, Track, TrackStats
from .ops import (
    area_xyxy,
    clamp_xyxy,
    from_xywh_px,
    intersect_xyxy,
    iou_xyxy,
    to_xywh_px,
    union_xyxy,
    xywh_to_xyxy,
    xyxy_to_xywh,
)
from .pollinator_groups import PollinatorGroup, PollinatorGroupDef, pollinator_groups_for_ancestry
from .services.projections import (
    datetime_to_temporal_sinusoids,
    elevation_to_sinusoids,
    latlon_to_unit_sphere,
    unit_sphere_to_latlon,
)

# Service symbols (taxonomy bases, offline/Postgres backends, elevation) pull in
# sqlalchemy, so they are resolved lazily on first attribute access. `typus` and
# its DTO/geometry modules stay importable with only pydantic installed.
if TYPE_CHECKING:
    from .services.elevation import ElevationService, PostgresRasterElevation
    from .services.taxonomy import AbstractTaxonomyService as TaxonomyService
    from .services.taxonomy import (
        BackendConnectionError,
        PostgresTaxonomyService,
        SQLiteTaxonomyService,
        TaxonNotFoundError,
        TaxonomyServiceError,
    )

_LAZY: dict[str, tuple[str, str]] = {
    "ElevationService": ("typus.services.elevation", "ElevationService"),
    "PostgresRasterElevation": ("typus.services.elevation", "PostgresRasterElevation"),
    "TaxonomyService": ("typus.services.taxonomy", "AbstractTaxonomyService"),
    "BackendConnectionError": ("typus.services.taxonomy", "BackendConnectionError"),
    "PostgresTaxonomyService": ("typus.services.taxonomy", "PostgresTaxonomyService"),
    "SQLiteTaxonomyService": ("typus.services.taxonomy", "SQLiteTaxonomyService"),
    "TaxonNotFoundError": ("typus.services.taxonomy", "TaxonNotFoundError"),
    "TaxonomyServiceError": ("typus.services.taxonomy", "TaxonomyServiceError"),
}

# Missing modules with these names mean an extra was not installed; anything else
# is a genuine internal import bug and must surface unchanged rather than be
# rebranded as a packaging problem.
_OPTIONAL_SERVICE_DEPS = frozenset({"sqlalchemy", "greenlet", "rapidfuzz", "asyncpg", "aiosqlite"})


if not TYPE_CHECKING:

    def __getattr__(name: str) -> object:
        target = _LAZY.get(name)
        if target is None:
            raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
        from importlib import import_module

        try:
            module = import_module(target[0])
        except ModuleNotFoundError as exc:  # pragma: no cover - dependency wiring guard
            if exc.name in _OPTIONAL_SERVICE_DEPS:
                raise ModuleNotFoundError(
                    f"`typus.{name}` requires the optional service dependencies "
                    f"(missing '{exc.name}'). Install with "
                    '`uv pip install "polli-typus[services]"` '
                    "(or [postgres] / [sqlite] for a driver)."
                ) from exc
            raise
        value = getattr(module, target[1])
        globals()[name] = value
        return value

    def __dir__() -> list[str]:
        return sorted((set(globals()) | set(_LAZY)) - {"TYPE_CHECKING"})


__all__ = [
    "RANK_CANON",
    "RankLevel",
    "Taxon",
    "TaxonomyCostMatrix",
    "TaxonSummary",
    "TaxonTrailNode",
    "infer_rank",
    "LineageMap",
    "BBoxXYWHNorm",
    "BBoxMapper",
    "BBox",
    "EncodedMask",
    "BBoxFormat",
    "MaskEncoding",
    "to_xyxy_px",
    "from_xyxy_px",
    "iou_xyxy",
    "area_xyxy",
    "intersect_xyxy",
    "union_xyxy",
    "clamp_xyxy",
    "to_xywh_px",
    "from_xywh_px",
    "xyxy_to_xywh",
    "xywh_to_xyxy",
    "InstancePrediction",
    "ImageDetectionResult",
    "Detection",
    "Track",
    "TrackStats",
    "latlon_to_unit_sphere",
    "unit_sphere_to_latlon",
    "datetime_to_temporal_sinusoids",
    "elevation_to_sinusoids",
    "ElevationService",
    "PostgresRasterElevation",
    "TaxonomyService",
    "TaxonomyServiceError",
    "BackendConnectionError",
    "TaxonNotFoundError",
    "PostgresTaxonomyService",
    "SQLiteTaxonomyService",
    "PollinatorGroup",
    "PollinatorGroupDef",
    "pollinator_groups_for_ancestry",
    "Clade",
    "AdjustmentReason",
    "AggregationStage",
    "AttributionGranularity",
    "AttributionSemantics",
    "BaseCandidate",
    "CalibrationMethod",
    "CalibrationProvenance",
    "CandidateMatch",
    "CandidateRef",
    "ClassificationCandidate",
    "ClassificationConsistency",
    "ClassificationInputContext",
    "ClassificationProvenance",
    "ClassificationResult",
    "ClassificationSourceKind",
    "DecisionOutcome",
    "DecisionPolicy",
    "DecisionPolicyKind",
    "DecisionScoreSemantics",
    "EvidenceShape",
    "InputAggregation",
    "InputAttribution",
    "ModelEvidenceProvenance",
    "OutcomeAdjustment",
    "PoolingMode",
    "RankBelief",
    "RankNullCandidate",
    "RankNullCandidateMatch",
    "ResidualBelowTaxonCandidate",
    "ResidualBelowTaxonCandidateMatch",
    "RoutingProvenance",
    "RoutingStrategy",
    "ScoreSemantics",
    "TaxonCandidate",
    "TaxonCandidateMatch",
    "TaxonSnapshot",
    "TaskPrediction",
    "HierarchicalClassificationResult",
    "TaxonomyContext",
    "cost_matrix_v0_aggressive",
    "cost_matrix_v0_balanced",
    "cost_matrix_v0_conservative",
    "cost_matrix_v0_profiles",
    "derive_lineage",
    "expected_utility_policy",
]
__version__ = _v("polli-typus")
