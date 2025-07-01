from __future__ import annotations

import gzip
import hashlib
import os
import sqlite3
import sys
from pathlib import Path
from typing import Literal

import polars as pl
import requests
from tqdm import tqdm

DEFAULT_URL = os.getenv(
    "TYPUS_EXPANDED_TAXA_URL",
    "https://assets.polli.ai/expanded_taxa/latest/expanded_taxa.sqlite",
)


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
    resp = requests.get(url, stream=True)
    resp.raise_for_status()
    total = int(resp.headers.get("content-length", 0))
    bar = tqdm(total=total, unit="B", unit_scale=True, disable=not sys.stderr.isatty())
    with dest.open("wb") as fh:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                fh.write(chunk)
                bar.update(len(chunk))
    bar.close()

    checksum_url = url + ".sha256"
    try:
        r2 = requests.get(checksum_url)
        if r2.ok:
            expected = r2.text.strip().split()[0]
            h = hashlib.sha256()
            with dest.open("rb") as fh:
                for b in iter(lambda: fh.read(8192), b""):
                    h.update(b)
            if h.hexdigest() != expected:
                dest.unlink(missing_ok=True)
                raise ValueError("Checksum mismatch for " + dest.name)
    except requests.RequestException:
        pass
    return dest


def _tsv_to_sqlite(tsv_path: Path, sqlite_path: Path, mode: Literal["replace", "append"]):
    conn = sqlite3.connect(str(sqlite_path))
    if mode == "replace":
        conn.execute("DROP TABLE IF EXISTS expanded_taxa;")
    if not _schema_ok(conn):
        # create schema from header + ancestry column
        with tsv_path.open("r") as fh:
            header = fh.readline().rstrip("\n").split("\t")
        cols = header + [
            c
            for c in [
                "ancestry",
            ]
            if c not in header
        ]
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
    for batch in frame.collect(streaming=True).iter_slices(n_rows=batch_size):
        pdf = batch.to_pandas()
        if "taxonActive" in pdf.columns:
            pdf["taxonActive"] = pdf["taxonActive"].map(lambda x: 1 if str(x).lower() == "t" else 0)
        # compute ancestry if absent
        if "ancestry" not in pdf.columns:
            ancestry_values = []
            rank_cols = [c for c in pdf.columns if c.startswith("L") and c.endswith("_taxonID")]
            rank_nums = [float(c[1:-8].replace("_", ".")) for c in rank_cols]
            ordered = [x for _, x in sorted(zip(rank_nums, rank_cols), reverse=True)]
            for _idx, row in pdf.iterrows():
                lineage = []
                current = int(row["rankLevel"])
                for col, num in zip(ordered, sorted(rank_nums, reverse=True)):
                    if num >= current:
                        val = row[col]
                        if val not in [None, "", "NULL"]:
                            try:
                                v = int(val)
                                if v not in lineage:
                                    lineage.append(v)
                            except ValueError:
                                pass
                ancestry_values.append("|".join(map(str, lineage)))
            pdf["ancestry"] = ancestry_values
        pdf.to_sql(
            "expanded_taxa", conn, if_exists="append", index=False, method="multi", chunksize=50000
        )
    conn.commit()
    conn.close()


def load_expanded_taxa(
    sqlite_path: Path,
    tsv_path: Path | None = None,
    url: str = DEFAULT_URL,
    if_exists: Literal["fail", "replace", "append"] = "fail",
    *,
    cache_dir: Path | None = None,
    force_self_consistent: bool = False,
) -> Path:
    if cache_dir is None:
        cache_dir = Path(os.getenv("TYPUS_CACHE_DIR", Path.home() / ".cache" / "typus"))
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
        _tsv_to_sqlite(
            tsv_path,
            sqlite_path,
            "replace" if not sqlite_path.exists() else if_exists,
        )
        if force_self_consistent:
            _ensure_self_consistent(sqlite_path)
        return sqlite_path
    # download
    file_name = Path(url).name
    cached = cache_dir / file_name
    if not cached.exists():
        try:
            _download(url, cached)
        except Exception:
            # fallback to TSV
            gz_url = url.rsplit(".", 1)[0] + ".tsv.gz"
            gz_path = cache_dir / Path(gz_url).name
            _download(gz_url, gz_path)
            with gzip.open(gz_path, "rb") as r, (cache_dir / "expanded_taxa.tsv").open("wb") as w:
                w.write(r.read())
            tsv_path = cache_dir / "expanded_taxa.tsv"
            _tsv_to_sqlite(tsv_path, sqlite_path, "replace")
            if force_self_consistent:
                _ensure_self_consistent(sqlite_path)
            return sqlite_path
    sqlite_path.write_bytes(cached.read_bytes())
    if force_self_consistent:
        _ensure_self_consistent(sqlite_path)
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
    args = parser.parse_args()
    mode = "replace" if args.replace else "fail"
    load_expanded_taxa(args.sqlite, args.tsv, args.url, mode, cache_dir=args.cache)


if __name__ == "__main__":  # pragma: no cover - manual invocation
    main()
