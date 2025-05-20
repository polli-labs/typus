#!/usr/bin/env python
"""
Regenerate tests/fixture_typus.sqlite from TSV snippets.

Run:  python scripts/gen_fixture_sqlite.py
"""

from __future__ import annotations

import csv
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TSV_DIR = ROOT / "tests" / "sample_tsv"
DB_PATH = ROOT / "tests" / "fixture_typus.sqlite"

INT_RE = re.compile(r"^-?\d+$")


def sql_type(val: str | None) -> str:
    return "INTEGER" if val is not None and INT_RE.fullmatch(val) else "TEXT"


def q(name: str) -> str:  # quote identifier
    return f'"{name}"'


def load_table(cur: sqlite3.Cursor, table: str, src: Path) -> None:
    with src.open(newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        rows = list(reader)
        if not rows:
            return
        header = reader.fieldnames or []

    cols_ddl = ", ".join(f"{q(col)} {sql_type(rows[0][col])}" for col in header)
    cur.execute(f"CREATE TABLE {q(table)} ({cols_ddl});")

    placeholders = ", ".join("?" for _ in header)
    insert = (
        f"INSERT INTO {q(table)} ({', '.join(map(q, header))}) VALUES ({placeholders});"
    )
    cur.executemany(insert, [[row[col] for col in header] for row in rows])


def main() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # load every .tsv as its own table
    for tsv in TSV_DIR.glob("*.tsv"):
        print(f"  → importing {tsv.name}")
        load_table(cur, tsv.stem, tsv)

    # expanded_taxa_cmn = copy with vernacular alias
    cur.execute(
        """
        CREATE TABLE "expanded_taxa_cmn" AS
        SELECT *, "commonName" AS vernacular FROM "expanded_taxa";
        """
    )

    conn.commit()
    conn.close()
    print("Fixture DB regenerated →", DB_PATH)


if __name__ == "__main__":
    sys.exit(main())
