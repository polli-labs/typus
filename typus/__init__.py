"""Public re‑exports for the Typus package."""

# ClassificationResult v1.2.1 is the canonical classification contract. The
# legacy HierarchicalClassificationResult and TaskPrediction exports are kept
# only for the POL-980 one-release deprecation window.

from importlib.metadata import version as _v

from .constants import RankLevel, infer_rank
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
from .models.geometry import BBoxMapper, BBoxXYWHNorm, from_xyxy_px, to_xyxy_px
from .models.lineage import LineageMap
from .models.summary import TaxonSummary, TaxonTrailNode
from .models.taxon import Taxon
from .models.tracks import Detection, Track, TrackStats
from .pollinator_groups import PollinatorGroup, PollinatorGroupDef, pollinator_groups_for_ancestry
from .services.elevation import ElevationService, PostgresRasterElevation
from .services.projections import (
    datetime_to_temporal_sinusoids,
    elevation_to_sinusoids,
    latlon_to_unit_sphere,
    unit_sphere_to_latlon,
)

# Core taxonomy service bases
from .services.taxonomy import (
    AbstractTaxonomyService as TaxonomyService,
)

# Lightweight offline service
from .services.taxonomy import (
    BackendConnectionError,
    PostgresTaxonomyService,
    SQLiteTaxonomyService,
    TaxonNotFoundError,
    TaxonomyServiceError,
)

__all__ = [
    "RankLevel",
    "Taxon",
    "TaxonSummary",
    "TaxonTrailNode",
    "infer_rank",
    "LineageMap",
    "BBoxXYWHNorm",
    "BBoxMapper",
    "to_xyxy_px",
    "from_xyxy_px",
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
]
__version__ = _v("polli-typus")
