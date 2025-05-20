from __future__ import annotations

import math
from datetime import datetime
from typing import List, Sequence, Tuple

__all__ = [
    "latlon_to_unit_sphere",
    "unit_sphere_to_latlon",
    "datetime_to_temporal_sinusoids",
    "elevation_to_sinusoids",
]


def latlon_to_unit_sphere(lat: float, lon: float) -> Tuple[float, float, float]:
    lat_r, lon_r = math.radians(lat), math.radians(lon)
    x = math.cos(lat_r) * math.cos(lon_r)
    y = math.cos(lat_r) * math.sin(lon_r)
    z = math.sin(lat_r)
    return x, y, z


def unit_sphere_to_latlon(x: float, y: float, z: float) -> Tuple[float, float]:
    lon = math.degrees(math.atan2(y, x))
    hyp = math.sqrt(x * x + y * y)
    lat = math.degrees(math.atan2(z, hyp))
    return lat, lon


def datetime_to_temporal_sinusoids(
    dt: datetime, *, use_jd: bool = False, use_hour: bool = False
) -> List[float]:
    vals: List[float] = []
    if use_jd:
        day = dt.timetuple().tm_yday
        vals.extend(_sin_cos(day / 365.25))
    else:
        vals.extend(_sin_cos(dt.month / 12.0))
    if use_hour:
        vals.extend(_sin_cos(dt.hour / 24.0))
    return vals


def elevation_to_sinusoids(elev_m: float, scales: Sequence[float]) -> List[float]:
    vals: List[float] = []
    for sc in scales:
        vals.extend(_sin_cos(elev_m / sc))
    return vals


def _sin_cos(r: float) -> List[float]:
    return [math.sin(2 * math.pi * r), math.cos(2 * math.pi * r)]
