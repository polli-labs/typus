import os
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.pg_test_utils import resolve_test_dsn
from typus.services.pg_index_helper import ensure_expanded_taxa_indexes
from typus.services.sql_ident import quote_identifier, quote_qualified_name


def test_quote_identifier_rejects_raw_sql_syntax():
    assert quote_identifier("expanded_taxa") == '"expanded_taxa"'
    assert quote_qualified_name("public.expanded_taxa") == '"public"."expanded_taxa"'

    for name in [
        "expanded taxa",
        "expanded_taxa;",
        "expanded_taxa--comment",
        '"expanded_taxa"',
        "public.expanded_taxa.extra",
        "1expanded_taxa",
    ]:
        with pytest.raises(ValueError):
            quote_qualified_name(name)


@pytest.mark.asyncio
async def test_pg_index_helper_quotes_table_names_for_ddl():
    class FakeConnection:
        def __init__(self) -> None:
            self.statements: list[str] = []

        async def exec_driver_sql(self, sql: str) -> None:
            self.statements.append(sql)

    class FakeBegin:
        def __init__(self, conn: FakeConnection) -> None:
            self.conn = conn

        async def __aenter__(self) -> FakeConnection:
            return self.conn

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

    class FakeEngine:
        def __init__(self) -> None:
            self.conn = FakeConnection()

        def begin(self) -> FakeBegin:
            return FakeBegin(self.conn)

    engine = FakeEngine()

    await ensure_expanded_taxa_indexes(
        cast(AsyncEngine, engine),
        schema="public",
        table="expanded_taxa",
        include_major_rank_indexes=False,
        include_pattern_indexes=False,
        include_trigram_indexes=False,
    )

    assert engine.conn.statements
    assert all('"public"."expanded_taxa"' in stmt for stmt in engine.conn.statements)
    assert engine.conn.statements[-1] == 'ANALYZE "public"."expanded_taxa"'


@pytest.mark.asyncio
async def test_pg_index_helper_rejects_invalid_identifiers_before_ddl():
    class FailEngine:
        def begin(self):
            raise AssertionError("DDL should not run for invalid identifiers")

    with pytest.raises(ValueError):
        await ensure_expanded_taxa_indexes(
            cast(AsyncEngine, FailEngine()),
            schema="public",
            table="expanded_taxa; DROP TABLE expanded_taxa",
        )


@pytest.mark.asyncio
async def test_pg_index_helper_runs_idempotently():
    dsn = resolve_test_dsn()
    if not dsn:
        pytest.skip("PG DSN not set")

    if not os.getenv("TYPUS_ALLOW_DDL"):
        pytest.skip("PG DSN not set or DDL not allowed")

    res = await ensure_expanded_taxa_indexes(
        dsn,
        include_major_rank_indexes=True,
        include_pattern_indexes=True,
        include_trigram_indexes=False,  # avoid extension requirements by default
        ensure_pg_trgm_extension=False,
    )

    assert any("idx_immediate_ancestor_taxon_id" in s for s in res.ensured)
    assert any("idx_expanded_taxa_ranklevel" in s for s in res.ensured)
