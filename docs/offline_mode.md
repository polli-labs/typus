# Offline Mode & SQLite Fixture Generation

This document provides a brief overview of using Typus in an offline mode, particularly concerning the generation and use of the SQLite fixture.

## SQLite Fixture

The `typus` package can utilize an SQLite database as a backend for taxonomy services, which is especially useful for offline environments, testing, or CI pipelines.

### Generation
The primary script for generating this SQLite fixture is `scripts/gen_fixture_sqlite.py`. This script processes data from TSV files (typically found in `tests/sample_tsv/`) to populate the `expanded_taxa` table and others in the SQLite database (`tests/fixture_typus.sqlite`).

Key columns, including parentage information like `immediateAncestor_taxonID` and `immediateMajorAncestor_taxonID`, are derived during this generation process.

### ORM Mapping
The ORM mappings for the `expanded_taxa` table, including how Python attributes map to database columns, can be found in `typus/orm/expanded_taxa.py`.

For more details on data models, please refer to [Models Documentation](./models.md).

Users intending to work with or regenerate the SQLite fixture should consult these files.
