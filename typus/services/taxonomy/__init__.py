"""Taxonomy services subpackage.

Provides a stable import surface for AbstractTaxonomyService,
PostgresTaxonomyService, and SQLiteTaxonomyService.

During the transition, implementations are imported from existing modules
to preserve behavior while normalizing layout.
"""

from .abstract import AbstractTaxonomyService
from .postgres import PostgresTaxonomyService
from .sqlite import SQLiteTaxonomyService

__all__ = [
    "AbstractTaxonomyService",
    "PostgresTaxonomyService",
    "SQLiteTaxonomyService",
]
