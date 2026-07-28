from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ..constants import RankLevel

INATURALIST_TAXON_SOURCE = "iNaturalist"


class Taxon(BaseModel):
    """Immutable scientific taxon object."""

    taxon_id: int
    scientific_name: str
    rank_level: RankLevel
    parent_id: int | None = Field(default=None, description="Immediate ancestor taxon_id")
    ancestry: list[int] = Field(default_factory=list, description="Root→self inclusive")
    source: str = Field(
        default=INATURALIST_TAXON_SOURCE,
        description=(
            "Authority governing taxon_id, parent_id, and ancestry IDs. "
            "Enrichment fields may have separate provenance."
        ),
    )
    vernacular: dict[str, list[str]] = Field(default_factory=dict)

    model_config = ConfigDict(
        frozen=True,
        extra="ignore",
    )
