from __future__ import annotations

import abc
from typing import Optional

from .postgres import PostgresRasterElevation


class ElevationService(abc.ABC):
    """Abstract base for DEM look‑ups."""

    @abc.abstractmethod
    async def elevation(self, lat: float, lon: float) -> Optional[float]:
        """Return meters above sea level, or ``None`` if unavailable."""

    async def elevations(
        self, coords: list[tuple[float, float]]
    ) -> list[Optional[float]]:  # pragma: no cover - default
        """Batch elevation lookup; default naive per-point implementation."""
        out: list[Optional[float]] = []
        for lat, lon in coords:
            out.append(await self.elevation(lat, lon))
        return out


__all__ = ["ElevationService", "PostgresRasterElevation"]
