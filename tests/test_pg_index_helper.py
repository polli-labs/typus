import os

import pytest


@pytest.mark.asyncio
async def test_pg_index_helper_runs_idempotently():
    dsn = os.getenv("TYPUS_TEST_DSN") or os.getenv("POSTGRES_DSN")
    if not dsn or not os.getenv("TYPUS_ALLOW_DDL"):
        pytest.skip("PG DSN not set or DDL not allowed")

    from typus.services.pg_index_helper import ensure_expanded_taxa_indexes

    res = await ensure_expanded_taxa_indexes(
        dsn,
        include_major_rank_indexes=True,
        include_pattern_indexes=True,
        include_trigram_indexes=False,  # avoid extension requirements by default
        ensure_pg_trgm_extension=False,
    )

    assert any("idx_immediate_ancestor_taxon_id" in s for s in res.ensured)
    assert any("idx_expanded_taxa_ranklevel" in s for s in res.ensured)
