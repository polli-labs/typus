import pytest

from typus.constants import RankLevel

DSN = "postgresql+asyncpg://typus:typus@localhost:5432/typus_test"


@pytest.mark.asyncio
async def test_get_taxon_smoke(taxonomy_service):
    """Test basic taxon retrieval."""
    bee_id = 630955  # Anthophila
    bee = await taxonomy_service.get_taxon(bee_id)
    assert bee.scientific_name == "Anthophila"
    assert bee.rank_level == RankLevel.L32  # Anthophila is L32 (epifamily) in sample data


@pytest.mark.asyncio
async def test_children_with_depth(taxonomy_service):
    """Test children retrieval with depth parameter."""
    vespidae_id = 52747

    # With depth=1, we should get direct children (only the Vespinae subfamily)
    direct_children = await taxonomy_service.children(vespidae_id, depth=1)
    assert len(direct_children) == 1
    assert direct_children[0].taxon_id == 84738  # Vespinae

    # With depth=2, we should get descendants up to 2 levels deep (Vespinae + its genera Vespa, Vespula)
    children_depth_2 = await taxonomy_service.children(vespidae_id, depth=2)
    assert len(children_depth_2) == 3  # Vespinae, Vespa, Vespula

    # Check that Vespa and Vespula genera are in the descendants
    genus_ids = {child.taxon_id for child in children_depth_2 if child.rank_level == RankLevel.L20}
    assert genus_ids == {54328, 61356}  # Vespa, Vespula
