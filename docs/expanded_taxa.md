# expanded_taxa overview

The `expanded_taxa` table unwraps iNaturalist's ancestry string into one column
per rank. Each row holds links to both its immediate parent and its nearest major
ancestor.

## Immediate Ancestor Columns

| Column | Description |
|---|---|
| `immediateMajorAncestor_taxonID` | TaxonID of the closest ancestor at a major rank |
| `immediateMajorAncestor_rankLevel` | Rank level of that ancestor |
| `immediateAncestor_taxonID` | Direct parent taxonID |
| `immediateAncestor_rankLevel` | Rank level of the direct parent |

## Rank level mapping

| Level | Rank |
|---|---|
| 5 | subspecies |
| 10 | species |
| 20 | genus |
| 30 | family |
| 40 | order |
| 50 | class |
| 60 | phylum |
| 70 | kingdom |

## Indexing strategy

Primary key on `taxonID` plus indexes on `rankLevel`, `name` and the most common
`LXX_taxonID` columns for fast clade filtering.

## Common use cases

* Filter by clade using `LXX_taxonID` columns.
* Look up immediate parents with the ancestor columns.
* Join observation tables on `taxonID`.

