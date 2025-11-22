import pytest

from typus import PollinatorGroup, pollinator_groups_for_ancestry
from typus.constants import RankLevel


@pytest.mark.asyncio
async def test_taxon_summary_major_trail(taxonomy_service):
    summary = await taxonomy_service.taxon_summary(47219)  # Apis mellifera

    assert summary.taxon_id == 47219
    assert summary.trail[-1].taxon_id == 47219
    names = [n.scientific_name for n in summary.trail]
    assert names[:2] == ["Animalia", "Arthropoda"]
    assert names[-2:] == ["Apis", "Apis mellifera"]

    ranks = [n.rank_level for n in summary.trail]
    assert RankLevel.L50 in ranks  # class Insecta
    assert RankLevel.L40 in ranks  # order Hymenoptera


@pytest.mark.asyncio
async def test_taxon_summary_preserves_focal_on_minor_rank(taxonomy_service):
    summary = await taxonomy_service.taxon_summary(630955)  # Anthophila (epifamily)

    assert summary.taxon_id == 630955
    assert summary.trail[-1].taxon_id == 630955
    # Even with major_ranks_only default, focal taxon is retained though epifamily is minor.
    assert any(node.taxon_id == 630955 for node in summary.trail)


@pytest.mark.asyncio
async def test_pollinator_groups_from_service(taxonomy_service):
    bee_groups = await taxonomy_service.pollinator_groups_for_taxon(47219)  # Apis mellifera
    wasp_groups = await taxonomy_service.pollinator_groups_for_taxon(54327)  # Vespa crabro
    moth_groups = await taxonomy_service.pollinator_groups_for_taxon(67430)  # Lepidoptera genus

    assert bee_groups == {PollinatorGroup.BEE}
    assert wasp_groups == {PollinatorGroup.WASP}
    assert PollinatorGroup.BUTTERFLY_MOTH in moth_groups


def test_pollinator_group_classifier_covers_all_roots():
    ancestry = [630955, 47822, 47208, 3, 40268]
    groups = pollinator_groups_for_ancestry(ancestry)

    assert PollinatorGroup.BEE in groups
    assert PollinatorGroup.FLY in groups
    assert PollinatorGroup.BEETLE in groups
    assert PollinatorGroup.BIRD in groups
    assert PollinatorGroup.BAT in groups
