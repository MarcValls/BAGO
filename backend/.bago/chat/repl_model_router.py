"""repl_model_router.py — Model routing for BAGO.

Provides the Selection dataclass and discover_models() that the /router
bridge endpoints (handlers_router.py) depend on. Also supports dynamic
discovery from Ollama's /api/tags endpoint.

When the SessionManager is available, discover_models() walks its adapter
catalog. Otherwise it falls back to querying the local Ollama daemon
(http://localhost:11434/api/tags) and a hardcoded roster of cloud models.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))
from ollama_discovery import discover_ollama_model_names


@dataclass
class ModelEntry:
    """One selectable model in the picker."""
    provider: str
    model_id: str
    wire_name: str = ""
    context_tokens: int = 0
    best_for: str = ""
    available: bool = True
    selected: bool = False

    def key(self) -> str:
        return f"{self.provider}/{self.model_id}"


@dataclass
class Selection:
    """The full picker state: entries + auto_switch flag."""
    entries: list[ModelEntry] = field(default_factory=list)
    auto_switch: bool = False
    last_pick: str = ""
    last_pick_at: str = ""


# ── Persistence ──────────────────────────────────────────────────────────────

_SELECTION_FILE = ".bago_model_selection.json"


def _selection_path(state_root: Path) -> Path:
    return Path(state_root) / _SELECTION_FILE


def load_selection(state_root: Path) -> Selection:
    """Load the saved selection from disk, or return empty."""
    p = _selection_path(state_root)
    if not p.exists():
        return Selection()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        entries = [ModelEntry(**e) for e in data.get("entries", [])]
        return Selection(
            entries=entries,
            auto_switch=data.get("auto_switch", False),
            last_pick=data.get("last_pick", ""),
            last_pick_at=data.get("last_pick_at", ""),
        )
    except Exception:
        return Selection()


def save_selection(state_root: Path, sel: Selection) -> None:
    """Atomically write the selection to disk (.tmp + os.replace)."""
    p = _selection_path(state_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "entries": [
            {
                "provider": e.provider,
                "model_id": e.model_id,
                "wire_name": e.wire_name,
                "context_tokens": e.context_tokens,
                "best_for": e.best_for,
                "available": e.available,
                "selected": e.selected,
            }
            for e in sel.entries
        ],
        "auto_switch": sel.auto_switch,
        "last_pick": sel.last_pick,
        "last_pick_at": sel.last_pick_at,
    }
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(str(tmp), str(p))


# ── Toggle / auto_switch helpers ─────────────────────────────────────────────

def toggle(sel: Selection, key: str) -> Selection:
    """Toggle the `selected` flag for the entry matching key."""
    for e in sel.entries:
        if e.key() == key:
            e.selected = not e.selected
            return sel
    raise KeyError(f"Modelo no encontrado: {key}")


def set_auto_switch(sel: Selection, enabled: bool) -> Selection:
    sel.auto_switch = enabled
    return sel


def pick(sel: Selection) -> Optional[ModelEntry]:
    """Pick the first selected+available model. Updates last_pick."""
    for e in sel.entries:
        if e.selected and e.available:
            sel.last_pick = e.key()
            sel.last_pick_at = time.strftime("%Y-%m-%dT%H:%M:%S")
            return e
    return None


# ── Discovery ────────────────────────────────────────────────────────────────

# Hardcoded fallback roster (used when neither SessionManager nor Ollama
# are available). Includes cloud models for reference even if keys aren't
# configured yet.
_DISABLED_LOCAL_MODELS = {"llama3.2:1b", "qwen2.5:1.5b"}

_FALLBACK: list[ModelEntry] = [
    # Local Ollama
    ModelEntry("ollama-local", "llama3.2:3b",  "llama3.2:3b",  32768, "general (mid)",     True),
    ModelEntry("ollama-local", "granite3.2:8b", "granite3.2:8b", 32768, "reasoning",        True),
    ModelEntry("ollama-local", "bago-orchestrator", "bago-orchestrator", 32768, "planning", True),
    ModelEntry("ollama-local", "bago-eyes",    "bago-eyes",    32768, "vision",            True),
    ModelEntry("ollama-local", "bago-llama32-bago-persona", "bago-llama32-bago-persona", 32768, "persona", True),
    ModelEntry("ollama-local", "minicpm-v",    "minicpm-v",    32768, "vision alt",        True),
    # Cloud (requires keys — marked unavailable until configured)
    ModelEntry("anthropic", "claude-sonnet-4", "claude-sonnet-4", 200000, "coding",  False),
    ModelEntry("openai",    "gpt-4o",         "gpt-4o",          128000, "general", False),
]


def _discover_ollama_local() -> list[ModelEntry]:
    """Query Ollama /api/tags for dynamically installed models."""
    entries: list[ModelEntry] = []
    try:
        for name in discover_ollama_model_names("http://localhost:11434"):
            if name in _DISABLED_LOCAL_MODELS:
                continue
            entries.append(ModelEntry(
                provider="ollama-local",
                model_id=name,
                wire_name=name,
                context_tokens=32768,
                best_for=_guess_best_for(name),
                available=True,
            ))
    except Exception:
        pass
    return entries


_BEST_FOR_HINTS = {
    "coder": "coding",
    "code": "coding",
    "orchestrator": "planning",
    "eyes": "vision",
    "vision": "vision",
    "minicpm": "vision",
    "persona": "persona",
    "granite": "reasoning",
    "llama3.2:3b": "general (mid)",
    "qwen2.5": "fast summarization",
    "qwen3": "general",
    "deepseek": "reasoning",
}


def _guess_best_for(model_name: str) -> str:
    name_lower = model_name.lower()
    for hint, label in _BEST_FOR_HINTS.items():
        if hint in name_lower:
            return label
    return "general"


def discover_models(manager=None) -> list[ModelEntry]:
    """Discover available models.

    Priority:
    1. SessionManager adapter catalog (if manager is provided)
    2. Local Ollama daemon (/api/tags) — dynamic discovery
    3. Hardcoded fallback roster
    """
    # 1. Try SessionManager catalog
    if manager is not None:
        try:
            catalog = manager.list_model_catalog()
            if catalog:
                entries = []
                for item in catalog:
                    model_id = item.get("model_id", item.get("id", ""))
                    if model_id in _DISABLED_LOCAL_MODELS:
                        continue
                    entries.append(ModelEntry(
                        provider=item.get("provider", "unknown"),
                        model_id=model_id,
                        wire_name=item.get("wire_name", item.get("model_id", "")),
                        context_tokens=item.get("context_tokens", 32768),
                        best_for=item.get("best_for", "general"),
                        available=item.get("available", True),
                    ))
                return entries
        except Exception:
            pass

    # 2. Try Ollama /api/tags (dynamic)
    ollama_entries = _discover_ollama_local()
    if ollama_entries:
        # Merge with cloud fallback (cloud entries remain unavailable)
        local_keys = {e.key() for e in ollama_entries}
        cloud_entries = [e for e in _FALLBACK if e.provider not in ("ollama-local",)]
        return ollama_entries + cloud_entries

    # 3. Hardcoded fallback
    return list(_FALLBACK)


def render_picker(sel: Selection) -> str:
    """Render a text picker for the REPL (box-drawing glyphs)."""
    lines = ["╭─ Model Router ────────────────────────────╮"]
    lines.append("│  ☑ checked  ☐ unchecked  ● available      │")
    lines.append("├──────────────────────────────────────────┤")
    for e in sel.entries:
        check = "☑" if e.selected else "☐"
        avail = "●" if e.available else "○"
        lines.append(f"│  {check} {avail} {e.provider}/{e.model_id:30s} │")
    lines.append("├──────────────────────────────────────────┤")
    lines.append(f"│  auto_switch: {'ON ' if sel.auto_switch else 'OFF'}{'':26s}│")
    lines.append("╰──────────────────────────────────────────╯")
    return "\n".join(lines)


def render_selection(sel: Selection) -> str:
    """One-line summary of current selection."""
    count = sum(1 for e in sel.entries if e.selected)
    return f"{count} modelos seleccionados · auto_switch={'ON' if sel.auto_switch else 'OFF'}"
