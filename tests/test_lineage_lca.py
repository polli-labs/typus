import pytest

from typus.constants import RankLevel
from typus.services.taxonomy import PostgresTaxonomyService

DSN = "postgresql+asyncpg://typus:typus@localhost:5432/typus_test"


@pytest.mark.asyncio
async def test_lca_distance():
    svc = PostgresTaxonomyService(DSN)
    bee = 630955  # Anthophila
    wasp = 7433  # Vespidae

    lca = await svc.lca({bee, wasp})
    assert lca.rank_level == RankLevel.L30  # expect family‑level ancestor
    assert lca.scientific_name == "Apoidea"  # example name

    d = await svc.distance(bee, wasp)
    assert d >= 10  # at least one major step apart
