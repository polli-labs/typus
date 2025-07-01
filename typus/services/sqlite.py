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
        # Uses "immediateAncestor_taxonID" as per new schema plan for fixtures
        # The ORM handles mapping ExpandedTaxa.parent_id to this.
        # For raw SQL, we need to use the actual column name that will be in the fixture.
        # The plan is to make gen_fixture_sqlite.py write "immediateAncestor_taxonID".
        sql = """
            SELECT "taxonID", "name", "rankLevel",
                   "immediateAncestor_taxonID", "ancestry", "commonName", "taxonActive"
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

        ancestry_list = []
        # Note: `ancestry` column is deprecated. Usage should be reviewed.
        if row["ancestry"]:
            try:
                ancestry_list = list(map(int, str(row["ancestry"]).split("|")))
            except ValueError:  # pragma: no cover
                pass  # Should not happen with well-formed fixture

        return Taxon(
            taxon_id=row["taxonID"],
            scientific_name=row["name"],
            rank_level=RankLevel(int(row["rankLevel"])),
            parent_id=row["immediateAncestor_taxonID"],  # Read directly from the new column name
            ancestry=ancestry_list,
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
        taxon = await self.get_taxon(taxon_id)
        if include_minor_ranks:
            return list(taxon.ancestry)

        # For major_ranks_only, filter the ancestry list
        # Ensure rank_cache is populated for all ancestor IDs
        ids_to_cache = set(taxon.ancestry) - set(self._rank_cache.keys())
        if ids_to_cache:
            loop = asyncio.get_running_loop()
            query = f'SELECT "taxonID", "rankLevel" FROM "expanded_taxa" WHERE "taxonID" IN ({",".join("?" * len(ids_to_cache))})'
            rows = await loop.run_in_executor(
                None, lambda: self._conn.execute(query, tuple(ids_to_cache)).fetchall()
            )
            for row in rows:
                self._rank_cache[row["taxonID"]] = RankLevel(int(row["rankLevel"]))

        major_ancestry = [
            tid for tid in taxon.ancestry if is_major(self._rank_cache.get(tid, RankLevel.L100))
        ]
        return major_ancestry

    async def lca(self, taxon_ids: set[int], *, include_minor_ranks: bool = False) -> Taxon:
        if not taxon_ids:
            raise ValueError("taxon_ids set cannot be empty for LCA calculation.")
        if len(taxon_ids) == 1:
            return await self.get_taxon(list(taxon_ids)[0])

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
            # This means no common root, which shouldn't happen if 'Life' is an ancestor.
            # Fallback or error. For tests, this implies data issue or algorithm error.
            raise ValueError(f"No common ancestor found for taxon IDs: {taxon_ids}")

        # Try to get the LCA taxon starting from the end of the common prefix
        # and moving backwards until we find a taxon that exists in the database
        for lca_id in reversed(common_prefix):
            try:
                return await self.get_taxon(lca_id)
            except KeyError:
                continue

        # If we couldn't find any common ancestor in the database, raise an error
        raise ValueError(f"No valid LCA found in the database for taxon IDs: {taxon_ids}")

    async def distance(
        self, a: int, b: int, *, include_minor_ranks: bool = False, inclusive: bool = False
    ) -> int:
        """Calculate the taxonomic distance (number of steps) between two taxa.

        The distance is the total number of edges in the path between two taxa,
        calculated as the sum of the distances from each taxon to their lowest common ancestor.

        For taxa that are directly related (one is an ancestor of the other), the distance
        is simply the number of steps between them.

        For identical taxa, the distance is 0.
        """
        # Identity check - if the same taxon, distance is 0
        if a == b:
            return 0

        # Find the lowest common ancestor
        lca_taxon = await self.lca({a, b}, include_minor_ranks=include_minor_ranks)

        # Get the ancestry paths for both taxa
        anc_a = await self._get_filtered_ancestry(a, include_minor_ranks)
        anc_b = await self._get_filtered_ancestry(b, include_minor_ranks)

        # Find the position of the LCA in each ancestry path
        try:
            idx_lca_in_a = anc_a.index(lca_taxon.taxon_id)
            idx_lca_in_b = anc_b.index(lca_taxon.taxon_id)
        except ValueError:
            raise ValueError(
                f"LCA {lca_taxon.taxon_id} not found in ancestry paths for {a} or {b}."
            )

        # Calculate the distance from each taxon to the LCA
        # The distance is the number of steps/edges, which is (len(path_segment) - 1)
        # where path_segment is the part of the ancestry from the taxon to the LCA (inclusive)
        dist_a_to_lca = len(anc_a) - 1 - idx_lca_in_a
        dist_b_to_lca = len(anc_b) - 1 - idx_lca_in_b

        distance = dist_a_to_lca + dist_b_to_lca
        if inclusive:
            distance += 1
        return distance

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
