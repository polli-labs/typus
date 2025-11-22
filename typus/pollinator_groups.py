from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional, Set


class PollinatorGroup(str, Enum):
    """Coarse pollinator groupings for UI labels and summaries."""

    BEE = "Bee"
    BUTTERFLY_MOTH = "Butterfly/Moth"
    FLY = "Fly"
    WASP = "Wasp"
    BEETLE = "Beetle"
    BIRD = "Bird"
    BAT = "Bat"
    OTHER = "Other"


@dataclass(frozen=True)
class PollinatorGroupDef:
    group: PollinatorGroup
    root_taxon_id: int
    note: Optional[str] = None


# Root taxon IDs come from the bundled expanded_taxa snapshot (2025-06-28).
POLLINATOR_GROUP_DEFS: tuple[PollinatorGroupDef, ...] = (
    PollinatorGroupDef(PollinatorGroup.BEE, 630955, note="Anthophila epifamily"),
    PollinatorGroupDef(PollinatorGroup.BUTTERFLY_MOTH, 47157, note="Order Lepidoptera"),
    PollinatorGroupDef(PollinatorGroup.FLY, 47822, note="Order Diptera"),
    PollinatorGroupDef(PollinatorGroup.WASP, 52747, note="Family Vespidae"),
    PollinatorGroupDef(PollinatorGroup.BEETLE, 47208, note="Order Coleoptera"),
    PollinatorGroupDef(PollinatorGroup.BIRD, 3, note="Class Aves"),
    PollinatorGroupDef(PollinatorGroup.BAT, 40268, note="Order Chiroptera"),
)


def pollinator_groups_for_ancestry(ancestry: Iterable[int]) -> Set[PollinatorGroup]:
    """Map an ancestry path (root → self) to high‑level pollinator groups.

    Returns a *set* to allow multiple memberships, but most taxa will match
    zero or one group. Callers may decide to fall back to ``{PollinatorGroup.OTHER}``
    when the returned set is empty.
    """

    ids = set(ancestry)
    matches: set[PollinatorGroup] = set()
    for defn in POLLINATOR_GROUP_DEFS:
        if defn.root_taxon_id in ids:
            matches.add(defn.group)
    return matches


__all__ = [
    "PollinatorGroup",
    "PollinatorGroupDef",
    "POLLINATOR_GROUP_DEFS",
    "pollinator_groups_for_ancestry",
]
