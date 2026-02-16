from pathlib import Path
from typing import AsyncGenerator

import pytest_asyncio

from typus.services import SQLiteTaxonomyService
from typus.services.sqlite_loader import load_expanded_taxa
from typus.services.taxonomy import AbstractTaxonomyService


@pytest_asyncio.fixture(scope="session")
async def taxonomy_service(tmp_path_factory) -> AsyncGenerator[AbstractTaxonomyService, None]:
    """Return SQLite service built from the sample TSV fixture."""
    tmp_dir = tmp_path_factory.mktemp("sqlite_fixture")
    db_path = tmp_dir / "expanded_taxa.sqlite"
    load_expanded_taxa(
        db_path,
        tsv_path=Path("tests/sample_tsv/expanded_taxa_sample.tsv"),
        force_self_consistent=True,
    )
    service = SQLiteTaxonomyService(db_path)
    try:
        yield service
    finally:
        await service.aclose()
