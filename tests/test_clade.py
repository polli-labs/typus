import pytest

from typus.constants import RankLevel
from typus.models.clade import Clade


@pytest.mark.asyncio
async def test_taxon_retrieval_works(taxonomy_service):
    """Test direct taxon retrieval and Clade model instantiation."""
    # Direct test that taxon service works correctly
    taxon = await taxonomy_service.get_taxon(52747)
    assert taxon.taxon_id == 52747
    assert taxon.scientific_name == "Vespidae"
    assert taxon.rank_level == RankLevel.L30

    # For Clade, which is a frozen model, we can just verify it can be instantiated
    cl = Clade(root_ids={52747})
    assert cl.root_ids == {52747}
