import gzip
import hashlib
import sqlite3
from pathlib import Path

import pytest

from typus.services import sqlite_loader
from typus.services.sqlite_loader import _cached_sqlite_ok, _download, load_expanded_taxa


def row_count(db: Path) -> int:
    conn = sqlite3.connect(db)
    try:
        cur = conn.execute("SELECT COUNT(*) FROM expanded_taxa")
        return cur.fetchone()[0]
    finally:
        conn.close()


def test_round_trip_tsv(tmp_path: Path) -> None:
    db = tmp_path / "exp.sqlite"
    tsv = Path("tests/sample_tsv/expanded_taxa_sample.tsv")
    load_expanded_taxa(db, tsv_path=tsv)
    assert row_count(db) == sum(1 for _ in tsv.open()) - 1


def test_auto_download_fallback(httpserver, tmp_path: Path) -> None:
    tsv = Path("tests/sample_tsv/expanded_taxa_sample.tsv")
    gz = gzip.compress(tsv.read_bytes())
    httpserver.expect_request("/expanded_taxa/latest/expanded_taxa.sqlite").respond_with_data(
        "", status=404
    )
    httpserver.expect_request("/expanded_taxa/latest/expanded_taxa.tsv.gz").respond_with_data(gz)
    url = httpserver.url_for("/expanded_taxa/latest/expanded_taxa.sqlite")

    db = tmp_path / "exp.sqlite"
    load_expanded_taxa(db, url=url, cache_dir=tmp_path)
    assert row_count(db) == sum(1 for _ in tsv.open()) - 1


def test_valid_sqlite_cache_hit_stays_offline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sample = Path("tests/sample_tsv/expanded_taxa_sample.tsv")
    source = tmp_path / "source.sqlite"
    load_expanded_taxa(source, tsv_path=sample)

    cache = tmp_path / "cache"
    cache.mkdir()
    cached = cache / "expanded_taxa.sqlite"
    cached.write_bytes(source.read_bytes())

    def fail_get(*_args, **_kwargs):
        pytest.fail("valid SQLite cache hit should not contact the network")

    monkeypatch.setattr(sqlite_loader.requests, "get", fail_get)

    out = tmp_path / "out.sqlite"
    load_expanded_taxa(out, url="http://example.com/expanded_taxa.sqlite", cache_dir=cache)
    assert row_count(out) == sum(1 for _ in sample.open()) - 1


def test_invalid_sqlite_cache_is_rejected_and_falls_back(httpserver, tmp_path: Path) -> None:
    sample = Path("tests/sample_tsv/expanded_taxa_sample.tsv")
    gz = gzip.compress(sample.read_bytes())
    httpserver.expect_request("/expanded_taxa/latest/expanded_taxa.sqlite").respond_with_data(
        "", status=404
    )
    httpserver.expect_request("/expanded_taxa/latest/expanded_taxa.tsv.gz").respond_with_data(gz)
    url = httpserver.url_for("/expanded_taxa/latest/expanded_taxa.sqlite")

    cache = tmp_path / "cache"
    cache.mkdir()
    cached = cache / "expanded_taxa.sqlite"
    cached.write_text("dummy")

    out = tmp_path / "out.sqlite"
    load_expanded_taxa(out, url=url, cache_dir=cache)

    assert row_count(out) == sum(1 for _ in sample.open()) - 1
    assert out.read_bytes() != b"dummy"
    assert not cached.exists()


def test_corrupt_sqlite_cache_with_readable_schema_is_rejected_and_falls_back(
    httpserver, tmp_path: Path
) -> None:
    sample = Path("tests/sample_tsv/expanded_taxa_sample.tsv")
    gz = gzip.compress(sample.read_bytes())
    httpserver.expect_request("/expanded_taxa/latest/expanded_taxa.sqlite").respond_with_data(
        "", status=404
    )
    httpserver.expect_request("/expanded_taxa/latest/expanded_taxa.tsv.gz").respond_with_data(gz)
    url = httpserver.url_for("/expanded_taxa/latest/expanded_taxa.sqlite")

    cache = tmp_path / "cache"
    cache.mkdir()
    cached = cache / "expanded_taxa.sqlite"
    _write_sqlite_with_corrupt_late_page(cached)

    conn = sqlite3.connect(cached)
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info('expanded_taxa')")}
    finally:
        conn.close()
    assert {
        "taxonID",
        "rankLevel",
        "name",
        "immediateAncestor_taxonID",
        "immediateMajorAncestor_taxonID",
    }.issubset(cols)
    assert not _cached_sqlite_ok(cached)

    out = tmp_path / "out.sqlite"
    load_expanded_taxa(out, url=url, cache_dir=cache)

    assert row_count(out) == sum(1 for _ in sample.open()) - 1
    assert not cached.exists()
    assert _cached_sqlite_ok(out)


def test_download_failure_cleans_partial_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class BrokenResponse:
        headers = {"content-length": "6"}

        def raise_for_status(self) -> None:
            return None

        def iter_content(self, chunk_size: int):
            assert chunk_size == 8192
            yield b"abc"
            raise sqlite_loader.requests.RequestException("interrupted")

    def fake_get(url: str, **_kwargs):
        assert url == "http://example.com/expanded_taxa.sqlite"
        return BrokenResponse()

    monkeypatch.setattr(sqlite_loader.requests, "get", fake_get)

    dest = tmp_path / "expanded_taxa.sqlite"
    with pytest.raises(sqlite_loader.requests.RequestException):
        _download("http://example.com/expanded_taxa.sqlite", dest)

    assert not dest.exists()
    assert not dest.with_name(dest.name + ".part").exists()


def test_download_uses_timeouts_for_artifact_and_checksum(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    payload = b"sqlite-bytes"
    calls = []

    class Response:
        def __init__(self, body: bytes = b"", text: str = "", ok: bool = True) -> None:
            self.body = body
            self.text = text
            self.ok = ok
            self.headers = {"content-length": str(len(body))}

        def raise_for_status(self) -> None:
            return None

        def iter_content(self, chunk_size: int):
            assert chunk_size == 8192
            yield self.body

    def fake_get(url: str, **kwargs):
        calls.append((url, kwargs))
        if url.endswith(".sha256"):
            return Response(text=hashlib.sha256(payload).hexdigest())
        return Response(body=payload)

    monkeypatch.setattr(sqlite_loader.requests, "get", fake_get)

    dest = tmp_path / "expanded_taxa.sqlite"
    _download("http://example.com/expanded_taxa.sqlite", dest)

    assert dest.read_bytes() == payload
    assert calls == [
        (
            "http://example.com/expanded_taxa.sqlite",
            {"stream": True, "timeout": sqlite_loader.DOWNLOAD_TIMEOUT},
        ),
        (
            "http://example.com/expanded_taxa.sqlite.sha256",
            {"timeout": sqlite_loader.DOWNLOAD_TIMEOUT},
        ),
    ]


def test_replace_append(tmp_path: Path) -> None:
    db = tmp_path / "exp.sqlite"
    tsv = Path("tests/sample_tsv/expanded_taxa_sample.tsv")
    load_expanded_taxa(db, tsv_path=tsv)
    load_expanded_taxa(db, tsv_path=tsv, if_exists="append")
    assert row_count(db) == 2 * (sum(1 for _ in tsv.open()) - 1)
    load_expanded_taxa(db, tsv_path=tsv, if_exists="replace")
    assert row_count(db) == sum(1 for _ in tsv.open()) - 1


def _index_names(db: Path) -> set[str]:
    conn = sqlite3.connect(db)
    try:
        cur = conn.execute("PRAGMA index_list('expanded_taxa')")
        return {row[1] for row in cur.fetchall()}
    finally:
        conn.close()


def test_indexes_created_by_default(tmp_path: Path) -> None:
    db = tmp_path / "exp.sqlite"
    tsv = Path("tests/sample_tsv/expanded_taxa_sample.tsv")
    load_expanded_taxa(db, tsv_path=tsv)
    idx = _index_names(db)
    # A few key indexes should exist
    assert {
        "idx_expanded_taxa_taxon_id",
        "idx_expanded_taxa_ranklevel",
        "idx_expanded_taxa_lower_name",
        "idx_expanded_taxa_lower_commonName",
    }.issubset(idx)


def test_disable_indexes_emits_warning(tmp_path: Path) -> None:
    db = tmp_path / "exp.sqlite"
    tsv = Path("tests/sample_tsv/expanded_taxa_sample.tsv")
    with pytest.warns(UserWarning):
        load_expanded_taxa(db, tsv_path=tsv, create_indexes=False)
    assert _index_names(db) == set()


def _write_sqlite_with_corrupt_late_page(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA page_size = 1024")
        conn.execute("PRAGMA journal_mode = OFF")
        conn.execute(
            """
            CREATE TABLE expanded_taxa (
                "taxonID" INTEGER,
                "rankLevel" INTEGER,
                "name" TEXT,
                "immediateAncestor_taxonID" INTEGER,
                "immediateMajorAncestor_taxonID" INTEGER,
                "payload" TEXT
            )
            """
        )
        payload = "x" * 800
        conn.executemany(
            """
            INSERT INTO expanded_taxa (
                "taxonID",
                "rankLevel",
                "name",
                "immediateAncestor_taxonID",
                "immediateMajorAncestor_taxonID",
                "payload"
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                (idx, 10, f"taxon-{idx}", idx - 1 if idx > 1 else None, 1, payload)
                for idx in range(1, 400)
            ),
        )
        conn.commit()
        conn.execute("VACUUM")
        page_size = conn.execute("PRAGMA page_size").fetchone()[0]
        page_count = conn.execute("PRAGMA page_count").fetchone()[0]
    finally:
        conn.close()

    with path.open("r+b") as handle:
        handle.seek(page_size * (page_count - 1))
        handle.write(b"\xff" * page_size)
