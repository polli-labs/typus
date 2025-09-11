import os

import pytest

from typus.constants import RankLevel


@pytest.mark.asyncio
async def test_scientific_exact_name(taxonomy_service):
    # species: Apis mellifera (47219)
    res = await taxonomy_service.search_taxa(
        "Apis mellifera", scopes={"scientific"}, match="exact", fuzzy=False
    )
    assert any(t.taxon_id == 47219 for t in res)


@pytest.mark.asyncio
async def test_scientific_prefix_and_rank_filter(taxonomy_service):
    # genus: Apis (47220)
    res = await taxonomy_service.search_taxa(
        "Apis",
        scopes={"scientific"},
        match="prefix",
        fuzzy=False,
        rank_filter={RankLevel.L20},
    )
    assert any(t.taxon_id == 47220 for t in res)


@pytest.mark.asyncio
async def test_vernacular_exact_name(taxonomy_service):
    # fixture has commonName for Apis mellifera as 'honey bee'
    res = await taxonomy_service.search_taxa(
        "honey bee", scopes={"vernacular"}, match="exact", fuzzy=False
    )
    assert any(t.taxon_id == 47219 for t in res)


@pytest.mark.asyncio
async def test_vernacular_fuzzy_near_miss(taxonomy_service):
    # Slightly incomplete token should fuzzy-match
    res = await taxonomy_service.search_taxa(
        "honey be",
        scopes={"vernacular"},
        match="substring",
        fuzzy=True,
        threshold=0.7,
        limit=10,
    )
    assert any(t.taxon_id == 47219 for t in res)


@pytest.mark.asyncio
async def test_with_scores_flag(taxonomy_service):
    res = await taxonomy_service.search_taxa(
        "Apis", scopes={"scientific"}, match="prefix", with_scores=True
    )
    assert isinstance(res, list)
    assert res and isinstance(res[0], tuple)
    taxon, score = res[0]
    assert hasattr(taxon, "taxon_id")
    assert 0.0 <= score <= 1.0


@pytest.mark.asyncio
async def test_postgres_parity_when_available():
    dsn = os.getenv("TYPUS_TEST_DSN")
    if not dsn:
        pytest.skip("Postgres DSN not configured")
    from typus import PostgresTaxonomyService

    svc = PostgresTaxonomyService(dsn)
    res = await svc.search_taxa("Apis mellifera", scopes={"scientific"}, match="exact", fuzzy=False)
    assert any(t.taxon_id == 47219 for t in res)
