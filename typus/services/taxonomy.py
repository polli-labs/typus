from __future__ import annotations

import abc

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ..constants import RankLevel
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
    async def lca(self, taxon_ids: set[int]) -> Taxon: ...

    @abc.abstractmethod
    async def distance(self, a: int, b: int) -> int: ...


class PostgresTaxonomyService(AbstractTaxonomyService):
    """Async service backed by `expanded_taxa` materialised view."""

    def __init__(self, dsn: str):
        self._engine = create_async_engine(dsn, pool_pre_ping=True)
        self._Session = async_sessionmaker(self._engine, expire_on_commit=False)

    async def get_taxon(self, taxon_id: int) -> Taxon:
        async with self._Session() as s:
            row = await s.scalar(select(ExpandedTaxa).where(ExpandedTaxa.taxon_id == taxon_id))
            if row is None:
                raise KeyError(taxon_id)
            return self._row_to_taxon(row)

    async def children(self, taxon_id: int, *, depth: int = 1):
        sql = text(
            """
            WITH RECURSIVE sub AS (
              SELECT *, 0 AS lvl FROM expanded_taxa WHERE taxon_id = :tid
              UNION ALL
              SELECT et.*, sub.lvl + 1 FROM expanded_taxa et
                JOIN sub ON et.parent_id = sub.taxon_id
              WHERE sub.lvl < :d )
            SELECT * FROM sub WHERE lvl > 0;
            """
        )
        async with self._Session() as s:
            res = await s.execute(sql, {"tid": taxon_id, "d": depth})
            for row in res:
                yield self._row_to_taxon(row)

    async def lca(self, taxon_ids: set[int]) -> Taxon:
        """Compute lowest common ancestor using ltree `@>` operator."""
        path_expr = " & ".join(
            f"path @> (SELECT path FROM expanded_taxa WHERE taxon_id = {t})" for t in taxon_ids
        )
        sql = text(
            f"SELECT taxon_id FROM expanded_taxa WHERE {path_expr} ORDER BY nlevel(path) DESC LIMIT 1"
        )
        async with self._Session() as s:
            tid = await s.scalar(sql)
        return await self.get_taxon(tid)

    async def distance(self, a: int, b: int) -> int:
        sql = text(
            """
            WITH pair AS (
              SELECT path FROM expanded_taxa WHERE taxon_id = :a
              UNION ALL
              SELECT path FROM expanded_taxa WHERE taxon_id = :b)
            SELECT max(nlevel(path)) - min(nlevel(path)) FROM pair;
            """
        )
        async with self._Session() as s:
            return await s.scalar(sql, {"a": a, "b": b})

    async def fetch_subtree(self, root_ids: set[int]) -> dict[int, int | None]:
        """Return `{child_id: parent_id}` for the minimal induced sub-tree
        containing *root_ids* and all their descendants."""
        if not root_ids:
            return {}
        roots_sql = ",".join(map(str, root_ids))
        sql = text(
            f"""
            WITH RECURSIVE sub AS (
              SELECT taxon_id, parent_id FROM expanded_taxa WHERE taxon_id IN ({roots_sql})
              UNION ALL 
              SELECT et.taxon_id, et.parent_id FROM expanded_taxa et 
                JOIN sub ON et.parent_id = sub.taxon_id
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

    def _row_to_taxon(self, row) -> Taxon:
        return Taxon(
            taxon_id=row.taxon_id,
            scientific_name=row.scientific_name,
            rank_level=RankLevel(row.rank_level),
            parent_id=row.parent_id,
            ancestry=list(map(int, row.ancestry.split("|"))),
        )
