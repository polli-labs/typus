from __future__ import annotations

import logging
from typing import List, Sequence, Set, Tuple

from rapidfuzz import fuzz
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from ...constants import RankLevel
from ...models.taxon import Taxon
from ...orm.expanded_taxa import ExpandedTaxa
from .abstract import AbstractTaxonomyService

logger = logging.getLogger(__name__)


class PostgresTaxonomyService(AbstractTaxonomyService):
    """Async service backed by `expanded_taxa` materialised view."""

    def __init__(self, dsn: str):
        # Use NullPool to avoid reusing connections across pytest event loops,
        # which can cause "Future attached to a different loop" with asyncpg.
        self._engine = create_async_engine(dsn, pool_pre_ping=True, poolclass=NullPool)
        self._Session = async_sessionmaker(self._engine, expire_on_commit=False)

    async def get_taxon(self, taxon_id: int) -> Taxon:
        try:
            async with self._Session() as s:
                stmt = select(ExpandedTaxa).where(ExpandedTaxa.taxon_id == taxon_id)
                row = await s.scalar(stmt)
                if row is None:
                    raise KeyError(taxon_id)
                return self._row_to_taxon(row)
        except Exception as e:  # pragma: no cover - test env skip
            raise RuntimeError(f"connection error: {e}") from e

    async def children(self, taxon_id: int, *, depth: int = 1):
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
        try:
            async with self._Session() as s:
                res = await s.execute(sql, {"tid": taxon_id, "d": depth})
                rows = res.mappings().all()
                for r in rows:
                    yield self._row_to_taxon_from_mapping(r)
        except Exception as e:  # pragma: no cover - test env skip
            raise RuntimeError(f"connection error: {e}") from e

    async def children_list(self, taxon_id: int, *, depth: int = 1) -> List[Taxon]:
        out: List[Taxon] = []
        async for t in self.children(taxon_id, depth=depth):
            out.append(t)
        return out

    async def _lca_via_expanded_columns(self, s, taxon_ids: set[int]) -> int | None:
        """Efficient LCA using expanded L*_taxonID columns for major ranks."""
        major_levels = [10, 20, 30, 40, 50, 60, 70]  # species to kingdom

        taxon_list = list(taxon_ids)
        placeholders = ",".join([f":tid{i}" for i in range(len(taxon_list))])

        column_names = []
        for level in major_levels:
            column_names.append(f'"L{level}_taxonID"')
        column_names.append('"taxonID"')

        columns_str = ", ".join(column_names)

        sql = text(f"""
            SELECT {columns_str}
            FROM expanded_taxa
            WHERE "taxonID" IN ({placeholders})
        """)

        params = {f"tid{i}": tid for i, tid in enumerate(taxon_list)}
        result = await s.execute(sql, params)
        rows = result.mappings().all()

        if len(rows) != len(taxon_ids):
            return None

        for level in major_levels:
            col_name = f"L{level}_taxonID"
            values_at_level = set()
            for row in rows:
                val = row.get(col_name)
                if val is not None:
                    values_at_level.add(val)
            if len(values_at_level) == 1:
                return values_at_level.pop()

        return None

    async def _lca_recursive_fallback(self, s, taxon_ids: set[int]) -> int | None:
        """LCA implementation using recursive CTE for all ranks."""
        anchor_parts = []
        for tid in taxon_ids:
            anchor_parts.append(
                'SELECT {tid} AS query_taxon_id, "taxonID" as taxon_id, "immediateAncestor_taxonID" AS parent_id, 0 AS lvl FROM expanded_taxa WHERE "taxonID" = {tid}'.format(
                    tid=tid
                )
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
            HAVING COUNT(DISTINCT query_taxon_id) = {len(taxon_ids)}
            ORDER BY MAX(lvl) DESC
            LIMIT 1
        """
        lca_tid = await s.scalar(text(recursive_sql))
        return lca_tid

    async def lca(self, taxon_ids: set[int], *, include_minor_ranks: bool = False) -> Taxon:
        if not taxon_ids:
            raise ValueError("taxon_ids set cannot be empty for LCA calculation.")
        if len(taxon_ids) == 1:
            return await self.get_taxon(list(taxon_ids)[0])

        try:
            async with self._Session() as s:
                if not include_minor_ranks:
                    lca_tid = await self._lca_via_expanded_columns(s, taxon_ids)
                else:
                    lca_tid = await self._lca_recursive_fallback(s, taxon_ids)

                if lca_tid is None:
                    raise ValueError(f"Could not determine LCA for taxon IDs: {taxon_ids}")
        except Exception as e:  # pragma: no cover - test env skip
            raise RuntimeError(f"connection error: {e}") from e

        return await self.get_taxon(lca_tid)

    async def distance(
        self,
        a: int,
        b: int,
        *,
        include_minor_ranks: bool = False,
        inclusive: bool = False,
    ) -> int:
        if a == b:
            return 0

        lca_taxon = await self.lca({a, b}, include_minor_ranks=include_minor_ranks)
        lca_id = lca_taxon.taxon_id

        if lca_id == a:
            return await self._distance_to_ancestor(b, a, include_minor_ranks) + (
                1 if inclusive else 0
            )
        if lca_id == b:
            return await self._distance_to_ancestor(a, b, include_minor_ranks) + (
                1 if inclusive else 0
            )

        try:
            async with self._Session() as s:
                if include_minor_ranks:
                    parent_col = '"immediateAncestor_taxonID"'
                else:
                    parent_col = '"immediateMajorAncestor_taxonID"'

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

                dist_a = await s.scalar(distance_sql, {"taxon_id": a, "lca_id": lca_id})
                if dist_a is None:
                    dist_a = 0

                dist_b = await s.scalar(distance_sql, {"taxon_id": b, "lca_id": lca_id})
                if dist_b is None:
                    dist_b = 0
        except Exception as e:  # pragma: no cover - test env skip
            raise RuntimeError(f"connection error: {e}") from e

        distance = (dist_a or 0) + (dist_b or 0)
        if inclusive:
            distance += 1
        return distance

    async def _distance_to_ancestor(
        self, descendant: int, ancestor: int, include_minor_ranks: bool
    ) -> int:
        try:
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
        except Exception as e:  # pragma: no cover - test env skip
            raise RuntimeError(f"connection error: {e}") from e

    async def fetch_subtree(self, root_ids: set[int]) -> dict[int, int | None]:
        if not root_ids:
            return {}
        roots_sql = ",".join(map(str, root_ids))
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
        try:
            async with self._Session() as s:
                res = await s.execute(sql)
                return {r.taxon_id: r.parent_id for r in res}
        except Exception as e:  # pragma: no cover - test env skip
            raise RuntimeError(f"connection error: {e}") from e

    async def subtree(self, root_id: int) -> dict[int, int | None]:  # pragma: no cover
        return await self.fetch_subtree({root_id})

    def _row_to_taxon(self, row: ExpandedTaxa) -> Taxon:
        common_name = getattr(row, "common_name", None) if hasattr(row, "common_name") else None
        vernacular = {}
        if common_name and isinstance(common_name, str):
            vernacular = {"en": [common_name]}

        return Taxon(
            taxon_id=row.taxon_id,
            scientific_name=row.scientific_name,
            rank_level=RankLevel(row.rank_level),
            parent_id=row.parent_id,
            ancestry=[],
            vernacular=vernacular,
        )

    def _row_to_taxon_from_mapping(self, row_mapping) -> Taxon:
        common_name = row_mapping.get("commonName")
        vernacular = {}
        if common_name and isinstance(common_name, str):
            vernacular = {"en": [common_name]}

        return Taxon(
            taxon_id=row_mapping.get("taxon_id") or row_mapping.get("taxonID"),
            scientific_name=row_mapping["name"],
            rank_level=RankLevel(row_mapping["rankLevel"]),
            parent_id=row_mapping.get("immediateAncestor_taxonID"),
            ancestry=[],
            vernacular=vernacular,
        )

    async def ancestors(self, taxon_id: int, *, include_minor_ranks: bool = True) -> list[int]:
        """Return ancestry as list of IDs from root to self.

        Uses recursive CTE on immediateAncestor_taxonID or immediateMajorAncestor_taxonID.
        """
        parent_col = (
            '"immediateAncestor_taxonID"'
            if include_minor_ranks
            else '"immediateMajorAncestor_taxonID"'
        )
        sql = text(f"""
            WITH RECURSIVE path AS (
                SELECT "taxonID", {parent_col} AS parent, 0 AS lvl
                FROM expanded_taxa WHERE "taxonID" = :tid
                UNION ALL
                SELECT et."taxonID", et.{parent_col}, p.lvl + 1
                FROM expanded_taxa et
                JOIN path p ON et."taxonID" = p.parent
                WHERE p.parent IS NOT NULL
            )
            SELECT "taxonID" FROM path
        """)
        try:
            async with self._Session() as s:
                rows = await s.execute(sql, {"tid": taxon_id})
                ids = [r.taxonID for r in rows]
        except Exception as e:  # pragma: no cover - test env skip
            raise RuntimeError(f"connection error: {e}") from e
        # rows is from self up to root; reverse to root->self and ensure self included
        out = list(reversed(ids))
        if not out or out[-1] != taxon_id:
            out.append(taxon_id)
        return out

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

        cols: List[str] = []
        if "scientific" in scopes:
            cols.append('"name"')
        if "vernacular" in scopes:
            cols.append('"commonName"')

        def make_predicates(mode: str) -> tuple[str, dict]:
            where_clauses: list[str] = []
            params: dict[str, str] = {}
            idx = 0

            def add_clause(fmt: str, val: str) -> None:
                nonlocal idx
                key = f"q{idx}"
                idx += 1
                for c in cols:
                    where_clauses.append(fmt.format(col=c, p=f":{key}_{len(where_clauses)}"))
                    params[f"{key}_{len(where_clauses) - 1}"] = val

            ql = q_norm.lower()
            if mode == "exact":
                for c in cols:
                    k = f"q{idx}"
                    idx += 1
                    where_clauses.append(f"LOWER({c}) = :{k}")
                    params[k] = ql
            elif mode == "prefix":
                for c in cols:
                    k = f"q{idx}"
                    idx += 1
                    where_clauses.append(f"LOWER({c}) LIKE :{k}")
                    params[k] = ql + "%"
            elif mode == "substring":
                for c in cols:
                    k = f"q{idx}"
                    idx += 1
                    where_clauses.append(f"LOWER({c}) LIKE :{k}")
                    params[k] = f"%{ql}%"
            return " OR ".join(where_clauses), params

        modes: Sequence[str] = ("exact", "prefix", "substring") if match == "auto" else (match,)

        rank_filter_sql = ""
        if rank_filter:
            levels = sorted(int(r.value) for r in rank_filter)
            placeholders = ",".join(str(v) for v in levels)
            rank_filter_sql = f' AND "rankLevel" IN ({placeholders})'

        results_acc: List[Tuple[Taxon, float]] = []
        try:
            async with self._Session() as s:
                superset_rows: list[dict] = []
                for mode in modes:
                    pred_sql, params = make_predicates(mode)
                    if not pred_sql:
                        continue
                    sup_limit = max(limit * 5, 50) if fuzzy else limit
                    base_sql = (
                        'SELECT DISTINCT "taxonID", "name", "rankLevel", "immediateAncestor_taxonID", "commonName" '
                        "FROM expanded_taxa "
                        f'WHERE ({pred_sql}) AND COALESCE("taxonActive", TRUE)'
                    )
                    base_sql += rank_filter_sql
                    base_sql += f' ORDER BY "rankLevel" ASC, "name" ASC LIMIT {sup_limit}'
                    res = await s.execute(text(base_sql), params)
                    superset_rows = [dict(r) for r in res.mappings().all()]
                    if superset_rows:
                        break
        except Exception as e:  # pragma: no cover - test env skip
            raise RuntimeError(f"connection error: {e}") from e

        def score_row(row: dict) -> float:
            cand = (row.get("name") or "").strip()
            vname = (row.get("commonName") or "").strip()
            base = cand if "scientific" in scopes else vname
            return float(fuzz.WRatio(q_norm.lower(), base.lower()) / 100.0)

        for r in superset_rows:
            tax = Taxon(
                taxon_id=r["taxonID"],
                scientific_name=r["name"],
                rank_level=RankLevel(int(r["rankLevel"])),
                parent_id=r["immediateAncestor_taxonID"],
                ancestry=[],
                vernacular={"en": [r["commonName"]]} if r.get("commonName") else {},
            )
            sc = score_row(r) if fuzzy else 1.0
            if not fuzzy or sc >= threshold:
                results_acc.append((tax, sc))

        results_acc.sort(key=lambda t: (-t[1], t[0].rank_level.value, t[0].scientific_name))
        results_acc = results_acc[:limit]
        if with_scores:
            return results_acc
        return [t for (t, _s) in results_acc]


__all__ = ["PostgresTaxonomyService"]
