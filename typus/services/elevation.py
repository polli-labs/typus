from __future__ import annotations

import abc
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ..orm.base import Base


class ElevationService(abc.ABC):
    """Abstract base for DEM look‑ups."""

    @abc.abstractmethod
    async def elevation(self, lat: float, lon: float) -> Optional[float]:
        """Return meters above sea level, or ``None`` if unavailable."""


class PostgresRasterElevation(ElevationService):
    def __init__(self, dsn: str, raster_table: str = "elevation_raster"):
        self._engine = create_async_engine(dsn, pool_pre_ping=True)
        self._Session = async_sessionmaker(self._engine)
        self._tbl = Base.metadata.tables.get(raster_table)
        if self._tbl is None:
            raise RuntimeError(f"Raster table '{raster_table}' not reflected in metadata")

    async def elevation(self, lat: float, lon: float):
        async with self._Session() as s:
            point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
            stmt = (
                select(func.ST_Value(self._tbl.c.rast, point))
                .where(func.ST_Intersects(self._tbl.c.rast, point))
                .limit(1)
            )
            val = await s.scalar(stmt)
            return float(val) if val is not None else None
