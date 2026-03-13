from typus.models.taxon import Taxon

SearchTaxaResult = list[Taxon] | list[tuple[Taxon, float]]


def taxon_ids(results: SearchTaxaResult) -> list[int]:
    return [item[0].taxon_id if isinstance(item, tuple) else item.taxon_id for item in results]
