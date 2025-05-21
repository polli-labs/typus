import pytest

DSN = "postgresql+asyncpg://typus:typus@localhost:5432/typus_test"


@pytest.mark.asyncio
async def test_subtree_size(taxonomy_service):
    # Vespidae mini-subtree test (specific small tree with known size)
    vespidae_id = 52747
    vespidae_subtree = await taxonomy_service.subtree(vespidae_id)
    assert len(vespidae_subtree) == 7  # Vespidae and its 6 descendants in the sample data

    # Anthophila subtree test (in a full production database, this would have many descendants)
    # In our test fixture it only has a few entries
    anthophila_id = 630955
    subtree = await taxonomy_service.subtree(anthophila_id)
    assert len(subtree) >= 2  # Should at least have Anthophila itself and Apidae


@pytest.mark.asyncio
async def test_subtree_parent_consistency(taxonomy_service):
    """Test that parent-child relationships in subtree are consistent."""
    vespidae_id = 52747
    sub = await taxonomy_service.subtree(vespidae_id)

    # Check that every node's parent is also in the subtree (except the root)
    for child_id, parent_id in sub.items():
        if child_id != vespidae_id and parent_id is not None:  # Skip the root node itself
            assert parent_id in sub, f"Parent {parent_id} of node {child_id} not in subtree"

    # Check parent-child consistency
    # For each node (except the root), its parent's parent should either be None (if parent is root)
    # or should match the grand-parent we'd get by calling get_taxon
    for child_id, parent_id in sub.items():
        if child_id != vespidae_id and parent_id is not None and parent_id != vespidae_id:
            # This node has a parent that's not the root, so the parent should have a parent in the subtree
            grandparent_id_in_subtree = sub[parent_id]
            assert grandparent_id_in_subtree is not None

            # Verify with get_taxon that the parent's parent matches
            parent_taxon = await taxonomy_service.get_taxon(parent_id)
            assert parent_taxon.parent_id == grandparent_id_in_subtree

    # Verify specific known relationships in the Vespidae subtree
    assert sub[84738] == vespidae_id  # Vespinae is child of Vespidae
    assert sub[54328] == 84738  # Vespa is child of Vespinae
    assert sub[322284] == 54328  # Vespa mandarinia is child of Vespa
