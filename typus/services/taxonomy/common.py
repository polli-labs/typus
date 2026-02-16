"""Shared helpers used by both SQLite and Postgres taxonomy backends."""

from __future__ import annotations

from collections.abc import Mapping, Set
from typing import Any

from rapidfuzz import fuzz

from ...constants import RankLevel, is_major
from ...models.taxon import Taxon


def col_prefix_for_level(level: RankLevel) -> str:
    if level.value == 335:
        return "L33_5"
    if level.value == 345:
        return "L34_5"
    return f"L{int(level.value)}"


def ancestry_pairs_from_mapping(row: Mapping[str, Any]) -> list[tuple[int, RankLevel]]:
    """Return ancestry as (taxon_id, rank_level) pairs in root->self order."""
    pairs: list[tuple[int, RankLevel]] = []
    levels_desc = sorted([lvl for lvl in RankLevel], key=lambda r: int(r.value), reverse=True)
    for lvl in levels_desc:
        prefix = col_prefix_for_level(lvl)
        col = f"{prefix}_taxonID"
        val = row.get(col)
        if val is not None:
            pairs.append((int(val), lvl))

    self_tid = row.get("taxonID") or row.get("taxon_id")
    self_rank = row.get("rankLevel") or row.get("rank_level")
    if self_tid is None or self_rank is None:
        raise KeyError("Row mapping is missing taxonID/rankLevel fields")

    pairs.append((int(self_tid), RankLevel(int(self_rank))))

    seen: set[int] = set()
    out: list[tuple[int, RankLevel]] = []
    for tid, lvl in pairs:
        if tid not in seen:
            out.append((tid, lvl))
            seen.add(tid)
    return out


def filtered_ancestry_ids(row: Mapping[str, Any], include_minor_ranks: bool) -> list[int]:
    has_expanded = any(k.startswith("L") and k.endswith("_taxonID") for k in row.keys())
    if not has_expanded:
        return []
    pairs = ancestry_pairs_from_mapping(row)
    return [tid for tid, lvl in pairs if include_minor_ranks or is_major(lvl)]


def score_taxon_match(
    query: str,
    *,
    scientific_name: str | None,
    vernacular_name: str | None,
    scopes: Set[str],
) -> float:
    """Compute fuzzy score against all active scopes and return best match."""
    q_norm = query.strip().lower()
    if not q_norm:
        return 0.0

    candidates: list[str] = []
    if "scientific" in scopes and scientific_name:
        candidates.append(scientific_name.strip())
    if "vernacular" in scopes and vernacular_name:
        candidates.append(vernacular_name.strip())

    if not candidates:
        fallback = scientific_name or vernacular_name
        if not fallback:
            return 0.0
        candidates = [fallback.strip()]

    return max(float(fuzz.WRatio(q_norm, candidate.lower()) / 100.0) for candidate in candidates)


def taxon_from_search_row(
    row: Mapping[str, Any],
    *,
    ancestry: list[int] | None = None,
) -> Taxon:
    taxon_id_raw = row.get("taxonID")
    if taxon_id_raw is None:
        taxon_id_raw = row.get("taxon_id")
    if taxon_id_raw is None:
        raise KeyError("Row mapping is missing taxonID/taxon_id")

    scientific_name_raw = row.get("name")
    if scientific_name_raw is None:
        scientific_name_raw = row.get("scientific_name")
    if scientific_name_raw is None:
        raise KeyError("Row mapping is missing name/scientific_name")

    rank_level_raw = row.get("rankLevel")
    if rank_level_raw is None:
        rank_level_raw = row.get("rank_level")
    if rank_level_raw is None:
        raise KeyError("Row mapping is missing rankLevel/rank_level")

    parent_raw = row.get("immediateAncestor_taxonID")
    if parent_raw is None:
        parent_raw = row.get("parent_id")

    common_name_raw = row.get("commonName")
    if common_name_raw is None:
        common_name_raw = row.get("common_name")

    return Taxon(
        taxon_id=int(taxon_id_raw),
        scientific_name=str(scientific_name_raw),
        rank_level=RankLevel(int(rank_level_raw)),
        parent_id=int(parent_raw) if parent_raw is not None else None,
        ancestry=ancestry or [],
        vernacular={"en": [str(common_name_raw)]} if common_name_raw else {},
    )
