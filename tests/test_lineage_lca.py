import pytest

# ruff: noqa
from sqlalchemy import create_engine as sqlalchemy_create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession  # Correct imports for async
from typus.services.taxonomy import PostgresTaxonomyService  # Import the concrete service
from typus.models.taxon import Taxon  # For constructing expected Taxon object

from typus.constants import RankLevel

DSN = "postgresql+asyncpg://typus:typus@localhost:5432/typus_test"

# Taxon IDs from the sample data (tests/sample_tsv/expanded_taxa_lca_sample.tsv)
BEE_ANTHOPHILA = 630955  # Anthophila, epifamily, L32
WASP_VESPIDAE = 52747  # Vespidae, family, L30
LCA_ACULEATA_ID = (
    326777  # Aculeata, infraorder, L35 (LCA of Anthophila and Vespidae with minor ranks)
)
LCA_HYMENOPTERA_ID = 47201  # Hymenoptera, order, L40 (LCA with major ranks only)

# Species-level taxa for sibling distance test
VESPA_MANDARINIA = 322284  # Asian giant hornet
VESPA_CRABRO = 54327  # European hornet

# Additional taxon for three-way LCA test
NEMESIIDAE = 47369  # Spider family


@pytest.mark.asyncio
async def test_empty_lca_raises_error(taxonomy_service):
    """Test that an empty set to lca raises ValueError."""
    with pytest.raises(ValueError, match="taxon_ids set cannot be empty"):
        await taxonomy_service.lca(set())


@pytest.mark.asyncio
async def test_lca_distance(taxonomy_service):
    # ---- strict expectations (now that Apocrita & Aculeata are present) ----
    lca_minor = await taxonomy_service.lca(
        {BEE_ANTHOPHILA, WASP_VESPIDAE}, include_minor_ranks=True
    )


@pytest.mark.asyncio
async def test_postgres_lca_fallback_mechanism():
    """Test the Postgres fallback mechanism using a simple SQLite DB."""
    # 1. Set up an in-memory SQLite engine (async)
    async_engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    # 2. Create a minimal expanded_taxa table
    async with async_engine.connect() as connection:
        await connection.run_sync(
            lambda conn: conn.execute(
                text("""
            CREATE TABLE expanded_taxa (
                taxonID INTEGER PRIMARY KEY,
                taxon_id INTEGER,
                name TEXT,
                rankLevel INTEGER,
                "immediateAncestor_taxonID" INTEGER,
                ancestry TEXT,
                "immediateAncestor_rankLevel" INTEGER,
                "immediateMajorAncestor_taxonID" INTEGER,
                "immediateMajorAncestor_rankLevel" INTEGER,
                "commonName" TEXT,
                "taxonActive" BOOLEAN,
                "path" TEXT -- Include to simulate a table that *might* have it (though it won't be used by fallback)
            );
        """)
            )
        )
        await connection.run_sync(
            lambda conn: conn.execute(
                text("""
            INSERT INTO expanded_taxa (taxonID, taxon_id, name, rankLevel, "immediateAncestor_taxonID", ancestry, path) VALUES
            (1, 1, 'Life', 70, NULL, '1', '1'),
            (2, 2, 'PhylumA', 60, 1, '1|2', '1.2'),
            (3, 3, 'ClassA', 50, 2, '1|2|3', '1.2.3'),
            (4, 4, 'ClassB', 50, 2, '1|2|4', '1.2.4'),
            (5, 5, 'OrderA', 40, 3, '1|2|3|5', '1.2.3.5'),
            (6, 6, 'OrderB', 40, 4, '1|2|4|6', '1.2.4.6'),
            (7, 7, 'SpeciesA', 10, 5, '1|2|3|5|7', '1.2.3.5.7'),
            (8, 8, 'SpeciesB', 10, 6, '1|2|4|6|8', '1.2.4.6.8'),
            (9, 9, 'OrderC', 40, 4, '1|2|4|9', '1.2.4.9'),
            (10, 10, 'SpeciesC', 10, 9, '1|2|4|9|10', '1.2.4.9.10');
        """)
            )
        )
        await connection.commit()

    # 3. Instantiate PostgresTaxonomyService. The DSN is a placeholder.
    service_for_test = PostgresTaxonomyService(dsn="postgresql+asyncpg://user:pass@host/db")

    # 4. Create a session and test the fallback method
    AsyncSessionLocal = sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as session:
        # Test case 1: LCA of 7 (SpeciesA) and 8 (SpeciesB) should be 2 (PhylumA)
        lca_id_7_8 = await service_for_test._lca_recursive_fallback(session, {7, 8})
        assert lca_id_7_8 == 2

        # Test case 2: LCA of 7 (SpeciesA) and 10 (SpeciesC) should be 2 (PhylumA)
        lca_id_7_10 = await service_for_test._lca_recursive_fallback(session, {7, 10})
        assert lca_id_7_10 == 2

        # Test case 3: LCA of 5 (OrderA) and 6 (OrderB) should be 2 (PhylumA)
        lca_id_5_6 = await service_for_test._lca_recursive_fallback(session, {5, 6})
        assert lca_id_5_6 == 2

        # Test case 4: LCA of 7 (SpeciesA), 8 (SpeciesB), 10 (SpeciesC) should be 2 (PhylumA)
        lca_id_7_8_10 = await service_for_test._lca_recursive_fallback(session, {7, 8, 10})
        assert lca_id_7_8_10 == 2

        # Test case 5: LCA of a single ID
        lca_id_7_only = await service_for_test._lca_recursive_fallback(session, {7})
        assert lca_id_7_only == 7

        # Test case 6: LCA involving a non-existent ID
        lca_id_non_existent = await service_for_test._lca_recursive_fallback(session, {7, 999})
        assert lca_id_non_existent is None

    # Clean up the async engine
    await async_engine.dispose()
    assert (lca_minor.taxon_id, lca_minor.rank_level) == (LCA_ACULEATA_ID, RankLevel.L35)
    assert lca_minor.scientific_name == "Aculeata"

    lca_major = await taxonomy_service.lca(
        {BEE_ANTHOPHILA, WASP_VESPIDAE}, include_minor_ranks=False
    )
    assert (lca_major.taxon_id, lca_major.rank_level) == (LCA_HYMENOPTERA_ID, RankLevel.L40)
    assert lca_major.scientific_name == "Hymenoptera"

    # The fixture has both Anthophila and Vespidae with Aculeata as a common ancestor
    # When minor ranks are included, the distance should be:
    # Anthophila -> Apoidea -> Aculeata <- Vespoidea <- Vespidae
    # (i.e., 2 steps from each to the common ancestor, for a total of 4)
    distance_with_minors = await taxonomy_service.distance(
        BEE_ANTHOPHILA, WASP_VESPIDAE, include_minor_ranks=True
    )
    assert distance_with_minors == 4

    # When only major ranks are considered:
    # Anthophila (L32, minor) → filtered out, maps to major ancestry ending at Hymenoptera (L40)
    # Vespidae (L30, major) → Hymenoptera (L40) = 1 edge
    # Total distance = 0 + 1 = 1
    distance_major_only = await taxonomy_service.distance(
        BEE_ANTHOPHILA, WASP_VESPIDAE, include_minor_ranks=False
    )
    assert distance_major_only == 1

    # ---- NEW: species-level sibling distance inside Vespa ----
    assert (
        await taxonomy_service.distance(
            VESPA_MANDARINIA,  # Vespa mandarinia
            VESPA_CRABRO,  # Vespa crabro
            include_minor_ranks=True,
        )
        == 2
    )  # mandarinia -> Vespa (genus) -> crabro


@pytest.mark.asyncio
async def test_ancestry_verification(taxonomy_service):
    """Verify that ancestry paths end with correct root nodes."""
    # The ancestry for Apocrita (suborder) should have Hymenoptera (order) and other higher-rank ancestors
    apocrita_id = 124417
    apocrita = await taxonomy_service.get_taxon(apocrita_id)

    # Check that ancestry is from root -> taxon (highest rank to lowest)
    assert apocrita.ancestry[0] == 1  # First should be Kingdom Animalia

    # Verify selected ancestors appear in proper order
    expected_ancestors = [1, 47120, 372739, 47158, 184884, 47201]  # Animalia -> ... -> Hymenoptera

    # Check each expected ancestor exists in the ancestry and in the correct order
    for i, ancestor_id in enumerate(expected_ancestors):
        assert apocrita.ancestry[i] == ancestor_id, (
            f"Expected {ancestor_id} at position {i}, got {apocrita.ancestry[i]}"
        )

    # The last ID in ancestry should be the taxon's own ID
    assert apocrita.ancestry[-1] == apocrita_id


@pytest.mark.asyncio
async def test_distance_symmetry_identity(taxonomy_service):
    """Test that distance is symmetric and identity distance is 0."""
    # Test distance symmetry: d(a,b) == d(b,a)
    a, b = 52747, 47221  # Vespidae, Apidae

    # Distance should be symmetric regardless of the argument order
    dist_a_to_b = await taxonomy_service.distance(a, b)
    dist_b_to_a = await taxonomy_service.distance(b, a)
    assert dist_a_to_b == dist_b_to_a, (
        f"Distance not symmetric: d({a},{b})={dist_a_to_b} != d({b},{a})={dist_b_to_a}"
    )

    # Also check with include_minor_ranks parameter
    dist_a_to_b_with_minors = await taxonomy_service.distance(a, b, include_minor_ranks=True)
    dist_b_to_a_with_minors = await taxonomy_service.distance(b, a, include_minor_ranks=True)
    assert dist_a_to_b_with_minors == dist_b_to_a_with_minors

    # Test identity: d(a,a) == 0
    assert await taxonomy_service.distance(a, a) == 0
    assert await taxonomy_service.distance(b, b) == 0
    assert await taxonomy_service.distance(a, a, include_minor_ranks=False) == 0


@pytest.mark.asyncio
async def test_three_way_lca(taxonomy_service):
    """Test LCA computation with more than two taxa (will follow different ancestors based on the taxa)."""
    # Let's try with two Hymenoptera and one from a different order
    ids = {BEE_ANTHOPHILA, WASP_VESPIDAE, NEMESIIDAE}  # Anthophila, Vespidae, Nemesiidae

    # With all these different families, the LCA should be much higher up
    # Since Nemesiidae is a spider family, it's in a different order than bees and wasps,
    # so their common ancestor will be higher in the tree
    lca = await taxonomy_service.lca(ids)

    # The LCA should be Arthropoda (phylum)
    assert lca.taxon_id == 47120  # Arthropoda
    assert lca.rank_level == RankLevel.L60


@pytest.mark.asyncio
async def test_ancestor_descendant_distance(taxonomy_service):
    """Test distance between ancestor and descendant taxa."""
    # Test direct parent-child relationship
    vespidae_id = 52747  # Family
    vespinae_id = 84738  # Subfamily (direct child of Vespidae)
    vespa_id = 54328  # Genus (child of Vespinae)

    # Distance between parent and direct child should be 1
    assert await taxonomy_service.distance(vespidae_id, vespinae_id) == 1

    # Distance between parent and grandchild should be 2
    assert await taxonomy_service.distance(vespidae_id, vespa_id) == 2

    # Distance from genus to its species should be 1
    assert await taxonomy_service.distance(vespa_id, VESPA_MANDARINIA) == 1

    # Test with minors excluded - should skip levels correctly
    anthophila_id = 630955  # Epifamily (minor rank)
    apidae_id = 47221  # Family (major rank)

    # The distance between Anthophila (epifamily) and Aculeata (infraorder) with minors included
    # Anthophila -> Apoidea -> Aculeata = 2 steps
    assert (
        await taxonomy_service.distance(anthophila_id, LCA_ACULEATA_ID, include_minor_ranks=True)
        == 2
    )

    # With minors excluded, we should get the distance between Apidae (family) and Hymenoptera (order)
    # Apidae -> Hymenoptera = 1 step
    assert (
        await taxonomy_service.distance(apidae_id, LCA_HYMENOPTERA_ID, include_minor_ranks=False)
        == 1
    )
