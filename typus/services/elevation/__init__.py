from __future__ import annotations

import abc
from typing import Optional

from .postgres import PostgresRasterElevation


class ElevationService(abc.ABC):
    """Abstract base for DEM look‑ups."""

    @abc.abstractmethod
    async def elevation(self, lat: float, lon: float) -> Optional[float]:
        """Return meters above sea level, or ``None`` if unavailable."""


__all__ = ["ElevationService", "PostgresRasterElevation"]

