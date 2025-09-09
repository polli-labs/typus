Title: Elevation Service (Postgres)

The Elevation service provides elevation lookups (meters above sea level) using PostGIS rasters loaded from MERIT DEM. This service is Postgres-only.

Usage

- Import: from `typus import PostgresRasterElevation`.
- DSN: use `TYPUS_TEST_DSN` or `POSTGRES_DSN`; you may also set `ELEVATION_DSN` to override specifically for elevation tests.
- Table: defaults to `elevation_raster`. Override via the `raster_table` parameter or `ELEVATION_TABLE` env var.

Example

```
from typus import PostgresRasterElevation

dsn = os.getenv("ELEVATION_DSN") or os.getenv("TYPUS_TEST_DSN")
svc = PostgresRasterElevation(dsn, raster_table=os.getenv("ELEVATION_TABLE", "elevation_raster"))

val = await svc.elevation(34.0522, -118.2437)  # Los Angeles (lat, lon)
print(val)  # float | None

# Batch example
vals = await svc.elevations([
  (34.0522, -118.2437),  # LA
  (0.0, -30.0),          # ocean (likely None)
  (40.7128, -74.0060),   # NYC
])
```

Environment

- `TYPUS_ELEVATION_TEST=1` enables guarded tests in `tests/test_elevation_service.py`.
- `ELEVATION_DSN` (optional) overrides DSN used by elevation tests.
- `ELEVATION_TABLE` (optional) overrides raster table name (default `elevation_raster`).

Database Expectations

- Table schema: `elevation_raster(rid SERIAL PRIMARY KEY, rast raster, filename text)`.
- SRID 4326 (WGS84). Queries use `ST_Intersects(rast, ST_SetSRID(ST_MakePoint(lon, lat), 4326))` and `ST_Value`.
- Indexes: retain only the primary key and a single GIST spatial index on `ST_ConvexHull(rast)`.

Performance Notes

- After duplicate index cleanup on `elevation_raster`, only two indexes remain:
  - `elevation_raster_pkey` (primary key)
  - `elevation_raster_st_convexhull_idx` (GIST spatial)
- In the reference environment, single-point lookup improved from ~538ms → ~207ms after removing 1,150 duplicate indexes (faster planning, less noise).

Coverage & Limitations

- MERIT DEM coverage focuses on global land; ocean or no-data areas can return `None`.
- Some polar regions are not covered (above ~60°N / below ~60°S).
