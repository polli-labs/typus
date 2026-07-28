import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from typus import PostgresRasterElevation

ELEVATION_DSN = (
    os.getenv("ELEVATION_DSN") or os.getenv("TYPUS_TEST_DSN") or os.getenv("POSTGRES_DSN")
)
ELEVATION_TABLE = os.getenv("ELEVATION_TABLE", "elevation_raster")


def test_elevation_rejects_invalid_table_name():
    with pytest.raises(ValueError):
        PostgresRasterElevation(
            "postgresql+asyncpg://mock:mock@localhost/mock",
            raster_table="elevation_raster; DROP TABLE elevation_raster",
        )


@pytest.mark.asyncio
async def test_elevations_batch_quotes_table_and_binds_coordinates():
    svc = PostgresRasterElevation(
        "postgresql+asyncpg://mock:mock@localhost/mock",
        raster_table="public.elevation_raster",
    )
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [(0, 12.5), (1, None)]
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with (
        patch.object(svc, "_Session", return_value=mock_session),
        patch.object(svc, "_ensure_table", AsyncMock()),
    ):
        values = await svc.elevations([(34.0522, -118.2437), (0.0, -30.0)])

    assert values == [12.5, None]
    sql = str(mock_session.execute.call_args.args[0])
    params = mock_session.execute.call_args.args[1]

    assert '"public"."elevation_raster" er' in sql
    assert ":lon0" in sql
    assert ":lat0" in sql
    assert "-118.2437" not in sql
    assert "34.0522" not in sql
    assert params == {
        "id0": 0,
        "lon0": -118.2437,
        "lat0": 34.0522,
        "id1": 1,
        "lon1": -30.0,
        "lat1": 0.0,
    }


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
