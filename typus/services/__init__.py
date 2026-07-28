"""Services for Typus (taxonomy, elevation, etc.)."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .taxonomy import (
        AbstractTaxonomyService,
        BackendConnectionError,
        PostgresTaxonomyService,
        SQLiteTaxonomyService,
        TaxonNotFoundError,
        TaxonomyServiceError,
    )

# Missing modules with these names mean an extra was not installed; anything else
# is a genuine internal import bug and must surface unchanged.
_OPTIONAL_SERVICE_DEPS = frozenset({"sqlalchemy", "greenlet", "rapidfuzz", "asyncpg", "aiosqlite"})

# Taxonomy services pull in sqlalchemy; resolve them lazily so that importing
# `typus.services` (e.g. for `projections`) stays dependency-light.
_LAZY = {
    "AbstractTaxonomyService",
    "BackendConnectionError",
    "PostgresTaxonomyService",
    "SQLiteTaxonomyService",
    "TaxonNotFoundError",
    "TaxonomyServiceError",
}


if not TYPE_CHECKING:

    def __getattr__(name: str) -> object:
        if name not in _LAZY:
            raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
        from importlib import import_module

        try:
            module = import_module("typus.services.taxonomy")
        except ModuleNotFoundError as exc:  # pragma: no cover - dependency wiring guard
            if exc.name in _OPTIONAL_SERVICE_DEPS:
                raise ModuleNotFoundError(
                    f"`typus.services.{name}` requires the optional service dependencies "
                    f"(missing '{exc.name}'). Install with "
                    '`uv pip install "polli-typus[services]"` '
                    "(or [postgres] / [sqlite] for a driver)."
                ) from exc
            raise
        value = getattr(module, name)
        globals()[name] = value
        return value

    def __dir__() -> list[str]:
        return sorted((set(globals()) | _LAZY) - {"TYPE_CHECKING"})


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
