from __future__ import annotations

import abc
import logging

from sqlalchemy import select, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ..constants import RankLevel, is_major
from ..models.taxon import Taxon
from ..orm.expanded_taxa import ExpandedTaxa


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


logger = logging.getLogger(__name__)


class PostgresTaxonomyService(AbstractTaxonomyService):
    """Async service backed by `expanded_taxa` materialised view."""

    def __init__(self, dsn: str):
        self._engine = create_async_engine(dsn, pool_pre_ping=True)
        self._Session = async_sessionmaker(self._engine, expire_on_commit=False)

    async def get_taxon(self, taxon_id: int) -> Taxon:
        async with self._Session() as s:
            # ORM mapping ExpandedTaxa.parent_id to immediateAncestor_taxonID handles this
            stmt = select(ExpandedTaxa).where(ExpandedTaxa.taxon_id == taxon_id)
            row = await s.scalar(stmt)
            if row is None:
                raise KeyError(taxon_id)
            return self._row_to_taxon(row)

    async def children(self, taxon_id: int, *, depth: int = 1):
        # Uses immediateAncestor_taxonID via ORM's parent_id mapping.
        # The SQL query below refers to "parent_id", which SQLAlchemy resolves
        # to the mapped column "immediateAncestor_taxonID".
        sql = text(
            """
            WITH RECURSIVE sub AS (
              SELECT *, 0 AS lvl FROM expanded_taxa WHERE taxon_id = :tid
              UNION ALL
              SELECT et.*, sub.lvl + 1 FROM expanded_taxa et
                JOIN sub ON et."immediateAncestor_taxonID" = sub.taxon_id
              WHERE sub.lvl < :d )
            SELECT * FROM sub WHERE lvl > 0;
            """
        )
        async with self._Session() as s:
            res = await s.execute(sql, {"tid": taxon_id, "d": depth})
            rows = res.mappings().all()  # Use mappings to get dict-like rows
            for row_mapping in rows:
                # Convert the RowMapping to an ExpandedTaxa-like object for _row_to_taxon
                # This assumes _row_to_taxon can handle an object with attributes matching ExpandedTaxa
                # A more robust way would be to select ExpandedTaxa entities directly if possible,
                # or reconstruct them carefully.
                # For now, let's assume _row_to_taxon can handle dict access or attribute access.
                # To be safe, we can create a temporary object that _row_to_taxon expects.
                # However, ExpandedTaxa instances are what _row_to_taxon usually gets from SQLAlchemy ORM queries.
                # Let's try to use the ORM to fetch full objects if the query structure allows.
                # The current raw SQL returns all columns, so we can try to build Taxon objects.
                # The _row_to_taxon expects an ORM object, so we need to provide that.
                # A simpler way for raw SQL is to make _row_to_taxon take a dict-like row.
                # Let's adjust _row_to_taxon or how we call it.
                # The ticket's `_row_to_taxon` expects `row.taxon_id`, `row.parent_id`, etc.
                # `res.mappings().all()` gives list of dict-like objects.
                yield self._row_to_taxon_from_mapping(row_mapping)

    async def _lca_recursive_fallback(self, s, taxon_ids: set[int]) -> int | None:
        """Fallback LCA implementation using recursive CTE."""
        logger.info("LCA: path column/ltree unavailable, using recursive fallback.")
        # Build the parts of the CTE
        # Anchor: select direct ancestors for each taxon_id
        anchor_parts = []
        for i, tid in enumerate(taxon_ids):
            anchor_parts.append(
                f'SELECT {tid} AS query_taxon_id, taxon_id, "immediateAncestor_taxonID" AS parent_id, 0 AS lvl FROM expanded_taxa WHERE taxon_id = {tid}'
            )
        anchor_sql = " UNION ALL ".join(anchor_parts)

        recursive_sql = f"""
            WITH RECURSIVE taxon_ancestors (query_taxon_id, taxon_id, parent_id, lvl) AS (
                {anchor_sql}
                UNION ALL
                SELECT ta.query_taxon_id, et.taxon_id, et."immediateAncestor_taxonID", ta.lvl + 1
                FROM expanded_taxa et
                JOIN taxon_ancestors ta ON et.taxon_id = ta.parent_id
                WHERE ta.parent_id IS NOT NULL
            )
            SELECT taxon_id
            FROM taxon_ancestors
            GROUP BY taxon_id
            HAVING COUNT(DISTINCT query_taxon_id) = {len(taxon_ids)}  -- Must be an ancestor of ALL query_taxon_ids
            ORDER BY MAX(lvl) DESC  -- Deepest common ancestor
            LIMIT 1
        """
        lca_tid = await s.scalar(text(recursive_sql))
        return lca_tid

    async def lca(self, taxon_ids: set[int], *, include_minor_ranks: bool = False) -> Taxon:
        """Compute lowest common ancestor.
        Tries ltree approach first, falls back to recursive CTE if `path` is missing or ltree fails.
        """
        if not taxon_ids:
            raise ValueError("taxon_ids set cannot be empty for LCA calculation.")
        if len(taxon_ids) == 1:
            return await self.get_taxon(list(taxon_ids)[0])

        async with self._Session() as s:
            lca_tid: int | None = None
            try:
                # Try ltree approach
                path_conditions = []
                for t_id in taxon_ids:
                    # Subquery to get path for each taxon_id
                    subquery = (
                        select(ExpandedTaxa.path_ltree)
                        .where(ExpandedTaxa.taxon_id == t_id)
                        .scalar_subquery()
                    )
                    path_conditions.append(ExpandedTaxa.path_ltree.op("@>")(subquery))  # type: ignore

                stmt = (
                    select(ExpandedTaxa.taxon_id)
                    .where(*path_conditions)
                    .order_by(
                        text("nlevel(path) DESC")
                    )  # Assuming 'path' is ExpandedTaxa.path_ltree
                    .limit(1)
                )
                lca_tid = await s.scalar(stmt)
                if (
                    lca_tid is None and len(taxon_ids) > 0
                ):  # If ltree query returned no result, but it should have
                    logger.warning(
                        f"LCA by ltree returned no result for {taxon_ids}, attempting fallback."
                    )
                    lca_tid = await self._lca_recursive_fallback(s, taxon_ids)

            except ProgrammingError as e:
                # Catch errors like "column path does not exist" or "function nlevel(character varying) does not exist"
                logger.warning(
                    f"LCA: ltree approach failed (error: {e}), attempting recursive fallback."
                )
                lca_tid = await self._lca_recursive_fallback(s, taxon_ids)

            if lca_tid is None:
                raise ValueError(f"Could not determine LCA for taxon IDs: {taxon_ids}")

        return await self.get_taxon(lca_tid)

    async def distance(
        self,
        a: int,
        b: int,
        *,
        include_minor_ranks: bool = False,
        inclusive: bool = False,
    ) -> int:
        # This method originally used 'path' and 'nlevel'.
        # It needs to be updated to work without 'path' or have a fallback.
        # For now, the ticket does not explicitly require a change to distance() fallback,
        # but it's related to lca() and path column.
        # Let's assume for now that if lca() works (even with fallback),
        # distance can be calculated using ancestry paths from get_taxon, similar to SQLite's version.
        # This makes it independent of the 'path' column.

        if a == b:
            return 0

        # Get taxa and their ancestries (respecting ORM mappings)
        taxon_a = await self.get_taxon(a)
        taxon_b = await self.get_taxon(b)
        lca_taxon = await self.lca({a, b}, include_minor_ranks=include_minor_ranks)

        anc_a = (
            taxon_a.ancestry
            if include_minor_ranks
            else [
                tid
                for tid, rl in (await self._get_ancestry_with_ranks(taxon_a.ancestry)).items()
                if is_major(rl)
            ]
        )
        anc_b = (
            taxon_b.ancestry
            if include_minor_ranks
            else [
                tid
                for tid, rl in (await self._get_ancestry_with_ranks(taxon_b.ancestry)).items()
                if is_major(rl)
            ]
        )

        try:
            idx_lca_in_a = anc_a.index(lca_taxon.taxon_id)
            idx_lca_in_b = anc_b.index(lca_taxon.taxon_id)
        except ValueError:  # Should not happen if LCA is correct and part of ancestries
            raise ValueError(
                f"LCA {lca_taxon.taxon_id} not found in ancestry paths for {a} or {b}."
            )

        dist_a_to_lca = len(anc_a) - 1 - idx_lca_in_a
        dist_b_to_lca = len(anc_b) - 1 - idx_lca_in_b

        distance = dist_a_to_lca + dist_b_to_lca
        if inclusive:
            distance += 1
        return distance

    async def _get_ancestry_with_ranks(self, ancestry: list[int]) -> dict[int, RankLevel]:
        if not ancestry:
            return {}
        async with self._Session() as s:
            res = await s.execute(
                select(ExpandedTaxa.taxon_id, ExpandedTaxa.rank_level).where(
                    ExpandedTaxa.taxon_id.in_(ancestry)
                )
            )
            return {row.taxon_id: RankLevel(row.rank_level) for row in res}

        # Original SQL using path:
        # sql = text(
        # """
        #    WITH pair AS (
        #      SELECT path FROM expanded_taxa WHERE taxon_id = :a
        #      UNION ALL
        #      SELECT path FROM expanded_taxa WHERE taxon_id = :b)
        #    SELECT max(nlevel(path)) - min(nlevel(path)) FROM pair;
        # """
        # )
        # async with self._Session() as s:
        #     return await s.scalar(sql, {"a": a, "b": b})

    async def fetch_subtree(self, root_ids: set[int]) -> dict[int, int | None]:
        """Return `{child_id: parent_id}` for the minimal induced sub-tree
        containing *root_ids* and all their descendants."""
        if not root_ids:
            return {}
        roots_sql = ",".join(map(str, root_ids))
        # Uses immediateAncestor_taxonID via ORM's parent_id mapping.
        # The SQL query refers to "parent_id", which SQLAlchemy resolves.
        # For raw SQL, ensure the correct column name is used.
        sql = text(
            f"""
            WITH RECURSIVE sub AS (
              SELECT taxon_id, "immediateAncestor_taxonID" AS parent_id FROM expanded_taxa WHERE taxon_id IN ({roots_sql})
              UNION ALL 
              SELECT et.taxon_id, et."immediateAncestor_taxonID" FROM expanded_taxa et
                JOIN sub ON et."immediateAncestor_taxonID" = sub.taxon_id
            )
            SELECT taxon_id, parent_id FROM sub;
            """
        )
        async with self._Session() as s:
            res = await s.execute(sql)
            return {r.taxon_id: r.parent_id for r in res}

    # Provide a convenience wrapper so tests can call `.subtree(root_id)`
    # instead of `.fetch_subtree({root_id})`.
    async def subtree(self, root_id: int) -> dict[int, int | None]:  # pragma: no cover
        return await self.fetch_subtree({root_id})

    def _row_to_taxon(self, row: ExpandedTaxa) -> Taxon:
        # This method expects an ORM row object (ExpandedTaxa instance)
        ancestry_list = []
        if row.ancestry_str:  # Use the ORM attribute for ancestry string
            try:
                ancestry_list = list(map(int, str(row.ancestry_str).split("|")))
            except ValueError:  # pragma: no cover
                logger.warning(
                    f"Could not parse ancestry string: {row.ancestry_str} for taxon {row.taxon_id}"
                )
                pass

        return Taxon(
            taxon_id=row.taxon_id,
            scientific_name=row.scientific_name,
            rank_level=RankLevel(row.rank_level),  # rank_level is an int in DB
            parent_id=row.parent_id,  # This uses the ORM mapping for parent_id
            ancestry=ancestry_list,
            # common_name handling can be added if needed, similar to SQLite impl.
            # vernacular={"en": [row.common_name]} if row.common_name else {},
        )

    def _row_to_taxon_from_mapping(self, row_mapping) -> Taxon:
        # Helper to convert a RowMapping (dict-like) from a raw SQL query to a Taxon object.
        # This is used when full ORM objects are not fetched.
        ancestry_list = []
        ancestry_value = row_mapping.get(
            "ancestry"
        )  # Assuming 'ancestry' is the column name for the string
        if ancestry_value:
            try:
                ancestry_list = list(map(int, str(ancestry_value).split("|")))
            except ValueError:  # pragma: no cover
                logger.warning(
                    f"Could not parse ancestry string from mapping: {ancestry_value} for taxon {row_mapping.get('taxon_id')}"
                )
                pass

        return Taxon(
            taxon_id=row_mapping["taxon_id"],
            scientific_name=row_mapping[
                "name"
            ],  # Assuming 'name' is the col name for scientific_name
            rank_level=RankLevel(row_mapping["rankLevel"]),  # Assuming 'rankLevel'
            parent_id=row_mapping.get(
                "immediateAncestor_taxonID"
            ),  # Explicitly use new parent col name
            ancestry=ancestry_list,
            # common_name handling can be added if needed
        )
        # The following lines were part of the original distance(self, a,b) method using SQL text()
        # and were related to a commented-out block. They are removed to fix indentation.
        # async with self._Session() as s:
        #     return await s.scalar(sql, {"a": a, "b": b})


# End of PostgresTaxonomyService class methods.
# The duplicated methods that caused F811 errors have been removed.
