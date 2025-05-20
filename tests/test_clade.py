import pytest

from typus.models.clade import Clade


@pytest.mark.asyncio
async def test_roots_cache(taxonomy_service):
    cl = Clade(root_ids={630955})
    roots1 = await cl.roots(taxonomy_service)
    roots2 = await cl.roots(taxonomy_service)
    assert roots1 == roots2  # cache hit
