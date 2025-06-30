from __future__ import annotations

from typing import Dict, Set

from pydantic import ConfigDict, Field

from ..services.taxonomy import AbstractTaxonomyService
from .serialise import CompactJsonMixin
from .taxon import Taxon


class Clade(CompactJsonMixin):
    """Set‑based clade (may be multi‑root == metaclade)."""

    root_ids: Set[int] = Field(description="taxon_id values designating the clade roots")
    name: str | None = None
    description: str | None = None

    # private, non‑serialised cache
    cache: Dict[int, Taxon] | None = Field(default=None, exclude=True, repr=False)

    model_config = ConfigDict(
        frozen=True,
    )

    async def roots(self, svc: AbstractTaxonomyService) -> Set[Taxon]:
        if self.cache is None:
            self.cache = {t.taxon_id: t async for t in svc.get_many(self.root_ids)}
        return set(self.cache.values())
