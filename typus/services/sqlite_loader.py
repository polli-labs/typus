from __future__ import annotations

import gzip
import hashlib
import os
import sqlite3
import sys
from pathlib import Path
from typing import Literal, cast

try:
    import polars as pl
    import requests
    from tqdm import tqdm
except ModuleNotFoundError as exc:  # pragma: no cover - dependency wiring guard
    missing = exc.name or "loader dependency"
    raise ModuleNotFoundError(
        f"`typus.services.sqlite_loader` requires optional dependency '{missing}'. "
        'Install with `uv pip install "polli-typus[loader]"`.'
    ) from exc

# Interim default points directly at the Backblaze B2 `public-0` object store.
# The branded `assets.polli.ai` host was a now-retired VPS; restoring a branded
# origin (Cloudflare / box in front of B2) is deferred (POL-1810). Override with
# `$TYPUS_EXPANDED_TAXA_URL` or the loader/CLI `--url` flag.
DEFAULT_URL = os.getenv(
    "TYPUS_EXPANDED_TAXA_URL",
    "https://f005.backblazeb2.com/file/public-0/expanded_taxa/latest/expanded_taxa.sqlite",
)
DOWNLOAD_TIMEOUT = (10, 120)


def _schema_ok(conn: sqlite3.Connection) -> bool:
    cur = conn.execute("PRAGMA table_info('expanded_taxa');")
    cols = {row[1] for row in cur.fetchall()}
    required = {
        "taxonID",
        "rankLevel",
        "name",
        "immediateAncestor_taxonID",
        "immediateMajorAncestor_taxonID",
    }
    return required.issubset(cols)


def _ensure_self_consistent(db: Path) -> None:
    conn = sqlite3.connect(str(db))
    conn.execute(
        """
        UPDATE expanded_taxa
        SET "immediateAncestor_taxonID" = "immediateMajorAncestor_taxonID",
            "immediateAncestor_rankLevel" = "immediateMajorAncestor_rankLevel"
        WHERE "immediateAncestor_taxonID" IS NULL
           OR "immediateAncestor_taxonID" NOT IN (SELECT "taxonID" FROM expanded_taxa)
        """
    )
    conn.commit()
    conn.close()


def _download(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_dest = dest.with_name(dest.name + ".part")
    tmp_dest.unlink(missing_ok=True)
    try:
        resp = requests.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT)
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        bar = tqdm(total=total, unit="B", unit_scale=True, disable=not sys.stderr.isatty())
        try:
            with tmp_dest.open("wb") as fh:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        fh.write(chunk)
                        bar.update(len(chunk))
        finally:
            bar.close()

        checksum_url = url + ".sha256"
        try:
            r2 = requests.get(checksum_url, timeout=DOWNLOAD_TIMEOUT)
            if r2.ok:
                expected = r2.text.strip().split()[0]
                h = hashlib.sha256()
                with tmp_dest.open("rb") as fh:
                    for b in iter(lambda: fh.read(8192), b""):
                        h.update(b)
                if h.hexdigest() != expected:
                    tmp_dest.unlink(missing_ok=True)
                    raise ValueError("Checksum mismatch for " + dest.name)
        except requests.RequestException:
            pass
        tmp_dest.replace(dest)
    except Exception:
        tmp_dest.unlink(missing_ok=True)
        raise
    return dest


def _cached_sqlite_ok(path: Path) -> bool:
    try:
        conn = sqlite3.connect(str(path))
        try:
            if not _schema_ok(conn):
                return False
            rows = conn.execute("PRAGMA quick_check;").fetchall()
            return bool(rows) and all(row[0] == "ok" for row in rows)
        finally:
            conn.close()
    except sqlite3.DatabaseError:
        return False


def _tsv_to_sqlite(tsv_path: Path, sqlite_path: Path, mode: Literal["replace", "append"]):
    conn = sqlite3.connect(str(sqlite_path))
    if mode == "replace":
        conn.execute("DROP TABLE IF EXISTS expanded_taxa;")
    if not _schema_ok(conn):
        # create schema from header
        with tsv_path.open("r") as fh:
            header = fh.readline().rstrip("\n").split("\t")
        cols = header
        col_defs = []
        for c in cols:
            if (
                c.endswith("_taxonID")
                or c.endswith("RankLevel")
                or c in {"taxonID", "rankLevel", "taxonActive"}
            ):
                col_defs.append(f'"{c}" INTEGER')
            else:
                col_defs.append(f'"{c}" TEXT')
        conn.execute(f"CREATE TABLE IF NOT EXISTS expanded_taxa ({', '.join(col_defs)});")
    # streaming read
    frame = pl.scan_csv(tsv_path, separator="\t")
    batch_size = 50000
    streamed = cast(pl.DataFrame, frame.collect(engine="streaming"))
    for batch in streamed.iter_slices(n_rows=batch_size):
        pdf = batch.to_pandas()
        if "taxonActive" in pdf.columns:
            pdf["taxonActive"] = pdf["taxonActive"].map(lambda x: 1 if str(x).lower() == "t" else 0)
        pdf.to_sql(
            "expanded_taxa", conn, if_exists="append", index=False, method="multi", chunksize=50000
        )
    conn.commit()
    conn.close()


def _create_indexes(sqlite_path: Path) -> None:
    """Create recommended indexes for expanded_taxa SQLite database.

    The indexes speed up common lookups and name search patterns used by
    SQLiteTaxonomyService. Idempotent and safe to run multiple times.
    """
    conn = sqlite3.connect(str(sqlite_path))
    try:
        cur = conn.cursor()
        # Fast PK lookups and parent traversals
        cur.execute(
            'CREATE INDEX IF NOT EXISTS idx_expanded_taxa_taxon_id ON expanded_taxa("taxonID")'
        )
        cur.execute(
            'CREATE INDEX IF NOT EXISTS idx_expanded_taxa_imm_ancestor ON expanded_taxa("immediateAncestor_taxonID")'
        )
        cur.execute(
            'CREATE INDEX IF NOT EXISTS idx_expanded_taxa_imm_major_ancestor ON expanded_taxa("immediateMajorAncestor_taxonID")'
        )
        # Rank filter and ordering aid
        cur.execute(
            'CREATE INDEX IF NOT EXISTS idx_expanded_taxa_ranklevel ON expanded_taxa("rankLevel")'
        )
        # Expression indexes for case-insensitive search
        cur.execute(
            'CREATE INDEX IF NOT EXISTS idx_expanded_taxa_lower_name ON expanded_taxa(LOWER("name"))'
        )
        cur.execute(
            'CREATE INDEX IF NOT EXISTS idx_expanded_taxa_lower_commonName ON expanded_taxa(LOWER("commonName"))'
        )
        # Gather statistics to help the planner
        cur.execute("ANALYZE")
        conn.commit()
    finally:
        conn.close()


def load_expanded_taxa(
    sqlite_path: Path,
    tsv_path: Path | None = None,
    url: str = DEFAULT_URL,
    if_exists: Literal["fail", "replace", "append"] = "fail",
    *,
    cache_dir: Path | None = None,
    force_self_consistent: bool = False,
    create_indexes: bool = True,
) -> Path:
    if cache_dir is None:
        cache_dir = Path(os.getenv("TYPUS_CACHE_DIR", Path.home() / ".cache" / "typus"))

    def build_from_tsv_gz() -> Path:
        gz_url = url.rsplit(".", 1)[0] + ".tsv.gz"
        gz_path = cache_dir / Path(gz_url).name
        _download(gz_url, gz_path)
        with gzip.open(gz_path, "rb") as r, (cache_dir / "expanded_taxa.tsv").open("wb") as w:
            w.write(r.read())
        local_tsv_path = cache_dir / "expanded_taxa.tsv"
        _tsv_to_sqlite(local_tsv_path, sqlite_path, "replace")
        return sqlite_path

    if sqlite_path.exists():
        conn = sqlite3.connect(str(sqlite_path))
        if _schema_ok(conn) and if_exists == "fail":
            conn.close()
            return sqlite_path
        conn.close()
        if if_exists == "replace":
            sqlite_path.unlink()
    if tsv_path is not None:
        if tsv_path.suffix == ".gz":
            with gzip.open(tsv_path, "rb") as r, (cache_dir / tsv_path.stem).open("wb") as w:
                w.write(r.read())
            tsv_path = cache_dir / tsv_path.stem
        load_mode: Literal["replace", "append"]
        if not sqlite_path.exists():
            load_mode = "replace"
        elif if_exists == "append":
            load_mode = "append"
        else:
            load_mode = "replace"

        _tsv_to_sqlite(tsv_path, sqlite_path, load_mode)
        if force_self_consistent:
            _ensure_self_consistent(sqlite_path)
        if create_indexes:
            # Only create indexes if this looks like a valid expanded_taxa database
            try:
                conn = sqlite3.connect(str(sqlite_path))
                ok = _schema_ok(conn)
                conn.close()
            except Exception:
                ok = False
            if ok:
                _create_indexes(sqlite_path)
            # If not ok, silently skip (e.g., cache hit test writes a dummy file)
        else:
            import warnings as _warnings

            _warnings.warn(
                "SQLite indexes were not created. Expect slower name search and ancestry operations.",
                stacklevel=1,
            )
        return sqlite_path
    # download
    file_name = Path(url).name
    cached = cache_dir / file_name
    validate_cached_sqlite = cached.suffix == ".sqlite"
    if cached.exists() and validate_cached_sqlite and not _cached_sqlite_ok(cached):
        cached.unlink()
    if not cached.exists():
        try:
            _download(url, cached)
        except Exception:
            # fallback to TSV
            build_from_tsv_gz()
            if force_self_consistent:
                _ensure_self_consistent(sqlite_path)
            if create_indexes:
                try:
                    conn = sqlite3.connect(str(sqlite_path))
                    ok = _schema_ok(conn)
                    conn.close()
                except Exception:
                    ok = False
                if ok:
                    _create_indexes(sqlite_path)
            else:
                import warnings as _warnings

                _warnings.warn(
                    "SQLite indexes were not created. Expect slower name search and ancestry operations.",
                    stacklevel=1,
                )
            return sqlite_path
    sqlite_path.write_bytes(cached.read_bytes())
    if validate_cached_sqlite and not _cached_sqlite_ok(sqlite_path):
        sqlite_path.unlink(missing_ok=True)
        cached.unlink(missing_ok=True)
        build_from_tsv_gz()
    if force_self_consistent:
        _ensure_self_consistent(sqlite_path)
    if create_indexes:
        try:
            conn = sqlite3.connect(str(sqlite_path))
            ok = _schema_ok(conn)
            conn.close()
        except Exception:
            ok = False
        if ok:
            _create_indexes(sqlite_path)
    else:
        import warnings as _warnings

        _warnings.warn(
            "SQLite indexes were not created. Expect slower name search and ancestry operations.",
            stacklevel=1,
        )
    return sqlite_path


def main() -> None:
    """Entry point for ``typus-load-sqlite`` CLI."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Download or build expanded_taxa SQLite DB",
    )
    parser.add_argument("--sqlite", type=Path, required=True)
    parser.add_argument("--tsv", type=Path)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--cache", type=Path)
    try:
        # Python 3.10+: provides --with-indexes / --no-with-indexes
        from argparse import BooleanOptionalAction

        parser.add_argument(
            "--with-indexes",
            action=BooleanOptionalAction,
            default=True,
            help="Create recommended SQLite indexes (default: on)",
        )
    except Exception:
        parser.add_argument("--with-indexes", action="store_true", default=True)
    args = parser.parse_args()
    mode = "replace" if args.replace else "fail"
    if not getattr(args, "with_indexes", True):
        print(
            "WARNING: --with-indexes disabled. Expect slower name search and ancestry operations.",
            file=sys.stderr,
        )
    load_expanded_taxa(
        args.sqlite,
        args.tsv,
        args.url,
        mode,
        cache_dir=args.cache,
        create_indexes=getattr(args, "with_indexes", True),
    )


if __name__ == "__main__":  # pragma: no cover - manual invocation
    main()
