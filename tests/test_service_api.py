import pytest


@pytest.mark.asyncio
async def test_children_returns_list(taxonomy_service):
    # 52747 Vespidae has descendants in the fixture
    res = await taxonomy_service.children_list(52747, depth=2)
    assert isinstance(res, list)
    assert all(getattr(t, "taxon_id", None) for t in res)


@pytest.mark.asyncio
async def test_get_many_batched_matches_individual(taxonomy_service):
    ids = {47219, 47220, 52747}
    batched = await taxonomy_service.get_many_batched(ids)
    assert set(batched.keys()) == ids
    for i in ids:
        t = await taxonomy_service.get_taxon(i)
        assert batched[i].taxon_id == t.taxon_id
        assert batched[i].scientific_name == t.scientific_name


@pytest.mark.asyncio
async def test_ancestors_helper_runs(taxonomy_service):
    path = await taxonomy_service.ancestors(47219, include_minor_ranks=True)
    assert path and path[-1] == 47219
