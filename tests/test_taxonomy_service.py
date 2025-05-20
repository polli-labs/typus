import pytest

from typus.services.taxonomy import PostgresTaxonomyService

DSN = "postgresql+asyncpg://typus:typus@localhost:5432/typus_test"


@pytest.mark.asyncio
async def test_get_taxon_smoke():
    svc = PostgresTaxonomyService(DSN)
    t = await svc.get_taxon(47846)  # Apidae
    assert t.scientific_name == "Apidae"
    assert t.rank_level.value == 30
