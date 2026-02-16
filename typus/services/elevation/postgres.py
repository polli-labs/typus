from __future__ import annotations

from typing import Optional

from sqlalchemy import MetaData, Table, func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


class PostgresRasterElevation:
    def __init__(self, dsn: str, raster_table: str = "elevation_raster"):
        self._engine = create_async_engine(dsn, pool_pre_ping=True)
        self._Session = async_sessionmaker(self._engine)
        self._tbl_name = raster_table
        self._tbl: Optional[Table] = None

    async def _ensure_table(self) -> Table:
        if self._tbl is None:
            async with self._engine.begin() as conn:

                def _reflect(sync_conn):
                    md = MetaData()
                    Table(self._tbl_name, md, autoload_with=sync_conn)
                    self._tbl = md.tables[self._tbl_name]

                await conn.run_sync(_reflect)

        if self._tbl is None:  # pragma: no cover - defensive guard
            raise RuntimeError(f"Failed to reflect raster table {self._tbl_name!r}")

        return self._tbl

    async def elevation(self, lat: float, lon: float) -> Optional[float]:
        async with self._Session() as s:
            tbl = await self._ensure_table()
            point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
            stmt = (
                select(func.ST_Value(tbl.c.rast, point))
                .where(func.ST_Intersects(tbl.c.rast, point))
                .limit(1)
            )
            val = await s.scalar(stmt)
            return float(val) if val is not None else None

    async def elevations(self, coords: list[tuple[float, float]]) -> list[Optional[float]]:
        if not coords:
            return []
        async with self._Session() as s:
            await self._ensure_table()

            # Build a VALUES list of (id, lon, lat)
            values_rows: list[str] = []
            for i, (lat, lon) in enumerate(coords):
                values_rows.append(
                    f"({int(i)}, {float(lon)}::double precision, {float(lat)}::double precision)"
                )

            pts_cte = ", ".join(values_rows)
            # For each point, select the first intersecting raster and compute ST_Value
            sql = (
                "WITH pts(id, lon, lat) AS (VALUES " + pts_cte + ") "
                "SELECT p.id, ("
                "  SELECT ST_Value(er.rast, ST_SetSRID(ST_MakePoint(p.lon, p.lat), 4326)) "
                "  FROM "
                f"  {self._tbl_name} er "
                "  WHERE ST_Intersects(er.rast, ST_SetSRID(ST_MakePoint(p.lon, p.lat), 4326)) "
                "  LIMIT 1"
                ") AS val "
                "FROM pts p ORDER BY p.id"
            )
            res = await s.execute(text(sql))
            rows = res.fetchall()
            # Map by id to preserve order
            out_map: dict[int, Optional[float]] = {}
            for rid, val in rows:
                out_map[int(rid)] = float(val) if val is not None else None
            return [out_map.get(i) for i in range(len(coords))]


__all__ = ["PostgresRasterElevation"]
