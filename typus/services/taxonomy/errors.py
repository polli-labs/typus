"""Shared error types for taxonomy service backends."""

from __future__ import annotations


class TaxonomyServiceError(RuntimeError):
    """Base class for taxonomy service failures."""


class BackendConnectionError(TaxonomyServiceError):
    """Raised when a backend cannot be reached or queried reliably."""


class TaxonNotFoundError(KeyError):
    """Raised when a requested taxon does not exist in the active backend."""
