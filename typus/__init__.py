"""Public re‑exports for the Typus package."""

from importlib.metadata import version as _v

from .constants import RankLevel, infer_rank
from .models.clade import Clade
from .models.classification import (
    HierarchicalClassificationResult,
    TaskPrediction,
    TaxonomyContext,
)
from .models.geometry import BBoxMapper, BBoxXYWHNorm, from_xyxy_px, to_xyxy_px
from .models.lineage import LineageMap
from .models.taxon import Taxon
from .models.tracks import Detection, Track, TrackStats
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
    PostgresTaxonomyService,
    SQLiteTaxonomyService,
)

__all__ = [
    "RankLevel",
    "Taxon",
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
    "PostgresTaxonomyService",
    "SQLiteTaxonomyService",
    "Clade",
    "TaskPrediction",
    "HierarchicalClassificationResult",
    "TaxonomyContext",
]
__version__ = _v("polli-typus")
