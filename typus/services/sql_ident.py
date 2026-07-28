from __future__ import annotations

import re

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def quote_identifier(name: str) -> str:
    """Quote a simple SQL identifier after rejecting raw SQL syntax."""
    if not _IDENTIFIER_RE.fullmatch(name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return f'"{name}"'


def quote_qualified_name(name: str) -> str:
    """Quote a table name, allowing only ``table`` or ``schema.table``."""
    parts = name.split(".")
    if not 1 <= len(parts) <= 2:
        raise ValueError(f"Invalid SQL qualified name: {name!r}")
    return ".".join(quote_identifier(part) for part in parts)
