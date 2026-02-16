from __future__ import annotations

import asyncio
import logging
from typing import List, Sequence, Set, Tuple

from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from ...constants import RankLevel, is_major
from ...models.summary import TaxonSummary, TaxonTrailNode
from ...models.taxon import Taxon
from ...orm.expanded_taxa import ExpandedTaxa
from .abstract import AbstractTaxonomyService
from .common import (
    ancestry_pairs_from_mapping,
    col_prefix_for_level,
    filtered_ancestry_ids,
    score_taxon_match,
    taxon_from_search_row,
)
from .errors import BackendConnectionError, TaxonNotFoundError

logger = logging.getLogger(__name__)


class _ChildrenCursor:
    """Lazy children result that supports both ``await`` and ``async for``."""

    def __init__(self, svc: "PostgresTaxonomyService", taxon_id: int, depth: int):
        self._svc = svc
        self._taxon_id = taxon_id
        self._depth = depth
        self._task: asyncio.Task | None = None

    async def _fetch(self) -> list[Taxon]:
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
            async with self._svc._Session() as s:
                res = await s.execute(sql, {"tid": self._taxon_id, "d": self._depth})
                rows = res.mappings().all()
                return [self._svc._row_to_taxon_from_mapping(r) for r in rows]
        except SQLAlchemyError as exc:
            raise BackendConnectionError(
                f"Failed to fetch children from Postgres backend: {exc}"
            ) from exc

    async def _ensure(self) -> list[Taxon]:
        if self._task is None:
            self._task = asyncio.create_task(self._fetch())
        return await self._task

    def __await__(self):
        return self._ensure().__await__()

    def __aiter__(self):
        async def _gen():
            for item in await self._ensure():
                yield item

        return _gen()


class PostgresTaxonomyService(AbstractTaxonomyService):
    """Async service backed by `expanded_taxa` materialised view."""

    def __init__(self, dsn: str):
        # Use NullPool to avoid reusing connections across pytest event loops,
        # which can cause "Future attached to a different loop" with asyncpg.
        self._engine = create_async_engine(dsn, pool_pre_ping=True, poolclass=NullPool)
        self._Session = async_sessionmaker(self._engine, expire_on_commit=False)

    async def aclose(self) -> None:
        await self._engine.dispose()

    async def __aenter__(self) -> "PostgresTaxonomyService":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    async def get_taxon(self, taxon_id: int) -> Taxon:
        try:
            async with self._Session() as s:
                stmt = select(ExpandedTaxa.__table__).where(
                    ExpandedTaxa.__table__.c.taxonID == taxon_id
                )
                res = await s.execute(stmt)
                row = res.mappings().first()
        except SQLAlchemyError as exc:
            raise BackendConnectionError(f"Failed to query taxon {taxon_id}: {exc}") from exc

        if row is None:
            raise TaxonNotFoundError(taxon_id)
        return self._row_to_taxon_from_mapping(row)

    def children(self, taxon_id: int, *, depth: int = 1):
        return _ChildrenCursor(self, taxon_id, depth)

    async def children_list(self, taxon_id: int, *, depth: int = 1) -> List[Taxon]:
        return await self.children(taxon_id, depth=depth)

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
            vals: list[int] = []
            all_present = True
            for row in rows:
                val = row.get(col_name)
                if val is None:
                    all_present = False
                    break
                vals.append(val)
            if all_present and len(set(vals)) == 1:
                return vals[0]

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

        if not include_minor_ranks:
            try:
                async with self._Session() as s:
                    lca_tid = await self._lca_via_expanded_columns(s, taxon_ids)
                    if lca_tid is None:
                        lca_tid = await self._lca_recursive_fallback(s, taxon_ids)
            except SQLAlchemyError as exc:
                raise BackendConnectionError(
                    f"Failed to compute LCA from Postgres backend: {exc}"
                ) from exc

            if lca_tid is None:
                raise ValueError(f"Could not determine LCA for taxon IDs: {taxon_ids}")
            return await self.get_taxon(int(lca_tid))

        ancestries = [await self.ancestors(tid, include_minor_ranks=True) for tid in taxon_ids]
        common_prefix = ancestries[0]
        for anc in ancestries[1:]:
            current: list[int] = []
            for a, b in zip(common_prefix, anc):
                if a == b:
                    current.append(a)
                else:
                    break
            common_prefix = current
        if not common_prefix:
            raise ValueError(f"Could not determine LCA for taxon IDs: {taxon_ids}")
        return await self.get_taxon(common_prefix[-1])

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

        anc_a = await self.ancestors(a, include_minor_ranks=include_minor_ranks)
        anc_b = await self.ancestors(b, include_minor_ranks=include_minor_ranks)

        i = 0
        while i < len(anc_a) and i < len(anc_b) and anc_a[i] == anc_b[i]:
            i += 1
        dist_a = len(anc_a) - i
        dist_b = len(anc_b) - i
        distance = dist_a + dist_b
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
        except SQLAlchemyError as exc:
            raise BackendConnectionError(f"Failed to compute taxonomic distance: {exc}") from exc

    async def fetch_subtree(self, root_ids: set[int]) -> dict[int, int | None]:
        if not root_ids:
            return {}
        roots_sql = ",".join(str(tid) for tid in sorted(root_ids))
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
        except SQLAlchemyError as exc:
            raise BackendConnectionError(
                f"Failed to fetch subtree from Postgres backend: {exc}"
            ) from exc

    async def subtree(self, root_id: int) -> dict[int, int | None]:  # pragma: no cover
        return await self.fetch_subtree({root_id})

    def _row_to_taxon(self, row: ExpandedTaxa) -> Taxon:
        # Allow MagicMock rows in tests without full mapper
        if not hasattr(row, "__mapper__"):
            return taxon_from_search_row(
                {
                    "taxon_id": getattr(row, "taxon_id"),
                    "scientific_name": getattr(row, "scientific_name"),
                    "rank_level": getattr(row, "rank_level"),
                    "parent_id": getattr(row, "parent_id", None),
                    "commonName": None,
                },
                ancestry=[],
            )

        row_dict = {
            col.columns[0].name: getattr(row, col.key) for col in row.__mapper__.column_attrs
        }
        ancestry_ids = filtered_ancestry_ids(row_dict, include_minor_ranks=True)
        return taxon_from_search_row(
            row_dict,
            ancestry=ancestry_ids,
        )

    def _row_to_taxon_from_mapping(self, row_mapping) -> Taxon:
        row_dict = dict(row_mapping)
        ancestry_ids = filtered_ancestry_ids(row_dict, include_minor_ranks=True)
        return taxon_from_search_row(
            row_dict,
            ancestry=ancestry_ids,
        )

    async def ancestors(self, taxon_id: int, *, include_minor_ranks: bool = True) -> list[int]:
        """Return ancestry IDs root→self using expanded columns (works without ancestor rows)."""
        # Select explicitly to avoid optional columns like `path` if absent.
        sql = text(
            """
            SELECT * FROM expanded_taxa
            WHERE "taxonID" = :tid
            """
        )
        try:
            async with self._Session() as s:
                res = await s.execute(sql, {"tid": taxon_id})
                row = res.mappings().first()
        except SQLAlchemyError as exc:
            raise BackendConnectionError(
                f"Failed to fetch ancestry from Postgres backend: {exc}"
            ) from exc
        if row is None:
            raise TaxonNotFoundError(taxon_id)

        return filtered_ancestry_ids(dict(row), include_minor_ranks)

    async def taxon_summary(
        self,
        taxon_id: int,
        *,
        major_ranks_only: bool = True,
    ) -> TaxonSummary:
        try:
            async with self._Session() as s:
                res = await s.execute(
                    text('SELECT * FROM expanded_taxa WHERE "taxonID" = :tid'), {"tid": taxon_id}
                )
                row = res.mappings().first()
        except SQLAlchemyError as exc:
            raise BackendConnectionError(
                f"Failed to build taxon summary from Postgres backend: {exc}"
            ) from exc

        if row is None:
            raise TaxonNotFoundError(taxon_id)

        row_dict = dict(row)
        pairs = ancestry_pairs_from_mapping(row_dict)
        trail: list[TaxonTrailNode] = []

        for tid, lvl in pairs:
            if major_ranks_only and tid != taxon_id and not is_major(lvl):
                continue

            prefix = col_prefix_for_level(lvl)
            name_col = f"{prefix}_name"
            common_col = f"{prefix}_commonName"

            scientific_name = row_dict.get(name_col)
            vernacular_name = row_dict.get(common_col)

            if tid == taxon_id:
                scientific_name = scientific_name or row_dict.get("name")
                vernacular_name = vernacular_name or row_dict.get("commonName")

            if scientific_name is None:
                try:
                    taxon = await self.get_taxon(tid)
                    scientific_name = taxon.scientific_name
                    vernacular_name = vernacular_name or next(
                        iter(taxon.vernacular.get("en", [])), None
                    )
                except Exception:
                    scientific_name = str(tid)

            trail.append(
                TaxonTrailNode(
                    rank_level=lvl,
                    taxon_id=tid,
                    scientific_name=scientific_name,
                    vernacular_name=vernacular_name,
                )
            )

        return TaxonSummary(
            taxon_id=row_dict["taxonID"],
            scientific_name=row_dict["name"],
            vernacular_name=row_dict.get("commonName"),
            rank_level=RankLevel(int(row_dict["rankLevel"])),
            trail=trail,
        )

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
        except SQLAlchemyError as exc:
            raise BackendConnectionError(
                f"Failed to execute search against Postgres backend: {exc}"
            ) from exc

        for r in superset_rows:
            tax = taxon_from_search_row(
                r,
                ancestry=[],
            )
            sc = (
                score_taxon_match(
                    q_norm,
                    scientific_name=r.get("name"),
                    vernacular_name=r.get("commonName"),
                    scopes=scopes,
                )
                if fuzzy
                else 1.0
            )
            if not fuzzy or sc >= threshold:
                results_acc.append((tax, sc))

        results_acc.sort(key=lambda t: (-t[1], t[0].rank_level.value, t[0].scientific_name))
        results_acc = results_acc[:limit]
        if with_scores:
            return results_acc
        return [t for (t, _s) in results_acc]


__all__ = ["PostgresTaxonomyService"]
