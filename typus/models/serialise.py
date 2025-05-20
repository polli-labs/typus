from __future__ import annotations

from pydantic import BaseModel, ConfigDict


def _to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(p.title() for p in parts[1:])


class CompactJsonMixin(BaseModel):
    """Mixin adding `.to_json()` with snakes‑to‑camel plus exclude‑None."""

    def to_json(self, *, indent=None) -> str:
        return self.model_dump_json(indent=indent, exclude_none=True, by_alias=True)

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )
