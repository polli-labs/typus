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
TYPUS_CONSTANTS_PATH = ROOT / "typus" / "constants.py"  # Path to typus constants
DB_PATH = ROOT / "tests" / "fixture_typus.sqlite"

INT_RE = re.compile(r"^-?\d+$")


def sql_type(val: str | None) -> str:
    return "INTEGER" if val is not None and INT_RE.fullmatch(val) else "TEXT"


def q(name: str) -> str:  # quote identifier
    return f'"{name}"'


# Dynamically load RankLevel and MAJOR_LEVELS from typus.constants
def _load_typus_constants():
    import importlib.util

    spec = importlib.util.spec_from_file_location("typus.constants", TYPUS_CONSTANTS_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load typus.constants from {TYPUS_CONSTANTS_PATH}")
    constants_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(constants_module)
    return constants_module.RankLevel, constants_module.MAJOR_LEVELS


RankLevel, MAJOR_LEVELS = _load_typus_constants()
ALL_RANK_ENUMS_SORTED_ASC = sorted(
    list(RankLevel), key=lambda r: r.value
)  # Sort by rank value, low to high
ALL_RANK_ENUMS_SORTED_DESC = sorted(
    list(RankLevel), key=lambda r: r.value, reverse=True
)  # Sort by rank value, high to low
MAJOR_RANK_VALUES = {rl.value for rl in MAJOR_LEVELS}


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
    insert = f"INSERT INTO {q(table)} ({', '.join(map(q, header))}) VALUES ({placeholders});"
    cur.executemany(insert, [[row[col] for col in header] for row in rows])


def get_parent_info(row_dict: dict) -> tuple[int | None, int | None, int | None, int | None]:
    current_rank_val = int(row_dict["rankLevel"])  # TSV stores rankLevel as int string
    true_parent_id: int | None = None
    true_parent_rank_level: int | None = None
    major_parent_id: int | None = None
    major_parent_rank_level: int | None = None

    # True Parent: Smallest rank_value > current_rank_val that has a non-null taxon_id in this row's L{X}_taxonID columns
    parent_candidates = []
    for r_enum_cand in ALL_RANK_ENUMS_SORTED_ASC:  # Iterate from lowest rank value up
        cand_r_val = r_enum_cand.value
        if cand_r_val > current_rank_val:  # Parent rank value must be larger
            db_col_val_str = str(cand_r_val)
            if cand_r_val == 335:
                prefix = "L33_5"  # Match TSV column names
            elif cand_r_val == 345:
                prefix = "L34_5"
            else:
                prefix = f"L{db_col_val_str}"

            tid_at_cand_rank = row_dict.get(f"{prefix}_taxonID")
            if tid_at_cand_rank is not None and str(tid_at_cand_rank).strip() not in ["", "NULL"]:
                try:
                    parent_candidates.append({"id": int(tid_at_cand_rank), "rank_val": cand_r_val})
                except ValueError:
                    continue  # Skip if not a valid integer

    if parent_candidates:
        # The first one found (due to ALL_RANK_ENUMS_SORTED_ASC) will be the closest parent
        true_parent_id = parent_candidates[0]["id"]
        true_parent_rank_level = parent_candidates[0]["rank_val"]

    # Major Parent: Smallest major_rank_value > current_rank_val that has a non-null taxon_id
    major_parent_candidates = []
    for major_r_val in sorted(list(MAJOR_RANK_VALUES)):  # Iterate major ranks from lowest value up
        if major_r_val > current_rank_val:  # Parent major rank value must be larger
            prefix = f"L{major_r_val}"  # Major ranks use L{val} format in TSV (e.g., L10, L20)
            tid_at_major_rank = row_dict.get(f"{prefix}_taxonID")
            if tid_at_major_rank is not None and str(tid_at_major_rank).strip() not in ["", "NULL"]:
                try:
                    major_parent_candidates.append(
                        {"id": int(tid_at_major_rank), "rank_val": major_r_val}
                    )
                except ValueError:
                    continue

    if major_parent_candidates:
        # The first one found will be the closest major parent
        major_parent_id = major_parent_candidates[0]["id"]
        major_parent_rank_level = major_parent_candidates[0]["rank_val"]

    return true_parent_id, true_parent_rank_level, major_parent_id, major_parent_rank_level


def get_ancestry_str(row_dict: dict) -> str:
    lineage_ids_ordered = []
    current_taxon_rank_val = int(row_dict["rankLevel"])

    # Iterate all RankLevels from highest (e.g. L70 Kingdom) down to current_taxon_rank_val inclusive
    for r_enum_anc in ALL_RANK_ENUMS_SORTED_DESC:  # High rank value to low rank value
        anc_r_val = r_enum_anc.value
        if anc_r_val >= current_taxon_rank_val:
            db_col_val_str = str(anc_r_val)
            if anc_r_val == 335:
                prefix = "L33_5"  # Match TSV column names
            elif anc_r_val == 345:
                prefix = "L34_5"
            else:
                prefix = f"L{db_col_val_str}"

            id_val = row_dict.get(f"{prefix}_taxonID")
            if id_val is not None and str(id_val).strip() not in ["", "NULL"]:
                try:
                    id_int = int(id_val)
                    # The L{X}_taxonID for rank X is the ancestor at that rank.
                    # The list forms from highest rank to lowest for self.
                    # We want root -> self. This order is correct if L-cols are populated correctly.
                    lineage_ids_ordered.append(id_int)
                except ValueError:
                    pass  # Skip if not a valid integer

    # Remove duplicates while preserving order (from highest rank to current rank)
    # The L{X}_taxonID columns are supposed to represent the *unique* ancestor at that rank level.
    # So, theoretically, all IDs in lineage_ids_ordered should already be unique if the source expanded_taxa is correct.
    # However, a simple unique pass is safe.
    seen = set()
    unique_lineage_ids = [x for x in lineage_ids_ordered if not (x in seen or seen.add(x))]

    return "|".join(map(str, unique_lineage_ids))


def main() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    expanded_taxa_final_rows = []
    for tsv in TSV_DIR.glob("*.tsv"):
        print(f"  → importing {tsv.name}")
        if tsv.stem == "expanded_taxa":  # Process the main expanded_taxa.tsv
            with tsv.open(newline="") as fh:
                reader = csv.DictReader(fh, delimiter="\t")
                original_header = list(reader.fieldnames or [])

                # Add new derived columns to the header for SQLite table creation
                new_columns_to_add = [
                    "trueParentID",
                    "trueParentRankLevel",
                    "majorParentID",
                    "majorParentRankLevel",
                    "ancestry",
                ]
                final_header = original_header + [
                    nc for nc in new_columns_to_add if nc not in original_header
                ]
                # Ensure commonName is in the header if not already (it is in sample)
                if (
                    "commonName" not in final_header and "commonName" not in original_header
                ):  # commonName is in sample TSV, but might be empty
                    final_header.append("commonName")

                cur.execute(f"DROP TABLE IF EXISTS {q(tsv.stem)};")
                # SQLite uses dynamic typing, but TEXT is safe for most things. INTEGER for IDs and ranks.
                # For boolean taxonActive, store as INTEGER (0 or 1)
                cols_ddl_parts = []
                for col_name in final_header:
                    if "taxonID" in col_name or "ParentID" in col_name:
                        cols_ddl_parts.append(f"{q(col_name)} INTEGER")
                    elif "RankLevel" in col_name or col_name == "rankLevel":
                        cols_ddl_parts.append(f"{q(col_name)} INTEGER")
                    elif col_name == "taxonActive":
                        cols_ddl_parts.append(f"{q(col_name)} INTEGER")  # 0 or 1
                    else:
                        cols_ddl_parts.append(f"{q(col_name)} TEXT")
                cols_ddl = ", ".join(cols_ddl_parts)
                cur.execute(f"CREATE TABLE {q(tsv.stem)} ({cols_ddl});")

                for row_dict in reader:
                    # 1. Populate common names (base and ancestral)
                    if not row_dict.get("commonName") and row_dict.get("name"):
                        row_dict["commonName"] = row_dict["name"] + "_cmn"

                    for r_enum in RankLevel:  # Iterate through all RankLevel members
                        val_str = str(r_enum.value)
                        # Construct pfix based on TSV column naming (L<num>, L<num>_5)
                        if r_enum.value == 335:
                            pfix = "L33_5"
                        elif r_enum.value == 345:
                            pfix = "L34_5"
                        else:
                            pfix = f"L{val_str}"

                        if not row_dict.get(f"{pfix}_commonName") and row_dict.get(f"{pfix}_name"):
                            row_dict[f"{pfix}_commonName"] = row_dict[f"{pfix}_name"] + "_cmn"

                    # 2. Calculate parent info
                    tp_id, tp_rl, mp_id, mp_rl = get_parent_info(row_dict)
                    row_dict["trueParentID"] = tp_id
                    row_dict["trueParentRankLevel"] = tp_rl
                    row_dict["majorParentID"] = mp_id
                    row_dict["majorParentRankLevel"] = mp_rl

                    # 3. Calculate ancestry string
                    row_dict["ancestry"] = get_ancestry_str(row_dict)

                    # 4. Handle taxonActive boolean
                    if "taxonActive" in row_dict:  # 't' or 'f' in sample TSV
                        row_dict["taxonActive"] = (
                            1 if str(row_dict["taxonActive"]).lower() == "t" else 0
                        )

                    expanded_taxa_final_rows.append([row_dict.get(col) for col in final_header])

                placeholders = ", ".join("?" for _ in final_header)
                insert_sql = f"INSERT INTO {q(tsv.stem)} ({', '.join(map(q, final_header))}) VALUES ({placeholders});"
                cur.executemany(insert_sql, expanded_taxa_final_rows)
        else:  # For other TSV files like coldp_*, load them as simple tables
            load_table(cur, tsv.stem, tsv)

    conn.commit()
    conn.close()
    print("Fixture DB regenerated →", DB_PATH)


if __name__ == "__main__":
    sys.exit(main())
