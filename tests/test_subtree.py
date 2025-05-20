import pytest

from typus.services.taxonomy import PostgresTaxonomyService

DSN = "postgresql+asyncpg://typus:typus@localhost:5432/typus_test"


@pytest.mark.asyncio
async def test_subtree_size():
    svc = PostgresTaxonomyService(DSN)
    tree = await svc.fetch_subtree({630955})  # Anthophila
    # expect > 5 but < 2000 immediate descendants for CI fixture
    assert 5 < len(tree) < 2000
    assert tree[630955] is not None  # parent present
