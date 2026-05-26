"""Estado enable/disable de providers compartido por UI, credenciales y routing."""

from __future__ import annotations

import json

from .constants import PROVIDER_STATE_FILE


PROVIDER_DISABLE_ALIASES = {
    "ollama": {"ollama", "ollama-local"},
    "local": {"ollama", "ollama-local"},
    "ollama-local": {"ollama", "ollama-local"},
    "ollama-cloud": {"ollama-cloud", "ollama-cloud"},
    "ollama_cloud": {"ollama-cloud", "ollama-cloud"},
    "openai": {"openai", "codex"},
    "gpt": {"openai", "codex"},
    "codex": {"openai", "codex"},
    "github": {"github", "copilot"},
    "copilot": {"github", "copilot"},
}


def normalized_provider_id(name: str) -> str:
    return str(name or "").strip().lower().replace("_", "-")


def expand_provider_ids(name: str) -> set[str]:
    raw = normalized_provider_id(name)
    ids = {raw}
    ids.update(PROVIDER_DISABLE_ALIASES.get(raw, set()))
    ids.discard("")
    return ids


def load_provider_state() -> dict:
    try:
        return json.loads(PROVIDER_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"disabled": []}


def save_provider_state(data: dict) -> None:
    PROVIDER_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROVIDER_STATE_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )


def disabled_provider_ids() -> set[str]:
    data = load_provider_state()
    disabled = {
        normalized_provider_id(x)
        for x in data.get("disabled", [])
        if str(x).strip()
    }
    expanded = set(disabled)
    for item in disabled:
        expanded.update(PROVIDER_DISABLE_ALIASES.get(item, set()))
    return expanded
