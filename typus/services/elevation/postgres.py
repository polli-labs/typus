from __future__ import annotations

from typing import Optional

from sqlalchemy import MetaData, Table, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


class PostgresRasterElevation:
    def __init__(self, dsn: str, raster_table: str = "elevation_raster"):
        self._engine = create_async_engine(dsn, pool_pre_ping=True)
        self._Session = async_sessionmaker(self._engine)
        self._tbl_name = raster_table
        self._tbl: Optional[Table] = None

    async def elevation(self, lat: float, lon: float) -> Optional[float]:
        async with self._Session() as s:
            # Reflect table lazily on first use
            if self._tbl is None:
                async with self._engine.begin() as conn:
                    def _reflect(sync_conn):
                        md = MetaData()
                        Table(self._tbl_name, md, autoload_with=sync_conn)
                        self._tbl = md.tables[self._tbl_name]

                    await conn.run_sync(_reflect)

            point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
            stmt = (
                select(func.ST_Value(self._tbl.c.rast, point))
                .where(func.ST_Intersects(self._tbl.c.rast, point))
                .limit(1)
            )
            val = await s.scalar(stmt)
            return float(val) if val is not None else None


__all__ = ["PostgresRasterElevation"]
