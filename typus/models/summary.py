from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from ..constants import RankLevel


class TaxonTrailNode(BaseModel):
    """One step in a taxonomic trail (root → focal taxon)."""

    rank_level: RankLevel = Field(description="Rank level for this ancestor")
    taxon_id: int = Field(description="Taxon ID at this rank")
    scientific_name: str = Field(description="Canonical scientific name at this rank")
    vernacular_name: Optional[str] = Field(
        default=None, description="Optional common/vernacular name for this rank"
    )

    model_config = ConfigDict(frozen=True, extra="ignore")


class TaxonSummary(BaseModel):
    """Compact, UI‑friendly view of a taxon and its lineage."""

    taxon_id: int = Field(description="Taxon ID for the focal taxon")
    scientific_name: str = Field(description="Scientific name for the focal taxon")
    vernacular_name: Optional[str] = Field(
        default=None, description="Optional common/vernacular name for the focal taxon"
    )
    rank_level: RankLevel = Field(description="Rank level for the focal taxon")
    trail: List[TaxonTrailNode] = Field(
        description="Ordered lineage from root → focal taxon, inclusive"
    )

    model_config = ConfigDict(frozen=True, extra="ignore")

    def format_trail(
        self,
        *,
        separator: str = " \u2192 ",
        include_vernacular: bool = True,
    ) -> str:
        """Return a formatted trail string, e.g., ``Insecta → Hymenoptera → Apidae``.

        The trail is always rendered root → focal taxon. When ``include_vernacular``
        is true and a node has a vernacular name, it is appended in parentheses.
        """

        parts: list[str] = []
        for node in self.trail:
            if include_vernacular and node.vernacular_name:
                parts.append(f"{node.scientific_name} ({node.vernacular_name})")
            else:
                parts.append(node.scientific_name)
        return separator.join(parts)


__all__ = ["TaxonTrailNode", "TaxonSummary"]
