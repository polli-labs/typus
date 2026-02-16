from typus.services.pg_test_ops import (
    is_database_unavailable_error,
    normalize_test_dsn,
    resolve_test_dsn,
)


def test_normalize_test_dsn_rewrites_legacy_db_suffix():
    dsn = "postgresql+asyncpg://user:pass@host:5432/ibrida-v0-r1?sslmode=require"
    assert (
        normalize_test_dsn(dsn)
        == "postgresql+asyncpg://user:pass@host:5432/ibrida-v0?sslmode=require"
    )


def test_resolve_test_dsn_prefers_typus_test_dsn(monkeypatch):
    monkeypatch.setenv("POSTGRES_DSN", "postgresql+asyncpg://user:pass@host:5432/postgres")
    monkeypatch.setenv("TYPUS_TEST_DSN", "postgresql+asyncpg://user:pass@host:5432/ibrida-v0-r1")
    assert resolve_test_dsn() == "postgresql+asyncpg://user:pass@host:5432/ibrida-v0"


def test_is_database_unavailable_error_detects_connectivity_markers():
    err = RuntimeError("connection refused by server")
    assert is_database_unavailable_error(err)
