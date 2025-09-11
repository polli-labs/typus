from __future__ import annotations

import asyncio
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


@dataclass
class EnsureResult:
    ensured: list[str]
    errors: list[tuple[str, str]]


DDL_CORE = [
    # Parentage + rank filters
    'CREATE INDEX IF NOT EXISTS idx_immediate_ancestor_taxon_id ON {fqtn} ("immediateAncestor_taxonID")',
    'CREATE INDEX IF NOT EXISTS idx_immediate_major_ancestor_taxon_id ON {fqtn} ("immediateMajorAncestor_taxonID")',
    'CREATE INDEX IF NOT EXISTS idx_expanded_taxa_ranklevel ON {fqtn} ("rankLevel")',
    # Compound helpful for rank-filtered scientific name prefix queries
    'CREATE INDEX IF NOT EXISTS idx_expanded_taxa_rank_name ON {fqtn} ("rankLevel", lower((name)::text))',
]


DDL_PATTERN = [
    # Case-insensitive exact/prefix: use text_pattern_ops on lower(expression)
    "CREATE INDEX IF NOT EXISTS idx_expanded_taxa_lower_name_pattern ON {fqtn} (lower((name)::text) text_pattern_ops)",
    'CREATE INDEX IF NOT EXISTS idx_expanded_taxa_lower_common_pattern ON {fqtn} (lower(("commonName")::text) text_pattern_ops)',
]


DDL_TRGM = [
    # Substring acceleration; requires pg_trgm
    "CREATE INDEX IF NOT EXISTS idx_expanded_taxa_lower_name_trgm ON {fqtn} USING gin (lower((name)::text) gin_trgm_ops)",
    'CREATE INDEX IF NOT EXISTS idx_expanded_taxa_lower_common_trgm ON {fqtn} USING gin (lower(("commonName")::text) gin_trgm_ops)',
]


def _major_rank_index_ddls(fqtn: str) -> list[str]:
    levels = [10, 20, 30, 40, 50, 60, 70]
    ddls = []
    for lv in levels:
        ddls.append(
            f'CREATE INDEX IF NOT EXISTS idx_expanded_taxa_l{lv}_taxonid ON {fqtn} ("L{lv}_taxonID")'
        )
    return ddls


async def ensure_expanded_taxa_indexes(
    engine_or_dsn: str | AsyncEngine,
    *,
    schema: str = "public",
    table: str = "expanded_taxa",
    include_major_rank_indexes: bool = True,
    include_pattern_indexes: bool = True,
    include_trigram_indexes: bool = True,
    ensure_pg_trgm_extension: bool = False,
) -> EnsureResult:
    """Ensure recommended indexes exist on expanded_taxa.

    - Does NOT create a redundant btree on taxonID (PK already covers).
    - Plain name btree is omitted by default; lower(name) pattern index supersedes our queries.
    - Trigram indexes require pg_trgm; enabling `ensure_pg_trgm_extension` attempts CREATE EXTENSION.
    """
    if isinstance(engine_or_dsn, str):
        engine = create_async_engine(engine_or_dsn, pool_pre_ping=True)
        _own_engine = True
    else:
        engine = engine_or_dsn
        _own_engine = False

    fqtn = f'"{schema}".{table}' if schema else table

    ddls: list[str] = []
    ddls.extend([s.format(fqtn=fqtn) for s in DDL_CORE])
    if include_pattern_indexes:
        ddls.extend([s.format(fqtn=fqtn) for s in DDL_PATTERN])
    if include_trigram_indexes:
        ddls.extend([s.format(fqtn=fqtn) for s in DDL_TRGM])
    if include_major_rank_indexes:
        ddls.extend(_major_rank_index_ddls(fqtn))

    ensured: list[str] = []
    errors: list[tuple[str, str]] = []

    async with engine.begin() as conn:
        # Extension (optional – may require superuser)
        if include_trigram_indexes and ensure_pg_trgm_extension:
            try:
                await conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS pg_trgm")
                ensured.append("extension:pg_trgm")
            except Exception as e:  # pragma: no cover - depends on permissions
                errors.append(("extension:pg_trgm", str(e)))

        for ddl in ddls:
            name = ddl.split(" ")[4] if " INDEX IF NOT EXISTS " in ddl else ddl
            try:
                await conn.exec_driver_sql(ddl)
                ensured.append(name)
            except Exception as e:  # pragma: no cover - env specific
                errors.append((name, str(e)))

        # Update stats
        try:
            await conn.exec_driver_sql(f"ANALYZE {fqtn}")
            ensured.append("ANALYZE")
        except Exception as e:  # pragma: no cover
            errors.append(("ANALYZE", str(e)))

    if _own_engine:
        await engine.dispose()
    return EnsureResult(ensured=ensured, errors=errors)


def cli() -> None:  # pragma: no cover - thin wrapper
    import argparse
    import os

    p = argparse.ArgumentParser(description="Ensure Postgres indexes for expanded_taxa")
    p.add_argument("--dsn", default=os.getenv("POSTGRES_DSN") or os.getenv("TYPUS_TEST_DSN"))
    p.add_argument("--schema", default="public")
    p.add_argument("--table", default="expanded_taxa")
    p.add_argument("--no-major", action="store_true", help="Skip per-major rank L*_taxonID indexes")
    p.add_argument("--no-pattern", action="store_true", help="Skip lower(..) pattern indexes")
    p.add_argument("--no-trgm", action="store_true", help="Skip trigram indexes")
    p.add_argument("--ensure-trgm", action="store_true", help="Attempt CREATE EXTENSION pg_trgm")
    args = p.parse_args()

    if not args.dsn:
        raise SystemExit("No DSN provided via --dsn or env POSTGRES_DSN/TYPUS_TEST_DSN")

    res = asyncio.run(
        ensure_expanded_taxa_indexes(
            args.dsn,
            schema=args.schema,
            table=args.table,
            include_major_rank_indexes=not args.no_major,
            include_pattern_indexes=not args.no_pattern,
            include_trigram_indexes=not args.no_trgm,
            ensure_pg_trgm_extension=args.ensure_trgm,
        )
    )
    # Print a short summary
    print("ensured:")
    for n in res.ensured:
        print("  ", n)
    if res.errors:
        print("errors:")
        for n, e in res.errors:
            print("  ", n, "->", e)
