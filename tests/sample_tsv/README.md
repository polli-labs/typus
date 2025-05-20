# Sample Data for Testing

This directory contains sample data files that can be used for unit testing with SQLite or other lightweight database solutions. These samples are extracted from the ibridaDB database and provide realistic data structures and relationships for testing.

## Files Included

### ColDP Tables

These files contain samples from the Catalog of Life Data Package (ColDP) tables:

- `coldp_name_usage.tsv`: Scientific names and taxonomic information
- `coldp_vernacular_name.tsv`: Common names in various languages
- `coldp_distribution.tsv`: Geographic distribution information
- `coldp_media.tsv`: Links to images, sounds, and other media
- `coldp_reference.tsv`: Bibliographic references
- `coldp_type_material.tsv`: Type specimen information

### Mapping and Taxa Tables

- `inat_to_coldp_taxon_map.tsv`: Crosswalk between iNaturalist taxa and Catalog of Life taxa
- `expanded_taxa_sample.tsv`: Sample of the expanded_taxa table with taxonomic hierarchies and common names

## Usage for SQLite Testing

These files can be used to create a lightweight SQLite database for unit testing, particularly for the typus SDK. Here's an example of how to load them into SQLite:

```python
import sqlite3
import pandas as pd

# Create SQLite connection
conn = sqlite3.connect('test_db.sqlite')

# Load each TSV file into a table
for table_name in ['coldp_name_usage', 'coldp_vernacular_name', 'coldp_distribution', 
                  'coldp_media', 'coldp_reference', 'coldp_type_material',
                  'inat_to_coldp_taxon_map', 'expanded_taxa_sample']:
    df = pd.read_csv(f'{table_name}.tsv', sep='\t')
    df.to_sql(table_name, conn, if_exists='replace', index=False)

# Create view for expanded_taxa_cmn if needed
conn.execute('''
CREATE VIEW IF NOT EXISTS expanded_taxa_cmn AS
SELECT * FROM expanded_taxa_sample
''')

conn.commit()
conn.close()
```

## Table Relationships

The relationships between these tables mirror those in the full database:

- `inat_to_coldp_taxon_map.inat_taxon_id` → `expanded_taxa_sample.taxonID`
- `inat_to_coldp_taxon_map.col_taxon_id` → `coldp_name_usage.ID`
- `coldp_vernacular_name.taxonID` → `coldp_name_usage.ID`
- `coldp_distribution.taxonID` → `coldp_name_usage.ID`
- `coldp_media.taxonID` → `coldp_name_usage.ID`
- `coldp_reference.ID` is referenced by other tables' `referenceID` fields

## Notes

- These samples contain a limited subset of records for testing purposes
- All data relationships are preserved to allow for testing of joins and foreign key relationships
- The expanded_taxa_sample table includes full taxonomic hierarchies with common names for testing
- These files can be easily imported into a SQLite database or any other database system