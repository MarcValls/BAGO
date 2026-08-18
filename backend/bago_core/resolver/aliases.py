from __future__ import annotations

from typing import Any


def build_alias_index(entries: tuple[Any, ...]) -> dict[str, str]:
    index: dict[str, str] = {}
    for entry in entries:
        entry_id = getattr(entry, "id", None)
        if not entry_id and isinstance(entry, dict):
            entry_id = entry.get("id")
        alias_values = getattr(entry, "aliases", None)
        if alias_values is None and isinstance(entry, dict):
            alias_values = entry.get("aliases", [])
        index[str(entry_id)] = str(entry_id)
        for alias in alias_values or ():
            index.setdefault(str(alias), str(entry_id))
    return index
