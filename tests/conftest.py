import asyncio
import os
import sqlite3

import pytest

from typus.models.taxon import Taxon
from typus.services.taxonomy import AbstractTaxonomyService, PostgresTaxonomyService

FIXTURE = os.path.join(os.path.dirname(__file__), "fixture_typus.sqlite")


class SQLiteTaxonomyService(AbstractTaxonomyService):
    def __init__(self, path: str = FIXTURE):
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._loop = asyncio.get_event_loop()

    async def get_taxon(self, taxon_id: int) -> Taxon:
        row = self._loop.run_in_executor(
            None,
            lambda: self._conn.execute(
                "SELECT * FROM expanded_taxa WHERE taxon_id=?", (taxon_id,)
            ).fetchone(),
        )
        row = await row
        if row is None:
            raise KeyError(taxon_id)
        return Taxon(
            taxon_id=row["taxon_id"],
            scientific_name=row["scientific_name"],
            rank_level=row["rank_level"],
            parent_id=row["parent_id"],
            ancestry=[],
        )


# pytest fixture selecting service
@pytest.fixture(scope="session")
async def taxonomy_service():
    dsn = os.getenv("POSTGRES_DSN")
    if dsn:
        yield PostgresTaxonomyService(dsn)
    else:
        yield SQLiteTaxonomyService()
