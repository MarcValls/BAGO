#!/usr/bin/env python3
"""

_CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo
config_manager.py — BAGO 4.1.5 Configuration Manager

Gestiona la configuración persistente del sistema en `.bago/config.json`.
Soporta defaults de provider, modelos favoritos, timeouts, y flags de features.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from state_paths import resolve_state_root
from bago_core.user_state_paths import state_read_candidates

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


DEFAULT_CONFIG: dict[str, Any] = {
    "default_provider": "ollama-cloud",
    "default_model": "deepseek-v3.1:671b",
    "system_prompt": "",
    "temperature": 0.7,
    "max_tokens": None,
    "timeout_seconds": 60.0,
    "providers": {
        "ollama-local": {
            "enabled": True,
            "base_url": "http://127.0.0.1:11434",
        },
        "ollama-cloud": {
            "enabled": True,
            "base_url": "",
        },
        "copilot": {
            "enabled": False,
        },
        "anthropic": {
            "enabled": False,
        },
        "codex": {
            "enabled": False,
        },
        "openrouter": {
            "enabled": False,
        },
        "opencode": {
            "enabled": False,
            "base_url": "",
        },
    },
    "features": {
        "streaming": True,
        "tool_calling": True,
        "auto_allow_tools": False,
        "tool_approval_policy": "ask",
        "compression_on_downgrade": True,
        "rl_learning": True,
        "auto_evolve_on_start": True,
        "workspace_retrieval": True,
        "directory_context": True,
    },
    "model_catalog": {
        "mode": "all",
        "production_mode": "available-only",
    },
    "sources": {
        "read_roots": [],
    },
    "ollama": {
        "models_path": "",
    },
    "vision": {
        "model": "",
        "timeout_s": 180,
    },
    "ui": {
        "color": True,
        "multiline": True,
        "history": True,
        "prompt_provider_on_start": True,
    },
}


class ConfigManager:
    """Gestiona `.bago/config.json`."""

    def __init__(self, base_path: str | None = None, state_root: str | None = None):
        self.base_path = Path(base_path or os.getcwd())
        # An explicit state root is an isolation boundary. Do not let a
        # caller asking for a temporary/test state accidentally inherit a
        # user's global config through state_read_candidates().
        self._explicit_state_root = bool(str(state_root or "").strip())
        self.config_dir = resolve_state_root(state_root)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.config_dir / "config.json"
        self.config_source_path = self.config_path
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        source_path = None
        candidates = (self.config_path,) if self._explicit_state_root else state_read_candidates("config.json")
        for path in candidates:
            if path.exists():
                source_path = path
                break
        if source_path is not None:
            try:
                self._data = json.loads(source_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self._data = {}
        else:
            self._data = {}
            source_path = self.config_path
        # Merge with defaults (preserving user values)
        self._merge_defaults(DEFAULT_CONFIG)
        if self._data.get("default_provider") == "ollama-local":
            self._data["default_provider"] = "ollama-cloud"
        if self._data.get("default_model") == "llama3.2:3b":
            self._data["default_model"] = "deepseek-v3.1:671b"
        self.config_source_path = source_path
        if source_path == self.config_path or source_path is None:
            self._save()

    def _merge_defaults(self, defaults: dict, target: dict | None = None) -> None:
        if target is None:
            target = self._data
        for key, val in defaults.items():
            if isinstance(val, dict):
                target.setdefault(key, {})
                self._merge_defaults(val, target[key])
            else:
                target.setdefault(key, val)

    def _save(self) -> None:
        self.config_path.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")

    def get(self, key: str, default: Any = None) -> Any:
        """Obtiene valor por clave dot-notation, ej: 'providers.ollama-local.enabled'."""
        parts = key.split(".")
        node = self._data
        for part in parts:
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return default
        return node

    def set(self, key: str, value: Any) -> None:
        """Establece valor por clave dot-notation."""
        parts = key.split(".")
        node = self._data
        for part in parts[:-1]:
            if part not in node or not isinstance(node[part], dict):
                node[part] = {}
            node = node[part]
        node[parts[-1]] = value
        self._save()

    def delete(self, key: str) -> bool:
        """Borra clave dot-notation. Retorna True si existía."""
        parts = key.split(".")
        node = self._data
        for part in parts[:-1]:
            if not isinstance(node, dict) or part not in node:
                return False
            node = node[part]
        if parts[-1] in node:
            del node[parts[-1]]
            self._save()
            return True
        return False

    def reset(self) -> None:
        """Restaura configuración por defecto."""
        self._data = {}
        self._merge_defaults(DEFAULT_CONFIG)
        self._save()

    def all(self) -> dict[str, Any]:
        return dict(self._data)

    def provider_config(self, provider_name: str) -> dict[str, Any]:
        return self._data.get("providers", {}).get(provider_name, {})

    def is_provider_enabled(self, provider_name: str) -> bool:
        return self.provider_config(provider_name).get("enabled", False)

    def set_provider_enabled(self, provider_name: str, enabled: bool) -> None:
        self.set(f"providers.{provider_name}.enabled", enabled)

    @property
    def default_provider(self) -> str:
        return self._data.get("default_provider", "ollama-cloud")

    @default_provider.setter
    def default_provider(self, value: str) -> None:
        self._data["default_provider"] = value
        self._save()

    @property
    def default_model(self) -> str:
        return self._data.get("default_model", "deepseek-v3.1:671b")

    @default_model.setter
    def default_model(self, value: str) -> None:
        self._data["default_model"] = value
        self._save()

    @property
    def feature_streaming(self) -> bool:
        return self._data.get("features", {}).get("streaming", True)

    @property
    def feature_compression(self) -> bool:
        return self._data.get("features", {}).get("compression_on_downgrade", True)

    @property
    def feature_rl(self) -> bool:
        return self._data.get("features", {}).get("rl_learning", True)

    @property
    def feature_auto_evolve(self) -> bool:
        return self._data.get("features", {}).get("auto_evolve_on_start", True)

    def read_roots(self) -> list[dict[str, Any]]:
        value = self.get("sources.read_roots", [])
        return list(value) if isinstance(value, list) else []

    def set_read_roots(self, roots: list[dict[str, Any]]) -> None:
        self.set("sources.read_roots", list(roots))

    def add_read_root(self, root: dict[str, Any]) -> None:
        roots = self.read_roots()
        roots.append(dict(root))
        self.set_read_roots(roots)

    def remove_read_root(self, key: str) -> bool:
        clean = str(key or "").strip().lower()
        if not clean:
            return False
        roots = self.read_roots()
        next_roots = [root for root in roots if str(root.get("key") or "").strip().lower() != clean and str(root.get("path") or "").strip().lower() != clean]
        if len(next_roots) == len(roots):
            return False
        self.set_read_roots(next_roots)
        return True


# ── Quick test ──────────────────────────────────────────────────────

def _run_tests() -> int:
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        state_root = Path(td) / "state"
        old = os.environ.get("BAGO_STATE_ROOT")
        os.environ["BAGO_STATE_ROOT"] = str(state_root)
        cm = ConfigManager(base_path=td)
        assert cm.get("default_provider") == "ollama-cloud"
        cm.set("default_provider", "openrouter")
        assert cm.get("default_provider") == "openrouter"
        cm.set("providers.openrouter.enabled", True)
        assert cm.is_provider_enabled("openrouter")
        assert not cm.is_provider_enabled("anthropic")
        cm.set("features.streaming", False)
        assert cm.feature_streaming is False
        assert cm.get("ui.prompt_provider_on_start") is True
        assert cm.get("model_catalog.mode") == "all"
        assert cm.get("model_catalog.production_mode") == "available-only"
        cm.reset()
        assert cm.get("default_provider") == "ollama-cloud"
        assert cm.feature_streaming is True
        print("config_manager.py --test: ALL PASS")
        if old is None:
            os.environ.pop("BAGO_STATE_ROOT", None)
        else:
            os.environ["BAGO_STATE_ROOT"] = old
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
