import pytest

from typus.orm.expanded_taxa import ExpandedTaxa


def test_orm_smoke():
    cols = {c.name for c in ExpandedTaxa.__table__.columns}
    expected = {
        "immediateAncestor_taxonID",
        "immediateAncestor_rankLevel",
        "immediateMajorAncestor_taxonID",
        "immediateMajorAncestor_rankLevel",
    }
    assert expected.issubset(cols)
    assert "trueParentID" not in cols
    assert "majorParentID" not in cols


@pytest.mark.asyncio
async def test_lca_sqlite(taxonomy_service):
    assert (await taxonomy_service.lca({47219, 54327})).taxon_id == 47201
    assert (await taxonomy_service.lca({52775, 47220})).taxon_id == 47221
    assert (await taxonomy_service.lca({61356, 54328})).taxon_id == 52747
    assert (await taxonomy_service.lca({47219})).taxon_id == 47219


@pytest.mark.asyncio
async def test_distance_sqlite(taxonomy_service):
    assert await taxonomy_service.distance(47219, 54327, inclusive=False) == 6
    assert await taxonomy_service.distance(52775, 47220, inclusive=False) == 2


@pytest.mark.asyncio
async def test_children_sqlite(taxonomy_service):
    res = await taxonomy_service.children(47221)
    children = {t.taxon_id for t in res}
    assert children == {47220, 52775}
