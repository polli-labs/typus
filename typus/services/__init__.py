"""Services for Typus (taxonomy, elevation, etc.)."""

from .taxonomy import (
    AbstractTaxonomyService,
    BackendConnectionError,
    PostgresTaxonomyService,
    SQLiteTaxonomyService,
    TaxonNotFoundError,
    TaxonomyServiceError,
)


def load_expanded_taxa(*args, **kwargs):
    """Lazy loader wrapper to keep heavy TSV/HTTP deps optional at import time."""
    try:
        from .sqlite_loader import load_expanded_taxa as _load_expanded_taxa
    except ModuleNotFoundError as exc:  # pragma: no cover - dependency wiring guard
        if exc.name:
            raise ModuleNotFoundError(
                f"`load_expanded_taxa` requires optional dependency '{exc.name}'. "
                'Install with `uv pip install "polli-typus[loader]"`.'
            ) from exc
        raise

    return _load_expanded_taxa(*args, **kwargs)


__all__ = [
    "AbstractTaxonomyService",
    "TaxonomyServiceError",
    "BackendConnectionError",
    "TaxonNotFoundError",
    "PostgresTaxonomyService",
    "SQLiteTaxonomyService",
    "load_expanded_taxa",
]
