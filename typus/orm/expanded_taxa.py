# typus/orm/expanded_taxa.py
from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, deferred, mapped_column, synonym

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

    # Parentage fields - mapped to production DB column names
    parent_id: Mapped[int | None] = mapped_column(
        "immediateAncestor_taxonID", Integer, nullable=True
    )
    parent_rank_level: Mapped[int | None] = mapped_column(
        "immediateAncestor_rankLevel", Integer, nullable=True
    )
    major_parent_id: Mapped[int | None] = mapped_column(
        "immediateMajorAncestor_taxonID", Integer, nullable=True
    )
    major_parent_rank_level: Mapped[int | None] = mapped_column(
        "immediateMajorAncestor_rankLevel", Integer, nullable=True
    )

    # Deprecated legacy aliases. These allow code using the old attribute names
    # (`true_parent_id`, `true_parent_rank_level`) to continue working by
    # referring to the new primary attributes (`parent_id`, `parent_rank_level`).
    # The attributes `major_parent_id` and `major_parent_rank_level` were the
    # Python attribute names used previously and are now directly mapped to the
    # new `immediateMajorAncestor_*` database columns, so no synonyms are needed for them.
    true_parent_id: Mapped[int | None] = synonym("parent_id", doc="deprecated alias for parent_id")
    true_parent_rank_level: Mapped[int | None] = synonym(
        "parent_rank_level", doc="deprecated alias for parent_rank_level"
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
    ancestry_str: Mapped[str | None] = deferred(
        mapped_column("ancestry", String, nullable=True),
        doc="deprecated — replaced by immediate* columns",
    )
    path_ltree: Mapped[str | None] = deferred(
        mapped_column("path", String, nullable=True),
        doc="ltree string from Postgres. May be absent in some environments/tables.",
    )

    # Materialized expanded per-rank columns for ALL ranks in RankLevel
    # These must match the column names in tests/sample_tsv/expanded_taxa_sample.tsv
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
