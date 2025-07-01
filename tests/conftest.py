import os
from pathlib import Path
from typing import AsyncGenerator

import pytest_asyncio

from typus.services.sqlite import SQLiteTaxonomyService
from typus.services.sqlite_loader import load_expanded_taxa
from typus.services.taxonomy import AbstractTaxonomyService, PostgresTaxonomyService


@pytest_asyncio.fixture(scope="session")
async def taxonomy_service(tmp_path_factory) -> AsyncGenerator[AbstractTaxonomyService, None]:
    """Return Postgres service if ``POSTGRES_DSN`` is set, else build SQLite from TSV."""
    dsn = os.getenv("POSTGRES_DSN")
    if dsn:
        yield PostgresTaxonomyService(dsn)
    else:
        tmp_dir = tmp_path_factory.mktemp("sqlite_fixture")
        db_path = tmp_dir / "expanded_taxa.sqlite"
        load_expanded_taxa(db_path, tsv_path=Path("tests/sample_tsv/expanded_taxa_lca_sample.tsv"))
        # Ensure parent columns reference available ancestors in the tiny sample
        import sqlite3

        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            UPDATE expanded_taxa
            SET "immediateAncestor_taxonID" = "immediateMajorAncestor_taxonID",
                "immediateAncestor_rankLevel" = "immediateMajorAncestor_rankLevel"
            """
        )
        conn.commit()
        conn.close()

        yield SQLiteTaxonomyService(db_path)
