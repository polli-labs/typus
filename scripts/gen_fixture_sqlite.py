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


def get_immediate_ancestor_info(
    row_dict: dict,
) -> tuple[int | None, int | None]:
    """
    Calculates immediateAncestor_taxonID and immediateAncestor_rankLevel.
    This is equivalent to what was called "true parent" previously.
    """
    current_rank_val = int(row_dict["rankLevel"])
    ancestor_id: int | None = None
    ancestor_rank_level: int | None = None

    # Find the closest ancestor: Smallest rank_value > current_rank_val that has a non-null taxon_id
    parent_candidates = []
    for r_enum_cand in ALL_RANK_ENUMS_SORTED_ASC:  # Iterate from lowest rank value up
        cand_r_val = r_enum_cand.value
        if cand_r_val > current_rank_val:  # Parent rank value must be larger
            db_col_val_str = str(cand_r_val)
            if cand_r_val == 335:
                prefix = "L33_5"
            elif cand_r_val == 345:
                prefix = "L34_5"
            else:
                prefix = f"L{db_col_val_str}"

            tid_at_cand_rank = row_dict.get(f"{prefix}_taxonID")
            if tid_at_cand_rank is not None and str(tid_at_cand_rank).strip() not in ["", "NULL"]:
                try:
                    parent_candidates.append({"id": int(tid_at_cand_rank), "rank_val": cand_r_val})
                except ValueError:
                    continue

    if parent_candidates:
        ancestor_id = parent_candidates[0]["id"]
        ancestor_rank_level = parent_candidates[0]["rank_val"]

    return ancestor_id, ancestor_rank_level


def get_immediate_major_ancestor_info(
    row_dict: dict,
) -> tuple[int | None, int | None]:
    """
    Calculates immediateMajorAncestor_taxonID and immediateMajorAncestor_rankLevel.
    This is equivalent to what was called "major parent" previously.
    """
    current_rank_val = int(row_dict["rankLevel"])
    major_ancestor_id: int | None = None
    major_ancestor_rank_level: int | None = None

    # Find the closest major ancestor: Smallest major_rank_value > current_rank_val that has a non-null taxon_id
    major_parent_candidates = []
    for major_r_val in sorted(list(MAJOR_RANK_VALUES)):  # Iterate major ranks from lowest value up
        if major_r_val > current_rank_val:  # Parent major rank value must be larger
            prefix = f"L{major_r_val}"
            tid_at_major_rank = row_dict.get(f"{prefix}_taxonID")
            if tid_at_major_rank is not None and str(tid_at_major_rank).strip() not in ["", "NULL"]:
                try:
                    major_parent_candidates.append(
                        {"id": int(tid_at_major_rank), "rank_val": major_r_val}
                    )
                except ValueError:
                    continue

    if major_parent_candidates:
        major_ancestor_id = major_parent_candidates[0]["id"]
        major_ancestor_rank_level = major_parent_candidates[0]["rank_val"]

    return major_ancestor_id, major_ancestor_rank_level


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

    for tsv in TSV_DIR.glob("*.tsv"):
        print(f"  → importing {tsv.name}")
        if tsv.stem == "expanded_taxa":  # Process the main expanded_taxa.tsv
            with tsv.open(newline="") as fh:
                reader = csv.DictReader(fh, delimiter="\t")
                original_header = list(reader.fieldnames or [])
                current_header = list(original_header)  # Make a mutable copy

                # Define new column names
                new_col_immediate_ancestor_id = "immediateAncestor_taxonID"
                new_col_immediate_ancestor_rank_level = "immediateAncestor_rankLevel"
                new_col_immediate_major_ancestor_id = "immediateMajorAncestor_taxonID"
                new_col_immediate_major_ancestor_rank_level = "immediateMajorAncestor_rankLevel"
                ancestry_col = "ancestry"  # This one is kept but deprecated

                # Columns to be added to the SQLite table
                # (and potentially to the TSV if we were regenerating it)
                db_columns_to_add = [
                    new_col_immediate_ancestor_id,
                    new_col_immediate_ancestor_rank_level,
                    new_col_immediate_major_ancestor_id,
                    new_col_immediate_major_ancestor_rank_level,
                    ancestry_col,
                ]

                # Remove old parent columns from header if they exist from a previous version of the script/TSV
                # For this script, we assume the input TSV does *not* have these new columns yet,
                # but it might have the *old* derived parent columns.
                # The goal is that the *output SQLite table* has the new columns and *not* the old ones.
                old_parent_cols = [
                    "trueParentID",
                    "trueParentRankLevel",
                    "majorParentID",
                    "majorParentRankLevel",
                ]
                final_db_header = [col for col in current_header if col not in old_parent_cols]

                # Add the new DB columns to the header for SQLite table creation
                for new_col in db_columns_to_add:
                    if new_col not in final_db_header:
                        final_db_header.append(new_col)

                # Ensure commonName is in the header (it is in sample TSV, but could be all empty)
                if "commonName" not in final_db_header:
                    final_db_header.append("commonName")

                cur.execute(f"DROP TABLE IF EXISTS {q(tsv.stem)};")
                cols_ddl_parts = []
                for col_name in final_db_header:
                    if (
                        "taxonID" in col_name
                        or "ParentID" in col_name
                        or "Ancestor_taxonID" in col_name
                    ):  # Covers new names
                        cols_ddl_parts.append(f"{q(col_name)} INTEGER")
                    elif (
                        "RankLevel" in col_name
                        or col_name == "rankLevel"
                        or "Ancestor_rankLevel" in col_name
                    ):  # Covers new names
                        cols_ddl_parts.append(f"{q(col_name)} INTEGER")
                    elif col_name == "taxonActive":
                        cols_ddl_parts.append(f"{q(col_name)} INTEGER")  # 0 or 1
                    else:
                        cols_ddl_parts.append(f"{q(col_name)} TEXT")
                cols_ddl = ", ".join(cols_ddl_parts)
                cur.execute(f"CREATE TABLE {q(tsv.stem)} ({cols_ddl});")

                processed_rows_for_db = []
                for row_dict in reader:
                    # Make a copy to add new computed values for DB insertion
                    db_row_dict = dict(row_dict)

                    # 1. Populate common names (base and ancestral) - if not already present
                    if not db_row_dict.get("commonName") and db_row_dict.get("name"):
                        db_row_dict["commonName"] = (
                            db_row_dict["name"] + "_cmn"
                        )  # Suffix for auto-generated

                    for r_enum in RankLevel:
                        val_str = str(r_enum.value)
                        if r_enum.value == 335:
                            pfix = "L33_5"
                        elif r_enum.value == 345:
                            pfix = "L34_5"
                        else:
                            pfix = f"L{val_str}"

                        common_col = f"{pfix}_commonName"
                        name_col = f"{pfix}_name"
                        if not db_row_dict.get(common_col) and db_row_dict.get(name_col):
                            db_row_dict[common_col] = db_row_dict[name_col] + "_cmn"

                    # 2. Calculate new parent/ancestor info
                    ia_id, ia_rl = get_immediate_ancestor_info(
                        row_dict
                    )  # Use original row_dict from TSV
                    ima_id, ima_rl = get_immediate_major_ancestor_info(row_dict)

                    db_row_dict[new_col_immediate_ancestor_id] = ia_id
                    db_row_dict[new_col_immediate_ancestor_rank_level] = ia_rl
                    db_row_dict[new_col_immediate_major_ancestor_id] = ima_id
                    db_row_dict[new_col_immediate_major_ancestor_rank_level] = ima_rl

                    # 3. Calculate ancestry string (remains as "ancestry" but is deprecated)
                    db_row_dict[ancestry_col] = get_ancestry_str(row_dict)

                    # 4. Handle taxonActive boolean
                    if "taxonActive" in db_row_dict:  # Check in db_row_dict
                        db_row_dict["taxonActive"] = (
                            1 if str(db_row_dict["taxonActive"]).lower() == "t" else 0
                        )

                    # Remove old parent columns from the final dict to be inserted into DB
                    for old_col in old_parent_cols:
                        db_row_dict.pop(old_col, None)

                    processed_rows_for_db.append([db_row_dict.get(col) for col in final_db_header])

                placeholders = ", ".join("?" for _ in final_db_header)
                insert_sql = f"INSERT INTO {q(tsv.stem)} ({', '.join(map(q, final_db_header))}) VALUES ({placeholders});"
                cur.executemany(insert_sql, processed_rows_for_db)
        else:  # For other TSV files like coldp_*, load them as simple tables
            load_table(cur, tsv.stem, tsv)

    conn.commit()
    conn.close()
    print("Fixture DB regenerated →", DB_PATH)


if __name__ == "__main__":
    sys.exit(main())
