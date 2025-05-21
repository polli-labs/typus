# typus/orm/expanded_taxa.py
from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, deferred, mapped_column

from ..constants import RankLevel
from .base import Base


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
    taxon_id: Mapped[int] = mapped_column("taxonID", Integer, primary_key=True)

    # Derived parentage fields (populated by fixture generator for SQLite)
    true_parent_id: Mapped[int | None] = mapped_column("trueParentID", Integer, nullable=True)
    true_parent_rank_level: Mapped[int | None] = mapped_column(
        "trueParentRankLevel", Integer, nullable=True
    )
    major_parent_id: Mapped[int | None] = mapped_column("majorParentID", Integer, nullable=True)
    major_parent_rank_level: Mapped[int | None] = mapped_column(
        "majorParentRankLevel", Integer, nullable=True
    )

    rank_level: Mapped[int] = mapped_column(
        "rankLevel", Integer
    )  # In TSV it's int, maps to RankLevel enum value
    rank: Mapped[str] = mapped_column("rank", String)  # Canonical rank name string
    scientific_name: Mapped[str] = mapped_column("name", String)
    common_name: Mapped[str | None] = mapped_column("commonName", String, nullable=True)
    taxon_active: Mapped[bool | None] = mapped_column(
        "taxonActive", Boolean, nullable=True
    )  # SQLite will use 0/1

    # ancestry helpers
    ancestry_str: Mapped[str | None] = mapped_column(
        "ancestry", String, nullable=True
    )  # pipe-delimited IDs, populated by fixture generator
    path_ltree: Mapped[str | None] = mapped_column(
        "path", String, nullable=True
    )  # ltree string from Postgres

    # Materialized expanded per-rank columns for ALL ranks in RankLevel
    # These must match the column names in tests/sample_tsv/expanded_taxa.tsv
    # And the ORM attribute names should be Pythonic (lowercase with underscore)
    for rank_enum_member in RankLevel:
        attr_prefix = rank_enum_member.name.lower()  # e.g., "l10", "l335" for RankLevel.L335

        # Determine DB column prefix based on TSV (e.g. L10, L33_5)
        db_col_val_str = str(rank_enum_member.value)  # e.g. "10", "335"

        # Special handling for half-levels to match TSV column naming convention L<INT>_<DECIMAL>
        if rank_enum_member.value == 335:  # RankLevel.L335
            db_col_prefix_for_tsv = "L33_5"
        elif rank_enum_member.value == 345:  # RankLevel.L345
            db_col_prefix_for_tsv = "L34_5"
        else:  # Standard integer ranks
            db_col_prefix_for_tsv = f"L{db_col_val_str}"

        locals()[f"{attr_prefix}_taxon_id"]: Mapped[int | None] = deferred(
            mapped_column(f"{db_col_prefix_for_tsv}_taxonID", Integer, nullable=True)
        )
        locals()[f"{attr_prefix}_name"]: Mapped[str | None] = deferred(
            mapped_column(f"{db_col_prefix_for_tsv}_name", String, nullable=True)
        )
        locals()[f"{attr_prefix}_common"]: Mapped[str | None] = deferred(  # Maps to L{X}_commonName
            mapped_column(f"{db_col_prefix_for_tsv}_commonName", String, nullable=True)
        )

    del rank_enum_member  # Clean up loop variables from class namespace
    del attr_prefix
    del db_col_val_str
    del db_col_prefix_for_tsv
