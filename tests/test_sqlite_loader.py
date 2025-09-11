import gzip
import sqlite3
from pathlib import Path

import pytest

from typus.services.sqlite_loader import load_expanded_taxa


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


def test_cache_hit(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    cached = cache / "expanded_taxa.sqlite"
    cached.write_text("dummy")
    out = tmp_path / "out.sqlite"
    load_expanded_taxa(out, url="http://example.com/expanded_taxa.sqlite", cache_dir=cache)
    assert out.read_text() == "dummy"


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
