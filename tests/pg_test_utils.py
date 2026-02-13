from __future__ import annotations


def normalize_test_dsn(dsn: str | None) -> str | None:
    if not dsn:
        return dsn
    base, sep, query = dsn.partition("?")
    if base.endswith("/ibrida-v0-r1"):
        base = base.removesuffix("-r1")
    return f"{base}{sep}{query}" if sep else base


def is_database_unavailable_error(error: BaseException) -> bool:
    message = str(error).lower()
    markers = (
        "connection error",
        "cannot connect",
        "connect call failed",
        "connection refused",
        "multiple exceptions",
        "does not exist",
        "invalidcatalognameerror",
    )
    return any(marker in message for marker in markers)
