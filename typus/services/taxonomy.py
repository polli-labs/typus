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
            # Note: We don't use undefer for ancestry_str since it may not exist in all databases
            # TODO: ancestry_str is deprecated, we need to rebuild anything that uses it to instead use immediate major/minor ancestor cols for traversal, or ancestral cols if requried rank level for the query is known
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
              SELECT *, 0 AS lvl FROM expanded_taxa WHERE "taxonID" = :tid
              UNION ALL
              SELECT et.*, sub.lvl + 1 FROM expanded_taxa et
                JOIN sub ON et."immediateAncestor_taxonID" = sub."taxonID"
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

    async def _lca_via_expanded_columns(self, s, taxon_ids: set[int]) -> int | None:
        """Efficient LCA using expanded L*_taxonID columns for major ranks."""
        # Major rank levels in descending order (deepest to shallowest)
        # From MAJOR_LEVELS: 10=species, 20=genus, 30=tribe, 40=order, 50=class, 60=subphylum, 70=kingdom
        major_levels = [10, 20, 30, 40, 50, 60, 70]  # species to kingdom
        
        # Build query to fetch all major rank columns for all taxa
        taxon_list = list(taxon_ids)
        placeholders = ",".join([f":tid{i}" for i in range(len(taxon_list))])
        
        # Build column list for major ranks
        column_names = []
        for level in major_levels:
            column_names.append(f'"L{level}_taxonID"')
        column_names.append('"taxonID"')
        
        columns_str = ", ".join(column_names)
        
        # Raw SQL to fetch expanded columns
        sql = text(f"""
            SELECT {columns_str}
            FROM expanded_taxa
            WHERE "taxonID" IN ({placeholders})
        """)
        
        # Create parameter dict
        params = {f"tid{i}": tid for i, tid in enumerate(taxon_list)}
        result = await s.execute(sql, params)
        rows = result.mappings().all()
        
        if len(rows) != len(taxon_ids):
            # Some taxa not found
            return None
            
        # Find deepest common ancestor by checking each level
        for level in major_levels:
            col_name = f"L{level}_taxonID"
            
            # Get the value at this level for all taxa
            values_at_level = set()
            for row in rows:
                val = row.get(col_name)
                if val is not None:
                    values_at_level.add(val)
            
            # If all taxa have the same non-null value at this level, that's our LCA
            if len(values_at_level) == 1:
                return values_at_level.pop()
        
        return None  # No common ancestor found

    async def _lca_recursive_fallback(self, s, taxon_ids: set[int]) -> int | None:
        """LCA implementation using recursive CTE for all ranks."""
        # Build the parts of the CTE
        # Anchor: select direct ancestors for each taxon_id
        anchor_parts = []
        for i, tid in enumerate(taxon_ids):
            anchor_parts.append(
                f'SELECT {tid} AS query_taxon_id, "taxonID" as taxon_id, "immediateAncestor_taxonID" AS parent_id, 0 AS lvl FROM expanded_taxa WHERE "taxonID" = {tid}'
            )
        anchor_sql = " UNION ALL ".join(anchor_parts)

        recursive_sql = f"""
            WITH RECURSIVE taxon_ancestors (query_taxon_id, taxon_id, parent_id, lvl) AS (
                {anchor_sql}
                UNION ALL
                SELECT ta.query_taxon_id, et."taxonID" as taxon_id, et."immediateAncestor_taxonID", ta.lvl + 1
                FROM expanded_taxa et
                JOIN taxon_ancestors ta ON et."taxonID" = ta.parent_id
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
        """Compute lowest common ancestor using expanded taxonomy columns.
        
        For major ranks only: Uses indexed L*_taxonID columns for O(1) lookup.
        For all ranks: Uses recursive CTE traversal.
        """
        if not taxon_ids:
            raise ValueError("taxon_ids set cannot be empty for LCA calculation.")
        if len(taxon_ids) == 1:
            return await self.get_taxon(list(taxon_ids)[0])

        async with self._Session() as s:
            if not include_minor_ranks:
                # Optimized approach using expanded columns for major ranks
                lca_tid = await self._lca_via_expanded_columns(s, taxon_ids)
            else:
                # Use recursive CTE for all ranks
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
        """Calculate taxonomic distance between two taxa.
        
        Uses recursive CTEs to count steps from each taxon to their LCA.
        Avoids building full ancestry paths for efficiency.
        """
        if a == b:
            return 0

        # First find the LCA
        lca_taxon = await self.lca({a, b}, include_minor_ranks=include_minor_ranks)
        lca_id = lca_taxon.taxon_id
        
        # If one taxon is the LCA, calculate direct distance
        if lca_id == a:
            return await self._distance_to_ancestor(b, a, include_minor_ranks) + (1 if inclusive else 0)
        if lca_id == b:
            return await self._distance_to_ancestor(a, b, include_minor_ranks) + (1 if inclusive else 0)
        
        # Calculate distance from each taxon to LCA using recursive CTEs
        async with self._Session() as s:
            if include_minor_ranks:
                # Count all steps using immediateAncestor_taxonID
                parent_col = '"immediateAncestor_taxonID"'
            else:
                # Count only major rank steps using immediateMajorAncestor_taxonID  
                parent_col = '"immediateMajorAncestor_taxonID"'
            
            # Query to count steps from taxon to ancestor
            distance_sql = text(f"""
                WITH RECURSIVE path AS (
                    SELECT "taxonID", {parent_col} as parent, 0 as distance
                    FROM expanded_taxa WHERE "taxonID" = :taxon_id
                    UNION ALL
                    SELECT p.parent, et.{parent_col}, p.distance + 1
                    FROM path p
                    JOIN expanded_taxa et ON et."taxonID" = p.parent
                    WHERE p.parent IS NOT NULL AND p.parent != :lca_id
                )
                SELECT MAX(distance) + 1 as distance FROM path WHERE parent = :lca_id
            """)
            
            # Get distance from a to LCA
            dist_a = await s.scalar(distance_sql, {"taxon_id": a, "lca_id": lca_id})
            if dist_a is None:
                dist_a = 0  # Direct child of LCA
                
            # Get distance from b to LCA  
            dist_b = await s.scalar(distance_sql, {"taxon_id": b, "lca_id": lca_id})
            if dist_b is None:
                dist_b = 0  # Direct child of LCA
                
        distance = dist_a + dist_b
        if inclusive:
            distance += 1
        return distance
    
    async def _distance_to_ancestor(
        self, descendant: int, ancestor: int, include_minor_ranks: bool
    ) -> int:
        """Calculate distance from descendant to a known ancestor."""
        async with self._Session() as s:
            if include_minor_ranks:
                parent_col = '"immediateAncestor_taxonID"'
            else:
                parent_col = '"immediateMajorAncestor_taxonID"'
                
            sql = text(f"""
                WITH RECURSIVE path AS (
                    SELECT "taxonID", {parent_col} as parent, 0 as distance
                    FROM expanded_taxa WHERE "taxonID" = :descendant
                    UNION ALL
                    SELECT p.parent, et.{parent_col}, p.distance + 1
                    FROM path p
                    JOIN expanded_taxa et ON et."taxonID" = p.parent
                    WHERE p.parent IS NOT NULL
                )
                SELECT distance + 1 as distance FROM path WHERE parent = :ancestor
            """)
            
            dist = await s.scalar(sql, {"descendant": descendant, "ancestor": ancestor})
            return dist if dist is not None else 0

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
              SELECT "taxonID" as taxon_id, "immediateAncestor_taxonID" AS parent_id FROM expanded_taxa WHERE "taxonID" IN ({roots_sql})
              UNION ALL 
              SELECT et."taxonID" as taxon_id, et."immediateAncestor_taxonID" FROM expanded_taxa et
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
        """Convert ORM row to Taxon model.
        
        Note: ancestry list is always empty as modern databases don't have ancestry column.
        The Taxon model can compute ancestry if needed via its property.
        """
        common_name = getattr(row, "common_name", None) if hasattr(row, "common_name") else None
        vernacular = {}
        if common_name and isinstance(common_name, str):
            vernacular = {"en": [common_name]}
        
        return Taxon(
            taxon_id=row.taxon_id,
            scientific_name=row.scientific_name,
            rank_level=RankLevel(row.rank_level),
            parent_id=row.parent_id,  # Maps to immediateAncestor_taxonID
            ancestry=[],  # Empty - computed on demand if needed
            vernacular=vernacular,
        )

    def _row_to_taxon_from_mapping(self, row_mapping) -> Taxon:
        """Convert a RowMapping from raw SQL to Taxon model.
        
        Note: ancestry list is always empty as modern databases don't have ancestry column.
        """
        common_name = row_mapping.get("commonName")
        vernacular = {}
        if common_name and isinstance(common_name, str):
            vernacular = {"en": [common_name]}
            
        return Taxon(
            taxon_id=row_mapping.get("taxon_id") or row_mapping.get("taxonID"),
            scientific_name=row_mapping["name"],
            rank_level=RankLevel(row_mapping["rankLevel"]),
            parent_id=row_mapping.get("immediateAncestor_taxonID"),
            ancestry=[],  # Empty - computed on demand if needed
            vernacular=vernacular,
        )
        # The following lines were part of the original distance(self, a,b) method using SQL text()
        # and were related to a commented-out block. They are removed to fix indentation.
        # async with self._Session() as s:
        #     return await s.scalar(sql, {"a": a, "b": b})


# End of PostgresTaxonomyService class methods.
# The duplicated methods that caused F811 errors have been removed.
