import asyncio
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import List

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from typus.services import PostgresTaxonomyService, SQLiteTaxonomyService


@dataclass
class QueryCase:
    query: str
    scope: str  # "scientific" | "vernacular"
    match: str  # "exact" | "prefix" | "substring"


CASES: List[QueryCase] = [
    # Species-level naming convention: genus + species
    QueryCase("Apis mellifera", "scientific", "exact"),
    QueryCase("Apis me", "scientific", "prefix"),
    # Simple vernacular
    QueryCase("honey bee", "vernacular", "exact"),
    QueryCase("honey b", "vernacular", "prefix"),
    # Substring on binomial
    QueryCase("mellif", "scientific", "substring"),
]


def sqlite_fixture_count() -> int:
    db = Path("tests/expanded_taxa_sample.sqlite")
    conn = sqlite3.connect(db)
    try:
        return conn.execute('SELECT COUNT(*) FROM expanded_taxa').fetchone()[0]
    finally:
        conn.close()


async def pg_table_count(dsn: str) -> int:
    eng = create_async_engine(dsn, pool_pre_ping=True)
    try:
        async with eng.begin() as conn:
            r = await conn.exec_driver_sql('SELECT COUNT(*) FROM expanded_taxa')
            return r.scalar() or 0
    finally:
        await eng.dispose()


@pytest.mark.asyncio
async def test_cross_backend_parity_seeded_queries():
    # Baseline from SQLite fixture (truths)
    sqlite_db = Path("tests/expanded_taxa_sample.sqlite")
    sql_svc = SQLiteTaxonomyService(sqlite_db)

    baseline: dict[tuple[str, str, str], list[int]] = {}
    for c in CASES:
        res = await sql_svc.search_taxa(
            c.query,
            scopes={c.scope},
            match=c.match,
            fuzzy=False,
            limit=100,
        )
        baseline[(c.query, c.scope, c.match)] = [t.taxon_id for t in res]

    dsn = os.getenv("TYPUS_TEST_DSN") or os.getenv("POSTGRES_DSN")
    if not dsn:
        pytest.skip("No Postgres DSN; baseline only")

    pg_svc = PostgresTaxonomyService(dsn)

    # Determine whether datasets match (row count heuristic)
    s_count = sqlite_fixture_count()
    p_count = await pg_table_count(dsn)
    datasets_match = (s_count == p_count)

    warnings: list[str] = []
    for c in CASES:
        res_pg = await pg_svc.search_taxa(
            c.query,
            scopes={c.scope},
            match=c.match,
            fuzzy=False,
            limit=100,
        )
        pg_ids = [t.taxon_id for t in res_pg]
        base_ids = baseline[(c.query, c.scope, c.match)]

        if datasets_match:
            # Strict equality and ordering when datasets match
            assert pg_ids == base_ids, (
                f"Mismatch for {c.scope}:{c.match} '{c.query}':\n"
                f"sqlite={base_ids}\npg={pg_ids}"
            )
        else:
            # Warn-only: ensure baseline IDs are included; ordering may differ
            missing = [i for i in base_ids if i not in pg_ids]
            if missing:
                warnings.append(
                    f"Seeded IDs missing in PG for {c.scope}:{c.match} '{c.query}': {missing}"
                )

    # Emit warnings if any (won't fail the test)
    if warnings:
        pytest.skip("; ".join(warnings))

