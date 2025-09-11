import asyncio
import sqlite3
from pathlib import Path
from typing import List, Set, Tuple

from rapidfuzz import fuzz

from ...constants import RankLevel, is_major
from ...models.taxon import Taxon
from .abstract import AbstractTaxonomyService

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
                from ..sqlite_loader import load_expanded_taxa

                load_expanded_taxa(path, tsv_path=sample_tsv)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    async def _expanded_ancestry_pairs(self, taxon_id: int) -> list[tuple[int, RankLevel]]:
        """Return ancestry (root→self) as (taxon_id, RankLevel) pairs using expanded columns.

        Works even if intermediate ancestors are absent as rows in the fixture DB.
        """
        loop = asyncio.get_running_loop()
        row = await loop.run_in_executor(
            None,
            lambda: self._conn.execute(
                'SELECT * FROM "expanded_taxa" WHERE "taxonID"=?', (taxon_id,)
            ).fetchone(),
        )
        if row is None:
            raise KeyError(taxon_id)

        pairs: list[tuple[int, RankLevel]] = []
        levels_desc = sorted([lvl for lvl in RankLevel], key=lambda r: int(r.value), reverse=True)
        for lvl in levels_desc:
            if lvl.value == 335:
                prefix = "L33_5"
            elif lvl.value == 345:
                prefix = "L34_5"
            else:
                prefix = f"L{int(lvl.value)}"
            col = f"{prefix}_taxonID"
            try:
                if col in row.keys():
                    val = row[col]
                    if val is not None:
                        pairs.append((int(val), lvl))
            except Exception:
                pass
        # Append self at the end
        try:
            self_lvl = RankLevel(int(row["rankLevel"]))
        except Exception:
            self_lvl = RankLevel.L100
        pairs.append((int(row["taxonID"]), self_lvl))
        # Deduplicate preserving order
        seen: set[int] = set()
        out: list[tuple[int, RankLevel]] = []
        for tid, lvl in pairs:
            if tid not in seen:
                out.append((tid, lvl))
                seen.add(tid)
        return out

    async def get_taxon(self, taxon_id: int) -> Taxon:
        loop = asyncio.get_running_loop()
        row = await loop.run_in_executor(
            None,
            lambda: self._conn.execute(
                'SELECT * FROM "expanded_taxa" WHERE "taxonID"=?', (taxon_id,)
            ).fetchone(),
        )
        if row is None:
            raise KeyError(taxon_id)

        if row["taxonID"] not in self._rank_cache:
            self._rank_cache[row["taxonID"]] = RankLevel(int(row["rankLevel"]))

        pairs = await self._expanded_ancestry_pairs(int(row["taxonID"]))
        ancestry_path = [tid for (tid, _lvl) in pairs]

        return Taxon(
            taxon_id=row["taxonID"],
            scientific_name=row["name"],
            rank_level=RankLevel(int(row["rankLevel"])),
            parent_id=row["immediateAncestor_taxonID"],
            ancestry=ancestry_path,
            vernacular={"en": [row["commonName"]]} if row["commonName"] else {},
        )

    async def children(self, taxon_id: int, *, depth: int = 1) -> list[Taxon]:
        loop = asyncio.get_running_loop()
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

    async def children_list(self, taxon_id: int, *, depth: int = 1) -> list[Taxon]:
        return await self.children(taxon_id, depth=depth)

    async def _get_filtered_ancestry(self, taxon_id: int, include_minor_ranks: bool) -> list[int]:
        """Ancestry from expanded columns; filter to major ranks if requested."""
        pairs = await self._expanded_ancestry_pairs(taxon_id)
        if include_minor_ranks:
            return [tid for (tid, _lvl) in pairs]
        return [tid for (tid, lvl) in pairs if is_major(lvl)]

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
            major_levels = [10, 20, 30, 40, 50, 60, 70]
            taxon_list = list(taxon_ids)
            placeholders = ",".join(["?" for _ in taxon_list])
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

            for level in major_levels:
                col_name = f"L{level}_taxonID"
                vals = [row[col_name] for row in rows]
                if any(v is None for v in vals):
                    continue
                if len(set(vals)) == 1:
                    return await self.get_taxon(vals[0])

            raise ValueError(f"No common ancestor found for taxon IDs: {taxon_ids}")

        else:
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

            for lca_id in reversed(common_prefix):
                try:
                    return await self.get_taxon(lca_id)
                except KeyError:
                    continue

            raise ValueError(f"No valid LCA found in the database for taxon IDs: {taxon_ids}")

    async def distance(
        self,
        a: int,
        b: int,
        *,
        include_minor_ranks: bool = False,
        inclusive: bool = False,
    ) -> int:
        """Calculate the taxonomic distance between two taxa.

        Efficiently counts steps using expanded ancestry lists for minor ranks
        and SQL recursive counting for major ranks only.
        """
        if a == b:
            return 0

        if include_minor_ranks:
            anc_a = await self._get_filtered_ancestry(a, include_minor_ranks=True)
            anc_b = await self._get_filtered_ancestry(b, include_minor_ranks=True)

            i = 0
            while i < len(anc_a) and i < len(anc_b) and anc_a[i] == anc_b[i]:
                i += 1
            dist_a = len(anc_a) - i
            dist_b = len(anc_b) - i
            distance = dist_a + dist_b
            if inclusive:
                distance += 1
            return distance

        lca_taxon = await self.lca({a, b}, include_minor_ranks=False)
        lca_id = lca_taxon.taxon_id
        if lca_id == a:
            dist = await self._distance_to_ancestor(b, a, include_minor_ranks=False)
            return dist + (1 if inclusive else 0)
        if lca_id == b:
            dist = await self._distance_to_ancestor(a, b, include_minor_ranks=False)
            return dist + (1 if inclusive else 0)
        dist_a = await self._distance_to_ancestor(a, lca_id, include_minor_ranks=False)
        dist_b = await self._distance_to_ancestor(b, lca_id, include_minor_ranks=False)
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

        return {row["tid"]: row["tpid"] for row in rows}

    async def subtree(self, root_id: int) -> dict[int, int | None]:  # pragma: no cover
        return await self.fetch_subtree({root_id})

    async def search_taxa(
        self,
        query: str,
        *,
        scopes: Set[str] | None = None,
        languages: Set[str] | None = None,
        match: str = "auto",
        fuzzy: bool = True,
        threshold: float = 0.8,
        limit: int = 20,
        rank_filter: Set[RankLevel] | None = None,
        with_scores: bool = False,
    ) -> List[Taxon] | List[Tuple[Taxon, float]]:
        scopes = scopes or {"scientific", "vernacular"}
        q_norm = query.strip()
        if not q_norm:
            return []

        loop = asyncio.get_running_loop()

        cols: List[str] = []
        if "scientific" in scopes:
            cols.append('"name"')
        if "vernacular" in scopes:
            cols.append('"commonName"')

        def make_predicates(mode: str) -> str:
            if mode == "exact":
                return " OR " + (" OR ".join([f"LOWER({c}) = ?" for c in cols]))
            elif mode == "prefix":
                return " OR " + (" OR ".join([f"LOWER({c}) LIKE ?" for c in cols]))
            elif mode == "substring":
                return " OR " + (" OR ".join([f"LOWER({c}) LIKE ?" for c in cols]))
            return ""

        def build_params(mode: str) -> List[str]:
            ql = q_norm.lower()
            if mode == "exact":
                return [ql for _ in cols]
            if mode == "prefix":
                return [ql + "%" for _ in cols]
            if mode == "substring":
                return [f"%{ql}%" for _ in cols]
            return []

        modes = ("exact", "prefix", "substring") if match == "auto" else (match,)

        rank_filter_sql = None
        if rank_filter:
            levels = sorted(int(r.value) for r in rank_filter)
            placeholders = ",".join(str(v) for v in levels)
            rank_filter_sql = f' AND "rankLevel" IN ({placeholders})'

        superset: List[sqlite3.Row] = []

        for mode in modes:
            pred = make_predicates(mode)
            if not pred.strip():
                continue
            params = build_params(mode)
            base_sql = (
                'SELECT DISTINCT "taxonID", "name", "rankLevel", "immediateAncestor_taxonID", "commonName" '
                "FROM expanded_taxa WHERE ("
                + pred[4:]
                + ') AND ("taxonActive" IS NULL OR "taxonActive"=1)'
            )
            if rank_filter_sql:
                base_sql += rank_filter_sql
            sup_limit = max(limit * 5, 50) if fuzzy else limit
            base_sql += f' ORDER BY "rankLevel" ASC, "name" ASC LIMIT {sup_limit}'
            rows = await loop.run_in_executor(
                None, lambda: self._conn.execute(base_sql, tuple(params)).fetchall()
            )
            superset = rows
            if rows:
                break

        def score_row(row: sqlite3.Row) -> float:
            cand = (row["name"] or "").strip()
            vname = (row["commonName"] or "").strip()
            base = cand if "scientific" in scopes else vname
            return float(fuzz.WRatio(q_norm.lower(), base.lower()) / 100.0)

        results: List[Tuple[Taxon, float]] = []
        for r in superset:
            tax = Taxon(
                taxon_id=r["taxonID"],
                scientific_name=r["name"],
                rank_level=RankLevel(int(r["rankLevel"])),
                parent_id=r["immediateAncestor_taxonID"],
                ancestry=[],
                vernacular={"en": [r["commonName"]]} if r["commonName"] else {},
            )
            sc = score_row(r) if fuzzy else 1.0
            if not fuzzy or sc >= threshold:
                results.append((tax, sc))

        results.sort(key=lambda t: (-t[1], t[0].rank_level.value, t[0].scientific_name))
        results = results[:limit]

        if with_scores:
            return results
        return [t for (t, _s) in results]

    async def get_many_batched(self, ids: set[int]) -> dict[int, Taxon]:
        if not ids:
            return {}
        loop = asyncio.get_running_loop()
        placeholders = ",".join(["?" for _ in ids])
        sql = f'SELECT "taxonID", "name", "rankLevel", "immediateAncestor_taxonID", "commonName" FROM expanded_taxa WHERE "taxonID" IN ({placeholders})'
        rows = await loop.run_in_executor(
            None, lambda: self._conn.execute(sql, tuple(ids)).fetchall()
        )
        out: dict[int, Taxon] = {}
        for r in rows:
            out[r["taxonID"]] = Taxon(
                taxon_id=r["taxonID"],
                scientific_name=r["name"],
                rank_level=RankLevel(int(r["rankLevel"])),
                parent_id=r["immediateAncestor_taxonID"],
                ancestry=await self.ancestors(r["taxonID"], include_minor_ranks=True),
                vernacular={"en": [r["commonName"]]} if r["commonName"] else {},
            )
        return out

    async def ancestors(self, taxon_id: int, *, include_minor_ranks: bool = True) -> list[int]:
        return await self._get_filtered_ancestry(taxon_id, include_minor_ranks)


__all__ = ["SQLiteTaxonomyService"]
