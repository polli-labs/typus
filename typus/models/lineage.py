from __future__ import annotations

from collections import OrderedDict
from typing import Dict, Iterable

from pydantic import BaseModel, ConfigDict, Field

from ..constants import RankLevel
from .taxon import Taxon


class LineageMap(BaseModel):
    """Sparse mapping rank→Taxon along one ancestor chain."""

    ranks: Dict[RankLevel, Taxon] = Field(default_factory=dict)
    model_config = ConfigDict(
        frozen=True,
    )

    def lowest_present(self) -> Taxon:
        return max(self.ranks.items(), key=lambda kv: kv[0])[1]

    def ordered(self) -> OrderedDict[RankLevel, Taxon]:
        return OrderedDict(sorted(self.ranks.items(), key=lambda kv: kv[0]))

    def to_dict(self) -> dict[str, int]:
        """Return `{canonical_name: taxon_id}` mapping."""
        from ..constants import RANK_CANON

        return {RANK_CANON[k]: v.taxon_id for k, v in self.ordered().items()}

    @classmethod
    def from_taxon(cls, taxon: Taxon, ancestors: Iterable[Taxon]) -> "LineageMap":
        mapping = {t.rank_level: t for t in ancestors}
        mapping[taxon.rank_level] = taxon
        return cls(ranks=mapping)
