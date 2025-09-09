import os
import time
import pytest


def _enabled(var: str) -> bool:
    return os.getenv(var, "0") in {"1", "true", "TRUE"}


@pytest.mark.skipif(not _enabled("TYPUS_PERF"), reason="perf tests disabled by default")
@pytest.mark.asyncio
async def test_perf_name_search_sqlite():
    from pathlib import Path
    from typus.services import SQLiteTaxonomyService, load_expanded_taxa

    db = load_expanded_taxa(Path(".cache/typus/expanded_taxa.sqlite"))
    svc = SQLiteTaxonomyService(db)
    t0 = time.perf_counter()
    _ = await svc.search_taxa("Apis", scopes={"scientific"}, match="prefix", fuzzy=True, limit=50)
    dt = time.perf_counter() - t0
    # no strict assertion; print timing for local visibility
    print(f"sqlite search 'Apis' took {dt*1000:.1f} ms")


@pytest.mark.skipif(not _enabled("TYPUS_PERF"), reason="perf tests disabled by default")
@pytest.mark.asyncio
async def test_perf_name_search_postgres():
    import os
    from typus import PostgresTaxonomyService

    dsn = os.getenv("TYPUS_TEST_DSN")
    if not dsn:
        pytest.skip("TYPUS_TEST_DSN not set")
    svc = PostgresTaxonomyService(dsn)
    t0 = time.perf_counter()
    _ = await svc.search_taxa("Apis", scopes={"scientific"}, match="prefix", fuzzy=True, limit=50)
    dt = time.perf_counter() - t0
    print(f"postgres search 'Apis' took {dt*1000:.1f} ms")

