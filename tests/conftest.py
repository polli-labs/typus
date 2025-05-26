import os
from typing import AsyncGenerator

import pytest_asyncio

from typus.services.sqlite import SQLiteTaxonomyService
from typus.services.taxonomy import AbstractTaxonomyService, PostgresTaxonomyService


@pytest_asyncio.fixture(scope="session")
async def taxonomy_service() -> AsyncGenerator[AbstractTaxonomyService, None]:
    """Async fixture: returns Postgres service if POSTGRES_DSN is set, else SQLite."""
    dsn = os.getenv("POSTGRES_DSN")
    if dsn:
        yield PostgresTaxonomyService(dsn)
    else:
        yield SQLiteTaxonomyService()
