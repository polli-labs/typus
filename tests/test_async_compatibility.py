"""Test async compatibility for PostgresTaxonomyService.

This test ensures that PostgresTaxonomyService works correctly in pure asyncio
contexts without greenlet support, which is critical for FastAPI/uvicorn deployments.
"""

import asyncio
import os

import pytest

from typus import PostgresTaxonomyService
from typus.constants import RankLevel


@pytest.mark.asyncio
async def test_postgres_pure_asyncio():
    """Test PostgresTaxonomyService in pure asyncio context without greenlet.

    This test is critical for ensuring compatibility with FastAPI and other
    pure async frameworks that don't provide greenlet context.
    """
    # Get DSN from environment or use default test database
    dsn = os.environ.get(
        "TYPUS_TEST_DSN", "postgresql+asyncpg://postgres:ooglyboogly69@localhost:5432/ibrida-v0"
    )

    # Skip test if PostgreSQL is not available
    try:
        service = PostgresTaxonomyService(dsn)
    except Exception as e:
        pytest.skip(f"PostgreSQL not available: {e}")

    # Test 1: Basic get_taxon - this was failing with MissingGreenlet
    try:
        taxon = await service.get_taxon(47219)  # Apis mellifera
    except RuntimeError as e:
        if "does not exist" in str(e):
            pytest.skip(f"PostgreSQL database unavailable: {e}")
        raise
    assert taxon.scientific_name == "Apis mellifera"
    assert taxon.rank_level == RankLevel(10)  # species
    assert taxon.parent_id is not None

    # Test 2: Get another taxon
    bee_taxon = await service.get_taxon(630955)  # Anthophila
    assert bee_taxon.scientific_name == "Anthophila"

    # Test 3: Children method (uses raw SQL)
    children = []
    async for child in service.children(630955, depth=1):
        children.append(child)
    assert len(children) > 0
    assert all(child.parent_id == 630955 for child in children)

    # Test 4: LCA (Lowest Common Ancestor)
    lca = await service.lca({47219, 54327})  # Two bee species
    assert lca is not None
    assert lca.taxon_id != 47219  # Should be an ancestor, not one of the inputs
    assert lca.taxon_id != 54327

    # Test 5: Distance calculation
    distance = await service.distance(47219, 54327)
    assert distance > 0

    # Test 6: Fetch subtree
    subtree = await service.fetch_subtree({630955})
    assert len(subtree) > 0
    assert 630955 in subtree.values() or 630955 in subtree.keys()


def test_no_greenlet_context():
    """Test that the service works in a completely new event loop without greenlet.

    This simulates the environment of FastAPI/uvicorn where no greenlet context
    is available. The test creates its own event loop to ensure isolation.
    """

    async def run_test():
        dsn = os.environ.get(
            "TYPUS_TEST_DSN",
            "postgresql+asyncpg://postgres:ooglyboogly69@localhost:5432/ibrida-v0-r1",
        )

        try:
            service = PostgresTaxonomyService(dsn)

            # The critical test: get_taxon was failing with MissingGreenlet
            taxon = await service.get_taxon(47219)
            assert taxon.scientific_name == "Apis mellifera"

            # Test children to ensure raw SQL also works
            children_count = 0
            async for _ in service.children(630955, depth=1):
                children_count += 1
                if children_count > 2:  # Just check a few
                    break
            assert children_count > 0

            return True
        except Exception as e:
            if "MissingGreenlet" in str(e.__class__.__name__):
                pytest.fail(f"MissingGreenlet error still occurs: {e}")
            elif "cannot connect" in str(e).lower() or "connection" in str(e).lower():
                pytest.skip(f"Database connection not available: {e}")
            else:
                raise

    # Create a completely new event loop without any greenlet context
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(run_test())
        assert result is True
    finally:
        loop.close()


@pytest.mark.asyncio
async def test_handles_missing_ancestry_column():
    """Test that the service handles databases without ancestry column gracefully.

    The ibridaDB database doesn't have an ancestry column - it uses expanded
    columns like L10_taxonID instead. The service should handle this gracefully.
    """
    dsn = os.environ.get(
        "TYPUS_TEST_DSN", "postgresql+asyncpg://postgres:ooglyboogly69@localhost:5432/ibrida-v0"
    )

    try:
        service = PostgresTaxonomyService(dsn)
    except Exception as e:
        pytest.skip(f"PostgreSQL not available: {e}")

    # Get a taxon - should work even without ancestry column
    try:
        taxon = await service.get_taxon(47219)
    except RuntimeError as e:
        if "does not exist" in str(e):
            pytest.skip(f"PostgreSQL database unavailable: {e}")
        raise
    assert taxon.scientific_name == "Apis mellifera"

    # Ancestry may be empty (no ancestry column) or derived from expanded columns; both are acceptable.
    assert isinstance(taxon.ancestry, list)

    # But parent_id should still work via immediateAncestor_taxonID
    assert taxon.parent_id is not None

    # Verify we can traverse the hierarchy using parent_id
    parent = await service.get_taxon(taxon.parent_id)
    assert parent.scientific_name is not None
    assert parent.rank_level.value > taxon.rank_level.value  # Parent has higher rank number
