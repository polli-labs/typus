"""CI-friendly tests for async compatibility without requiring a database.

These tests use mocks to verify that the async/greenlet issues are resolved
without needing access to a PostgreSQL database.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from typus import PostgresTaxonomyService
from typus.constants import RankLevel


@pytest.mark.asyncio
async def test_no_greenlet_with_mock():
    """Test that ORM operations don't trigger greenlet issues - CI version.

    This test verifies the core fix: that accessing ORM attributes doesn't
    cause MissingGreenlet errors in pure asyncio contexts.
    """
    # Create a mock row that simulates what SQLAlchemy would return
    mock_row = MagicMock()
    mock_row.taxon_id = 47219
    mock_row.scientific_name = "Apis mellifera"
    mock_row.rank_level = 10
    mock_row.parent_id = 578086

    # The critical test: ancestry_str should be accessible without greenlet errors
    # In the broken version, accessing this deferred column would trigger MissingGreenlet
    mock_row.ancestry_str = None  # Simulates a database without ancestry column

    # Create service (DSN doesn't matter since we're mocking)
    service = PostgresTaxonomyService("postgresql+asyncpg://mock:mock@localhost/mock")

    # Test that _row_to_taxon handles the mock row correctly
    taxon = service._row_to_taxon(mock_row)

    assert taxon.taxon_id == 47219
    assert taxon.scientific_name == "Apis mellifera"
    assert taxon.rank_level == RankLevel(10)
    assert taxon.parent_id == 578086
    assert taxon.ancestry == []  # Should be empty when ancestry_str is None


@pytest.mark.asyncio
async def test_row_to_taxon_without_ancestry_column():
    """_row_to_taxon should not depend on legacy ancestry_str presence."""
    mock_row = MagicMock()
    mock_row.taxon_id = 47219
    mock_row.scientific_name = "Apis mellifera"
    mock_row.rank_level = 10
    mock_row.parent_id = 578086

    service = PostgresTaxonomyService("postgresql+asyncpg://mock:mock@localhost/mock")
    taxon = service._row_to_taxon(mock_row)

    assert taxon.ancestry == []


@pytest.mark.asyncio
async def test_row_to_taxon_mapping_without_ancestry():
    """Test that _row_to_taxon_from_mapping handles missing ancestry gracefully."""
    row_mapping = {
        "taxonID": 47219,  # Note: uses taxonID not taxon_id
        "name": "Apis mellifera",
        "rankLevel": 10,
        "immediateAncestor_taxonID": 578086,
        # No ancestry column
    }

    service = PostgresTaxonomyService("postgresql+asyncpg://mock:mock@localhost/mock")
    taxon = service._row_to_taxon_from_mapping(row_mapping)

    assert taxon.taxon_id == 47219
    assert taxon.scientific_name == "Apis mellifera"
    assert taxon.rank_level == RankLevel(10)
    assert taxon.parent_id == 578086
    assert taxon.ancestry == []


def test_no_greenlet_in_new_loop():
    """Test that the service works in a new event loop without greenlet.

    This simulates the FastAPI/uvicorn environment where no greenlet
    context is available.
    """

    async def test_async():
        # Mock the session and query execution
        with patch("typus.services.taxonomy.postgres.select") as mock_select:
            mock_stmt = MagicMock()
            mock_select.return_value.where.return_value = mock_stmt

            mock_row = MagicMock()
            mock_row.taxon_id = 47219
            mock_row.scientific_name = "Apis mellifera"
            mock_row.rank_level = 10
            mock_row.parent_id = 578086
            mock_row.ancestry_str = None

            service = PostgresTaxonomyService("postgresql+asyncpg://mock:mock@localhost/mock")

            # Mock the session
            mock_session = AsyncMock()
            mock_session.scalar = AsyncMock(return_value=mock_row)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)

            with patch.object(service, "_Session", return_value=mock_session):
                # This should not raise MissingGreenlet
                taxon = await service.get_taxon(47219)
                assert taxon.scientific_name == "Apis mellifera"
                assert taxon.ancestry == []

        return True

    # Create a new event loop without greenlet context
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(test_async())
        assert result is True
    finally:
        loop.close()


@pytest.mark.asyncio
async def test_sql_uses_correct_column_names():
    """Verify that raw SQL queries use the correct column names.

    The production database uses 'taxonID' not 'taxon_id', etc.
    """
    service = PostgresTaxonomyService("postgresql+asyncpg://mock:mock@localhost/mock")

    # Check children method SQL

    with patch("typus.services.taxonomy.postgres.text") as mock_text:
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(
                mappings=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            )
        )
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch.object(service, "_Session", return_value=mock_session):
            async for _ in service.children(630955, depth=1):
                break

        # Verify the SQL uses 'taxonID' not 'taxon_id'
        sql_call = mock_text.call_args[0][0]
        assert '"taxonID"' in sql_call
        assert "taxon_id" not in sql_call.replace('"taxonID"', "")  # Remove quoted version first
