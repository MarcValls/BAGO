"""_registry_entries.py — Canonical REGISTRY dict of all BAGO tools.

This module re-exports the fused REGISTRY from split sub-modules.
Import via tool_registry, not directly.
"""
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

from _registry_models import ToolEntry
from _registry_entries_core      import _ENTRIES as _CORE
from _registry_entries_v3        import _ENTRIES as _V3
from _registry_entries_visual    import _ENTRIES as _VISUAL
from _registry_entries_integrity import _ENTRIES as _INTEGRITY

REGISTRY: dict[str, ToolEntry] = {
    **_CORE,
    **_V3,
    **_VISUAL,
    **_INTEGRITY,
}
