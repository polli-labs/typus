# typus/orm/expanded_taxa.py
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, deferred, mapped_column

from .base import Base


# helper to generate column names for each rank prefix
def _rank_cols(prefix: str):
    return (
        f"{prefix}_taxonID",
        f"{prefix}_name",
        f"{prefix}_commonName",
    )


_RANK_PREFIXES = ("L5", "L10", "L20", "L30", "L40", "L50", "L60", "L70")


class ExpandedTaxa(Base):
    """
    Wide, ancestry-expanded view. Avoids n x round-trips to the DB for ancestry
    queries.

    All columns are mapped so callers can read them *when they need to*;
    most are declared `deferred` so a plain `select(ExpandedTaxa)` only
    pulls the light core fields.
    """

    __tablename__ = "expanded_taxa"

    # core identifiers
    taxon_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("expanded_taxa.taxon_id")
    )
    rank_level: Mapped[int] = mapped_column(Integer)
    rank: Mapped[str] = mapped_column(String)
    scientific_name: Mapped[str] = mapped_column("name", String)
    common_name: Mapped[str | None] = mapped_column(String, nullable=True)

    # ancestry helpers
    ancestry: Mapped[str | None] = mapped_column(
        String, nullable=True
    )  # pipe-delimited IDs
    path_ltree: Mapped[str | None] = mapped_column(
        "path", String, nullable=True
    )  # ltree string

    # expanded per-rank columns
    # L5 … L70   (species → kingdom)
    for _prefix in _RANK_PREFIXES:
        locals()[f"{_prefix.lower()}_taxon_id"]: Mapped[int | None] = deferred(
            mapped_column(Integer, nullable=True)
        )
        locals()[f"{_prefix.lower()}_name"]: Mapped[str | None] = deferred(
            mapped_column(String, nullable=True)
        )
        locals()[f"{_prefix.lower()}_common"]: Mapped[str | None] = deferred(
            mapped_column(String, nullable=True)
        )

    del _prefix  # clean namespace
