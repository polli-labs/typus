"""Abstract taxonomy service interface.

Shared contract for Postgres and SQLite taxonomy backends.
"""

from __future__ import annotations

import abc
from typing import List, Set, Tuple

from ...constants import RankLevel
from ...models.summary import TaxonSummary
from ...models.taxon import Taxon
from ...pollinator_groups import PollinatorGroup, pollinator_groups_for_ancestry


class AbstractTaxonomyService(abc.ABC):
    @abc.abstractmethod
    async def get_taxon(self, taxon_id: int) -> Taxon: ...

    async def get_many(self, ids: set[int]):
        for i in ids:
            yield await self.get_taxon(i)

    @abc.abstractmethod
    async def children(self, taxon_id: int, *, depth: int = 1): ...

    @abc.abstractmethod
    async def lca(self, taxon_ids: set[int], *, include_minor_ranks: bool = False) -> Taxon: ...

    @abc.abstractmethod
    async def distance(
        self,
        a: int,
        b: int,
        *,
        include_minor_ranks: bool = False,
        inclusive: bool = False,
    ) -> int: ...

    # Name search API
    @abc.abstractmethod
    async def search_taxa(
        self,
        query: str,
        *,
        scopes: Set[str] | None = None,  # {"scientific", "vernacular"}
        languages: Set[str] | None = None,  # currently only {"en"} effective
        match: str = "auto",  # one of: "exact", "prefix", "substring", "auto"
        fuzzy: bool = True,
        threshold: float = 0.8,
        limit: int = 20,
        rank_filter: Set[RankLevel] | None = None,
        with_scores: bool = False,
    ) -> List[Taxon] | List[Tuple[Taxon, float]]: ...

    # Efficient batched resolution (default naive backstop)
    async def get_many_batched(
        self, ids: Set[int]
    ) -> dict[int, Taxon]:  # pragma: no cover - backstop
        out: dict[int, Taxon] = {}
        for i in ids:
            out[i] = await self.get_taxon(i)
        return out

    # Ancestors helper
    @abc.abstractmethod
    async def ancestors(self, taxon_id: int, *, include_minor_ranks: bool = True) -> List[int]: ...

    # Convenience: uniform list return for children on all backends
    @abc.abstractmethod
    async def children_list(self, taxon_id: int, *, depth: int = 1) -> List[Taxon]: ...

    @abc.abstractmethod
    async def taxon_summary(
        self,
        taxon_id: int,
        *,
        major_ranks_only: bool = True,
    ) -> TaxonSummary: ...

    async def pollinator_groups_for_taxon(self, taxon_id: int) -> set[PollinatorGroup]:
        """Return pollinator groups matched by the taxon's ancestry (root → self)."""

        ancestry = await self.ancestors(taxon_id, include_minor_ranks=True)
        return pollinator_groups_for_ancestry(ancestry)


__all__ = ["AbstractTaxonomyService"]
