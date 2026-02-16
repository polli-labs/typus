from __future__ import annotations

import os
from collections.abc import Sequence

DEFAULT_TEST_DSN_ENV_ORDER: tuple[str, ...] = ("TYPUS_TEST_DSN", "POSTGRES_DSN")


def normalize_test_dsn(dsn: str | None) -> str | None:
    """Normalize historical DSN aliases used in test/ops workflows.

    Intentionally scoped to test/ops usage. Runtime services should not silently
    rewrite DSNs.
    """
    if not dsn:
        return dsn
    base, sep, query = dsn.partition("?")
    if base.endswith("/ibrida-v0-r1"):
        base = base.removesuffix("-r1")
    return f"{base}{sep}{query}" if sep else base


def resolve_test_dsn(env_order: Sequence[str] = DEFAULT_TEST_DSN_ENV_ORDER) -> str | None:
    """Resolve the first configured Postgres DSN for tests/ops and normalize it."""
    for env_key in env_order:
        value = os.getenv(env_key)
        if value:
            return normalize_test_dsn(value)
    return None


def is_database_unavailable_error(error: BaseException) -> bool:
    """Heuristic classifier for unavailable/misconfigured Postgres in tests."""
    message = str(error).lower()
    markers = (
        "connection error",
        "cannot connect",
        "connect call failed",
        "connection refused",
        "multiple exceptions",
        "does not exist",
        "invalidcatalognameerror",
        "could not translate host name",
        "name or service not known",
        "timeout expired",
    )
    return any(marker in message for marker in markers)
