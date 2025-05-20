"""Public re‑exports for the Typus package."""

from importlib.metadata import version as _v

from .constants import RankLevel, infer_rank
from .models.clade import Clade
from .models.classification import (
    HierarchicalClassificationResult,
    TaskPrediction,
    TaxonomyContext,
)
from .models.lineage import LineageMap
from .models.taxon import Taxon
from .services.elevation import ElevationService, PostgresRasterElevation
from .services.projections import (
    datetime_to_temporal_sinusoids,
    elevation_to_sinusoids,
    latlon_to_unit_sphere,
    unit_sphere_to_latlon,
)
from .services.taxonomy import (
    PostgresTaxonomyService,
    AbstractTaxonomyService as TaxonomyService,
)

__all__ = [
    "RankLevel",
    "Taxon",
    "infer_rank",
    "LineageMap",
    "latlon_to_unit_sphere",
    "unit_sphere_to_latlon",
    "datetime_to_temporal_sinusoids",
    "elevation_to_sinusoids",
    "ElevationService",
    "PostgresRasterElevation",
    "TaxonomyService",
    "PostgresTaxonomyService",
    "Clade",
    "TaskPrediction",
    "HierarchicalClassificationResult",
    "TaxonomyContext",
]
__version__ = _v("typus")
