from typus.constants import RankLevel, infer_rank


def test_infer_species():
    assert infer_rank("Species") == RankLevel.L10
    assert infer_rank("fam") == RankLevel.L30
