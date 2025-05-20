"""Rank levels, canonical names, and fuzzy helpers."""

from __future__ import annotations

import enum
from functools import lru_cache
from typing import Dict

from rapidfuzz import fuzz, process


class RankLevel(enum.IntEnum):
    # major ranks
    L10 = 10  # species
    L20 = 20  # genus
    L30 = 30  # family
    L40 = 40  # order
    L50 = 50  # class
    L60 = 60  # phylum
    L70 = 70  # kingdom
    # selected minor / half‑levels (multiplied by 10 for integrality)
    L05 = 5  # subspecies
    L11 = 11  # complex
    L12 = 12  # subsection
    L13 = 13  # section
    L15 = 15  # subgenus
    L24 = 24  # subtribe
    L25 = 25  # tribe
    L26 = 26  # supertribe
    L27 = 27  # subfamily
    L32 = 32  # epifamily
    L33 = 33  # superfamily
    L335 = 335  # zoosubsection (infra‑order half‑level)
    L34 = 34  # zoosection
    L345 = 345  # parvorder
    L35 = 35  # infraorder
    L37 = 37  # suborder
    L43 = 43  # superorder
    L44 = 44  # subterclass
    L45 = 45  # infraclass
    L47 = 47  # subclass
    L53 = 53  # superclass
    L57 = 57  # subphylum
    L67 = 67  # subkingdom
    L100 = 100  # stateofmatter / life


# canonical mapping level → english name
RANK_CANON: Dict[RankLevel, str] = {
    RankLevel.L05: "subspecies",
    RankLevel.L10: "species",
    RankLevel.L11: "complex",
    RankLevel.L12: "subsection",
    RankLevel.L13: "section",
    RankLevel.L15: "subgenus",
    RankLevel.L20: "genus",
    RankLevel.L24: "subtribe",
    RankLevel.L25: "tribe",
    RankLevel.L26: "supertribe",
    RankLevel.L27: "subfamily",
    RankLevel.L30: "family",
    RankLevel.L32: "epifamily",
    RankLevel.L33: "superfamily",
    RankLevel.L335: "zoosubsection",
    RankLevel.L34: "zoosection",
    RankLevel.L345: "parvorder",
    RankLevel.L35: "infraorder",
    RankLevel.L37: "suborder",
    RankLevel.L40: "order",
    RankLevel.L43: "superorder",
    RankLevel.L44: "subterclass",
    RankLevel.L45: "infraclass",
    RankLevel.L47: "subclass",
    RankLevel.L50: "class",
    RankLevel.L53: "superclass",
    RankLevel.L57: "subphylum",
    RankLevel.L60: "phylum",
    RankLevel.L67: "subkingdom",
    RankLevel.L70: "kingdom",
    RankLevel.L100: "stateofmatter",
}

# reverse mapping incl. simple aliases
NAME_TO_RANK: Dict[str, RankLevel] = {}
for lvl, nm in RANK_CANON.items():
    NAME_TO_RANK[nm] = lvl
    NAME_TO_RANK[nm.lower()] = lvl  # guard
# Add additional ad‑hoc aliases
NAME_TO_RANK.update(
    {
        "sp": RankLevel.L10,
        "gen": RankLevel.L20,
        "fam": RankLevel.L30,
    }
)


@lru_cache(maxsize=1024)
def infer_rank(name: str, *, cutoff: int = 80) -> RankLevel | None:
    """Return the best‑matching RankLevel for *name* using RapidFuzz.
    If no candidate exceeds *cutoff* (0‑100), return ``None``.
    """
    name_l = name.lower()
    if name_l in NAME_TO_RANK:
        return NAME_TO_RANK[name_l]
    match, score, _ = process.extractOne(
        name_l, NAME_TO_RANK.keys(), scorer=fuzz.WRatio, score_cutoff=cutoff
    ) or (None, 0, None)
    return NAME_TO_RANK.get(match) if match else None


# utility predicates
MAJOR_LEVELS = {
    RankLevel.L10,
    RankLevel.L20,
    RankLevel.L30,
    RankLevel.L40,
    RankLevel.L50,
    RankLevel.L60,
    RankLevel.L70,
}


def is_major(rank: RankLevel) -> bool:  # noqa: D401
    """Return ``True`` iff *rank* is one of the seven Linnaean major ranks."""
    return rank in MAJOR_LEVELS


def is_minor(rank: RankLevel) -> bool:
    return not is_major(rank)
