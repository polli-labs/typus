import os

import pytest

from typus import PostgresRasterElevation

ELEVATION_DSN = (
    os.getenv("ELEVATION_DSN") or os.getenv("TYPUS_TEST_DSN") or os.getenv("POSTGRES_DSN")
)
ELEVATION_TABLE = os.getenv("ELEVATION_TABLE", "elevation_raster")


@pytest.mark.asyncio
async def test_elevation_la_smoke():
    if os.getenv("TYPUS_ELEVATION_TEST", "0") not in {"1", "true", "TRUE", "yes"}:
        pytest.skip("TYPUS_ELEVATION_TEST not enabled")
    if not ELEVATION_DSN:
        pytest.skip("No DSN for elevation tests")

    svc = PostgresRasterElevation(ELEVATION_DSN, raster_table=ELEVATION_TABLE)

    # Los Angeles, CA
    lat, lon = 34.0522, -118.2437
    val = await svc.elevation(lat, lon)

    assert val is not None
    # Plausible range for land elevations (MERIT DEM ~ -430 to 8850 m)
    assert -500.0 <= float(val) <= 10000.0


@pytest.mark.asyncio
async def test_elevations_batch_smoke():
    if os.getenv("TYPUS_ELEVATION_TEST", "0") not in {"1", "true", "TRUE", "yes"}:
        pytest.skip("TYPUS_ELEVATION_TEST not enabled")
    if not ELEVATION_DSN:
        pytest.skip("No DSN for elevation tests")

    svc = PostgresRasterElevation(ELEVATION_DSN, raster_table=ELEVATION_TABLE)

    # LA (land), Central Atlantic (ocean), NYC (land)
    coords = [
        (34.0522, -118.2437),  # LA
        (0.0, -30.0),  # Ocean
        (40.7128, -74.0060),  # NYC
    ]
    vals = await svc.elevations(coords)
    assert len(vals) == 3
    assert vals[0] is not None
    assert vals[1] is None  # ocean expected None
    assert vals[2] is not None
