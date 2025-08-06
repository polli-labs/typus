# expanded_taxa Table Documentation

## Overview

The `expanded_taxa` table is a denormalized view that transforms iNaturalist's compact taxonomy representation into an expanded format optimized for efficient querying, filtering, and analysis. It "unpacks" the ancestry string from the original `taxa` table into discrete columns for each taxonomic rank level, enabling fast clade-based filtering and ancestor lookups without recursive string parsing.

## Purpose and Design Philosophy

The table serves as the foundation for taxonomic data processing and export operations, providing:
- **Efficient clade filtering** through indexed rank-level columns
- **Direct parent access** via immediate ancestor columns
- **Fast taxonomic traversal** without recursive queries
- **Common name integration** from Catalog of Life Data Package (ColDP)

## Core Table Schema

### Primary Identification Columns

| Column      | Type              | Description |
|-------------|-------------------|-------------|
| taxonID     | integer           | Primary key; unique taxon identifier from iNaturalist |
| rankLevel   | double precision  | Numeric indicator of the taxonomic rank (lower = higher in hierarchy) |
| rank        | varchar(255)      | Human-readable taxonomic rank label (e.g., "species", "genus") |
| name        | varchar(255)      | Scientific name of the taxon |
| taxonActive | boolean           | Indicates whether the taxon is currently active in iNaturalist's taxonomy |
| commonName  | varchar(255)      | Primary common name (populated from ColDP integration) |

### Immediate Ancestor Columns

These columns provide direct access to parent taxa in the taxonomic hierarchy, eliminating the need for recursive queries:

| Column                           | Type              | Description |
|----------------------------------|-------------------|-------------|
| immediateMajorAncestor_taxonID   | integer           | Taxon ID of the immediate major ancestor (next major rank up) |
| immediateMajorAncestor_rankLevel | double precision  | Rank level of the immediate major ancestor |
| immediateAncestor_taxonID        | integer           | Direct parent taxon ID in the taxonomy |
| immediateAncestor_rankLevel      | double precision  | Rank level of the direct parent |

### Expanded Taxonomic Hierarchy Columns

For each standard taxonomic rank level, three columns are provided:
- `L{level}_taxonID` - Taxon ID at that rank level
- `L{level}_name` - Scientific name at that rank level  
- `L{level}_commonName` - Common name at that rank level (from ColDP)

## Complete Rank Level Mapping

| Level | Standard Rank    | Column Prefix | Major Rank |
|-------|------------------|---------------|------------|
| 5     | subspecies       | L5_           | No         |
| 10    | species          | L10_          | Yes        |
| 11    | species group    | L11_          | No         |
| 12    | species subgroup | L12_          | No         |
| 13    | species complex  | L13_          | No         |
| 15    | hybrid           | L15_          | No         |
| 20    | genus            | L20_          | Yes        |
| 24    | subgenus         | L24_          | No         |
| 25    | section          | L25_          | No         |
| 26    | subsection       | L26_          | No         |
| 27    | series           | L27_          | No         |
| 30    | tribe            | L30_          | No         |
| 32    | subtribe         | L32_          | No         |
| 33    | supertribe       | L33_          | No         |
| 33.5  | subfamily        | L33_5_        | No         |
| 34    | family           | L34_          | Yes        |
| 34.5  | epifamily        | L34_5_        | No         |
| 35    | superfamily      | L35_          | No         |
| 37    | infraorder       | L37_          | No         |
| 40    | order            | L40_          | Yes        |
| 43    | suborder         | L43_          | No         |
| 44    | infraorder       | L44_          | No         |
| 45    | superorder       | L45_          | No         |
| 47    | infraclass       | L47_          | No         |
| 50    | class            | L50_          | Yes        |
| 53    | subclass         | L53_          | No         |
| 57    | superclass       | L57_          | No         |
| 60    | subphylum        | L60_          | No         |
| 67    | phylum           | L67_          | Yes        |
| 70    | kingdom          | L70_          | Yes        |

Note: Levels 33.5 and 34.5 use underscore notation (L33_5_, L34_5_) in column names.

## Indexing Strategy

The table employs strategic indexing for optimal query performance:

### Primary and Core Indexes
- Primary key on `taxonID`
- B-tree index on `name` for scientific name lookups
- B-tree index on `rankLevel` for rank-based filtering

### Taxonomic Level Indexes (for clade filtering)
- `idx_expanded_taxa_l10_taxonid` - Species-level filtering
- `idx_expanded_taxa_l20_taxonid` - Genus-level filtering  
- `idx_expanded_taxa_l30_taxonid` - Tribe-level filtering
- `idx_expanded_taxa_l40_taxonid` - Order-level filtering
- `idx_expanded_taxa_l50_taxonid` - Class-level filtering
- `idx_expanded_taxa_l60_taxonid` - Subphylum-level filtering
- `idx_expanded_taxa_l70_taxonid` - Kingdom-level filtering

### Immediate Ancestor Indexes
- `idx_immediate_ancestor_taxon_id` - For parent lookups
- `idx_immediate_major_ancestor_taxon_id` - For major ancestor traversal

## Common Use Cases

### Species-Level Filtering
```sql
-- Get all records for a specific species
SELECT * FROM expanded_taxa 
WHERE L10_taxonID = 47219;  -- Apis mellifera
```

### Clade-Based Filtering
```sql
-- Get all bees (Anthophila epifamily)
SELECT * FROM expanded_taxa 
WHERE L34_5_taxonID = 630955;

-- Get all birds (Aves class)
SELECT * FROM expanded_taxa 
WHERE L50_taxonID = 3;
```

### Ancestor Traversal
```sql
-- Find immediate parent
SELECT parent.* 
FROM expanded_taxa child
JOIN expanded_taxa parent ON child.immediateAncestor_taxonID = parent.taxonID
WHERE child.taxonID = 47219;
```

### Taxonomic Hierarchy Display
```sql
-- Show full taxonomic hierarchy for a species
SELECT 
    name as species_name,
    L20_name as genus,
    L34_name as family,
    L40_name as order,
    L50_name as class,
    L67_name as phylum,
    L70_name as kingdom
FROM expanded_taxa 
WHERE taxonID = 47219;
```

### Finding Taxa with Common Names
```sql
-- Find all taxa with common names at species level
SELECT taxonID, name, commonName 
FROM expanded_taxa 
WHERE rankLevel = 10 
  AND commonName IS NOT NULL;
```

## Performance Considerations

1. **Use Indexed Columns**: Always filter on indexed `LXX_taxonID` columns for clade queries
2. **Avoid String Operations**: Use numeric `taxonID` comparisons rather than name matching when possible
3. **Leverage Immediate Ancestors**: Use the immediate ancestor columns for parent lookups instead of joins
4. **Batch Operations**: For large updates, use appropriate transaction boundaries

## Important Notes on Ancestry Column

The `ancestry` column has been **deprecated** in production databases in favor of:
- Immediate ancestor columns for direct parent relationships
- Expanded `LXX_taxonID` columns for efficient hierarchical queries

Modern implementations should NOT rely on the ancestry column. The typus library handles both legacy (with ancestry) and modern (without ancestry) database schemas transparently.

## Integration with Typus Library

The typus library provides async taxonomy services that work with this table structure:

```python
from typus import PostgresTaxonomyService

# Connect to a database with expanded_taxa
service = PostgresTaxonomyService("postgresql+asyncpg://user:pass@host/db")

# Get a taxon - works with or without ancestry column
taxon = await service.get_taxon(47219)

# Traverse hierarchy using parent relationships
async for child in service.children(630955, depth=2):
    print(f"{child.scientific_name} (rank: {child.rank_level})")
```

## Data Sources and Updates

- **Primary Source**: iNaturalist taxonomy exports
- **Common Names**: Catalog of Life Data Package (ColDP) via mapping tables
- **Update Frequency**: Synchronized with iNaturalist data releases
- **Generation Process**: Created via expand_taxa.sh script during ingestion pipeline

## Version History

- **v0r1**: Added immediate ancestor columns, complete ColDP integration
- **v0r0**: Basic expanded taxonomy without common names or immediate ancestors

For implementation details and operational procedures, see the ingestion and ColDP integration documentation.