import asyncio
import sqlite3
from pathlib import Path

from typus.constants import RankLevel, is_major
from typus.models.taxon import Taxon
from typus.services.taxonomy import AbstractTaxonomyService

_FETCH_SUBTREE_SQL = """
WITH RECURSIVE subtree_nodes(tid, tpid) AS (
    SELECT "taxonID", "immediateAncestor_taxonID" FROM expanded_taxa WHERE "taxonID" IN ({})
    UNION ALL
    SELECT et."taxonID", et."immediateAncestor_taxonID" FROM expanded_taxa et
    JOIN subtree_nodes sn ON et."immediateAncestor_taxonID" = sn.tid
)
SELECT tid, tpid FROM subtree_nodes;
"""
assert "immediateAncestor_taxonID" in _FETCH_SUBTREE_SQL


class SQLiteTaxonomyService(AbstractTaxonomyService):
    """
    Implementation of AbstractTaxonomyService backed by SQLite fixture database.
    """

    _rank_cache: dict[int, RankLevel] = {}  # For caching taxon_id -> RankLevel

    async def _ensure_rank_cache_for_ids(self, taxon_ids: set[int]):
        """Ensures rank_level for given taxon_ids are in _rank_cache."""
        # Query SQLite for rankLevel of missing IDs and populate _rank_cache
        ids_to_cache = taxon_ids - set(self._rank_cache.keys())
        if not ids_to_cache:
            return

        loop = asyncio.get_running_loop()
        query = f'SELECT "taxonID", "rankLevel" FROM "expanded_taxa" WHERE "taxonID" IN ({",".join("?" * len(ids_to_cache))})'

        rows = await loop.run_in_executor(
            None, lambda: self._conn.execute(query, tuple(ids_to_cache)).fetchall()
        )

        for row in rows:
            self._rank_cache[row["taxonID"]] = RankLevel(int(row["rankLevel"]))

    def __init__(self, path: str | Path | None = None):
        if path is None:
            path = Path(__file__).parent.parent.parent / "tests" / "expanded_taxa_sample.sqlite"
            if not path.exists():
                sample_tsv = (
                    Path(__file__).parent.parent.parent
                    / "tests"
                    / "sample_tsv"
                    / "expanded_taxa_sample.tsv"
                )
                from .sqlite_loader import load_expanded_taxa

                load_expanded_taxa(path, tsv_path=sample_tsv)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    async def get_taxon(self, taxon_id: int) -> Taxon:
        loop = asyncio.get_running_loop()
        sql = """
            SELECT "taxonID", "name", "rankLevel",
                   "immediateAncestor_taxonID", "commonName", "taxonActive"
            FROM "expanded_taxa" WHERE "taxonID"=?
        """
        row = await loop.run_in_executor(
            None,
            lambda: self._conn.execute(sql, (taxon_id,)).fetchone(),
        )
        if row is None:
            raise KeyError(taxon_id)

        # Populate rank cache
        if row["taxonID"] not in self._rank_cache:
            self._rank_cache[row["taxonID"]] = RankLevel(int(row["rankLevel"]))

        # Return with empty ancestry list - computed on demand if needed
        return Taxon(
            taxon_id=row["taxonID"],
            scientific_name=row["name"],
            rank_level=RankLevel(int(row["rankLevel"])),
            parent_id=row["immediateAncestor_taxonID"],
            ancestry=[],  # Empty - matches PostgreSQL behavior
            vernacular={"en": [row["commonName"]]} if row["commonName"] else {},
        )

    async def children(self, taxon_id: int, *, depth: int = 1) -> list[Taxon]:
        loop = asyncio.get_running_loop()
        # Recursive CTE using "immediateAncestor_taxonID"
        query = """
        WITH RECURSIVE sub(tid, lvl) AS (
            SELECT "taxonID", 0 FROM expanded_taxa WHERE "taxonID" = ?
            UNION ALL
            SELECT et."taxonID", sub.lvl + 1 FROM expanded_taxa et
            JOIN sub ON et."immediateAncestor_taxonID" = sub.tid
            WHERE sub.lvl < ?
        )
        SELECT tid FROM sub WHERE lvl > 0;
        """
        child_ids_tuples = await loop.run_in_executor(
            None, lambda: self._conn.execute(query, (taxon_id, depth)).fetchall()
        )
        child_taxa = [
            await self.get_taxon(child_id_tuple[0]) for child_id_tuple in child_ids_tuples
        ]
        return child_taxa

    async def _get_filtered_ancestry(self, taxon_id: int, include_minor_ranks: bool) -> list[int]:
        """Build ancestry by traversing parent relationships."""
        loop = asyncio.get_running_loop()
        ancestry = [taxon_id]
        current_id = taxon_id
        
        # Build full ancestry by following parent links
        while True:
            parent_sql = """
                SELECT "immediateAncestor_taxonID", "rankLevel"
                FROM "expanded_taxa" WHERE "taxonID"=?
            """
            row = await loop.run_in_executor(
                None,
                lambda cid=current_id: self._conn.execute(parent_sql, (cid,)).fetchone(),
            )
            if row and row["immediateAncestor_taxonID"]:
                parent_id = row["immediateAncestor_taxonID"]
                ancestry.insert(0, parent_id)
                # Cache rank level
                if parent_id not in self._rank_cache:
                    parent_rank_sql = 'SELECT "rankLevel" FROM "expanded_taxa" WHERE "taxonID"=?'
                    parent_rank_row = await loop.run_in_executor(
                        None,
                        lambda pid=parent_id: self._conn.execute(parent_rank_sql, (pid,)).fetchone(),
                    )
                    if parent_rank_row:
                        self._rank_cache[parent_id] = RankLevel(int(parent_rank_row["rankLevel"]))
                current_id = parent_id
            else:
                break
        
        if include_minor_ranks:
            return ancestry
        
        # Filter for major ranks only
        major_ancestry = [
            tid for tid in ancestry if is_major(self._rank_cache.get(tid, RankLevel.L100))
        ]
        return major_ancestry

    async def lca(self, taxon_ids: set[int], *, include_minor_ranks: bool = False) -> Taxon:
        """Compute lowest common ancestor using efficient algorithms.
        
        For major ranks only: Uses expanded L*_taxonID columns.
        For all ranks: Uses ancestry traversal.
        """
        if not taxon_ids:
            raise ValueError("taxon_ids set cannot be empty for LCA calculation.")
        if len(taxon_ids) == 1:
            return await self.get_taxon(list(taxon_ids)[0])

        loop = asyncio.get_running_loop()
        
        if not include_minor_ranks:
            # Use expanded columns for major ranks
            # From MAJOR_LEVELS: 10=species, 20=genus, 30=tribe, 40=order, 50=class, 60=subphylum, 70=kingdom
            major_levels = [10, 20, 30, 40, 50, 60, 70]  # species to kingdom
            
            # Build query to fetch major rank columns
            taxon_list = list(taxon_ids)
            placeholders = ",".join(["?" for _ in taxon_list])
            
            # Build column list
            column_names = []
            for level in major_levels:
                column_names.append(f'"L{level}_taxonID"')
            column_names.append('"taxonID"')
            
            columns_str = ", ".join(column_names)
            
            sql = f"""
                SELECT {columns_str}
                FROM expanded_taxa
                WHERE "taxonID" IN ({placeholders})
            """
            
            rows = await loop.run_in_executor(
                None,
                lambda: self._conn.execute(sql, taxon_list).fetchall(),
            )
            
            if len(rows) != len(taxon_ids):
                raise ValueError(f"Some taxa not found: {taxon_ids}")
            
            # Find deepest common ancestor
            for level in major_levels:
                col_name = f"L{level}_taxonID"
                
                values_at_level = set()
                for row in rows:
                    val = row[col_name]
                    if val is not None:
                        values_at_level.add(val)
                
                # If all taxa have the same non-null value, that's our LCA
                if len(values_at_level) == 1:
                    lca_id = values_at_level.pop()
                    return await self.get_taxon(lca_id)
                    
            raise ValueError(f"No common ancestor found for taxon IDs: {taxon_ids}")
            
        else:
            # Use ancestry traversal for all ranks
            ancestries = []
            for tid in taxon_ids:
                anc_path = await self._get_filtered_ancestry(tid, include_minor_ranks)
                ancestries.append(anc_path)

            if not ancestries:
                return await self.get_taxon(list(taxon_ids)[0])

            common_prefix = ancestries[0]
            for i in range(1, len(ancestries)):
                current_common = []
                for j in range(min(len(common_prefix), len(ancestries[i]))):
                    if common_prefix[j] == ancestries[i][j]:
                        current_common.append(common_prefix[j])
                    else:
                        break
                common_prefix = current_common

            if not common_prefix:
                raise ValueError(f"No common ancestor found for taxon IDs: {taxon_ids}")

            # Get the deepest common ancestor
            for lca_id in reversed(common_prefix):
                try:
                    return await self.get_taxon(lca_id)
                except KeyError:
                    continue

            raise ValueError(f"No valid LCA found in the database for taxon IDs: {taxon_ids}")

    async def distance(
        self, a: int, b: int, *, include_minor_ranks: bool = False, inclusive: bool = False
    ) -> int:
        """Calculate the taxonomic distance between two taxa.
        
        Efficiently counts steps via parent traversal without building full ancestry.
        """
        if a == b:
            return 0

        # Find the LCA first
        lca_taxon = await self.lca({a, b}, include_minor_ranks=include_minor_ranks)
        lca_id = lca_taxon.taxon_id
        
        # If one is the LCA of the other, calculate direct distance
        if lca_id == a:
            dist = await self._distance_to_ancestor(b, a, include_minor_ranks)
            return dist + (1 if inclusive else 0)
        if lca_id == b:
            dist = await self._distance_to_ancestor(a, b, include_minor_ranks)
            return dist + (1 if inclusive else 0)
        
        # Calculate distance from each to LCA
        dist_a = await self._distance_to_ancestor(a, lca_id, include_minor_ranks)
        dist_b = await self._distance_to_ancestor(b, lca_id, include_minor_ranks)
        
        distance = dist_a + dist_b
        if inclusive:
            distance += 1
        return distance
    
    async def _distance_to_ancestor(
        self, descendant: int, ancestor: int, include_minor_ranks: bool
    ) -> int:
        """Count steps from descendant to ancestor."""
        loop = asyncio.get_running_loop()
        
        if include_minor_ranks:
            parent_col = '"immediateAncestor_taxonID"'
        else:
            parent_col = '"immediateMajorAncestor_taxonID"'
        
        # Use recursive CTE to count steps
        sql = f"""
            WITH RECURSIVE path AS (
                SELECT "taxonID", {parent_col} as parent, 0 as distance
                FROM expanded_taxa WHERE "taxonID" = ?
                UNION ALL
                SELECT p.parent, et.{parent_col}, p.distance + 1
                FROM path p
                JOIN expanded_taxa et ON et."taxonID" = p.parent
                WHERE p.parent IS NOT NULL
            )
            SELECT distance + 1 as distance FROM path WHERE parent = ?
        """
        
        result = await loop.run_in_executor(
            None,
            lambda: self._conn.execute(sql, (descendant, ancestor)).fetchone(),
        )
        
        return result["distance"] if result else 0

    async def fetch_subtree(self, root_ids: set[int]) -> dict[int, int | None]:
        if not root_ids:
            return {}

        loop = asyncio.get_running_loop()

        placeholders = ",".join("?" * len(root_ids))
        query = _FETCH_SUBTREE_SQL.format(placeholders)

        rows = await loop.run_in_executor(
            None, lambda: self._conn.execute(query, tuple(root_ids)).fetchall()
        )

        # Convert sqlite3.Row to dict
        return {row["tid"]: row["tpid"] for row in rows}

    async def subtree(self, root_id: int) -> dict[int, int | None]:  # pragma: no cover
        return await self.fetch_subtree({root_id})
