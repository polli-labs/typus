from __future__ import annotations

import argparse
import asyncio
from urllib.parse import urlsplit

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from typus.services.pg_test_ops import normalize_test_dsn, resolve_test_dsn


def _mask_dsn(dsn: str) -> str:
    parts = urlsplit(dsn)
    if not parts.netloc:
        return dsn
    userinfo, _, hostinfo = parts.netloc.rpartition("@")
    if not userinfo:
        return dsn
    username, sep, _password = userinfo.partition(":")
    redacted_userinfo = f"{username}{sep}***" if sep else username
    return dsn.replace(parts.netloc, f"{redacted_userinfo}@{hostinfo}", 1)


async def _run_smoke_check(dsn: str, *, table: str) -> None:
    engine = create_async_engine(dsn, pool_pre_ping=True, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            current_db = await conn.scalar(text("SELECT current_database()"))
            if not current_db:
                raise RuntimeError("Connected but current_database() returned no value")

            exists = await conn.scalar(
                text("SELECT to_regclass(:table_name)"), {"table_name": table}
            )
            if exists is None:
                raise RuntimeError(
                    f"Connected to database '{current_db}' but required table '{table}' was not found"
                )
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Smoke-check Postgres connectivity for Typus optional PG tests."
    )
    parser.add_argument(
        "--dsn",
        default=None,
        help="Postgres DSN (defaults to TYPUS_TEST_DSN then POSTGRES_DSN, normalized for test aliases)",
    )
    parser.add_argument(
        "--table",
        default="public.expanded_taxa",
        help="Fully-qualified table checked via to_regclass (default: public.expanded_taxa)",
    )
    args = parser.parse_args()

    dsn = normalize_test_dsn(args.dsn) if args.dsn else resolve_test_dsn()
    if not dsn:
        raise SystemExit(
            "No Postgres DSN configured. Set TYPUS_TEST_DSN (preferred) or POSTGRES_DSN, or pass --dsn."
        )

    try:
        asyncio.run(_run_smoke_check(dsn, table=args.table))
    except Exception as exc:
        raise SystemExit(f"Postgres smoke check failed ({_mask_dsn(dsn)}): {exc}") from exc

    print(f"Postgres smoke check passed ({_mask_dsn(dsn)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
