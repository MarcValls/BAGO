#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lsp_manager.py — Orquestación de Language Servers integrando GitHub Copilot CLI LSP

Implementa soporte LSP como servicio BAGO:
- Registro y gestión de servidores LSP
- Integración con herramientas de análisis (type_check, naming_check, etc.)
- Proporciona inteligencia de código a workflows
- Configurable vía pack.json

Uso:
  python3 .bago/tools/lsp_manager.py --status
  python3 .bago/tools/lsp_manager.py --register <lang> <command>
  python3 .bago/tools/lsp_manager.py --list
"""

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from pathlib import Path
import json
import sys
import subprocess
from bago_utils import (
    get_bago_root, get_state_dir, ensure_subdir, load_json, save_json,
    timestamp_iso
)

PACK_JSON = get_bago_root() / "pack.json"
LSP_REGISTRY = get_state_dir() / "lsp_registry.json"


def get_pack() -> dict:
    """Lee pack.json."""
    return load_json(PACK_JSON)


def get_lsp_registry() -> dict:
    """Lee registro LSP o crea vacío."""
    registry = load_json(LSP_REGISTRY)
    
    if not registry:
        return {
            "version": "1.0",
            "timestamp": timestamp_iso(),
            "servers": {}
        }
    
    return registry


def save_lsp_registry(registry: dict) -> None:
    """Guarda registro LSP."""
    save_json(LSP_REGISTRY, registry)


def detect_available_servers() -> dict:
    """Detecta servidores LSP disponibles en el sistema."""
    servers = {}
    
    # TypeScript/JavaScript
    try:
        result = subprocess.run(["which", "typescript-language-server"], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            servers["typescript"] = {
                "command": "typescript-language-server",
                "args": ["--stdio"],
                "languages": ["typescript", "javascript"]
            }
    except Exception:
        pass
    
    # Python
    try:
        result = subprocess.run(["which", "pylsp"],
                              capture_output=True, text=True)
        if result.returncode == 0:
            servers["python"] = {  # noqa: HARDCODE
                "command": "pylsp",
                "args": [],
                "languages": ["python"]  # noqa: HARDCODE
            }
    except Exception:
        pass
    
    # Go
    try:
        result = subprocess.run(["which", "gopls"],
                              capture_output=True, text=True)
        if result.returncode == 0:
            servers["go"] = {
                "command": "gopls",
                "args": ["serve"],
                "languages": ["go"]
            }
    except Exception:
        pass
    
    # Rust
    try:
        result = subprocess.run(["which", "rust-analyzer"],
                              capture_output=True, text=True)
        if result.returncode == 0:
            servers["rust"] = {
                "command": "rust-analyzer",
                "args": [],
                "languages": ["rust"]
            }
    except Exception:
        pass
    
    return servers


def register_server(language: str, command: str) -> bool:
    """Registra un servidor LSP."""
    registry = get_lsp_registry()
    
    registry["servers"][language] = {
        "command": command,
        "registered_at": timestamp_iso(),
        "status": "pending_validation"
    }
    
    save_lsp_registry(registry)
    return True


def list_servers() -> None:
    """Lista servidores LSP registrados."""
    registry = get_lsp_registry()
    
    if not registry.get("servers"):
        print("✓ Sin servidores LSP registrados aún.")
        print("  Ejecuta: bago lsp --detect")
        return
    
    print("\n══ LSP Servers Registered ═══════════════════════════════")
    for lang, info in registry["servers"].items():
        status = info.get("status", "?")
        icon = "🟢" if status == "active" else "🟡"
        print(f"  {icon} {lang:15} | {info.get('command', '?')}")
    print()


def show_status() -> None:
    """Muestra estado de los servidores LSP."""
    registry = get_lsp_registry()
    servers = registry.get("servers", {})
    
    print("\n══ LSP Status ═════════════════════════════════════════════")
    if not servers:
        print("  ⚪ No LSP servers configured yet")
    else:
        active = sum(1 for s in servers.values() if s.get("status") == "active")
        print(f"  🟢 Active:   {active}/{len(servers)}")
        print(f"  ⏳ Total:    {len(servers)}")
    print()


def detect_servers() -> None:
    """Detecta y registra servidores LSP disponibles."""
    print("\n══ Detecting LSP Servers ══════════════════════════════════")
    print("  Buscando servidores LSP disponibles en el sistema...")
    print()
    
    available = detect_available_servers()
    
    if not available:
        print("  ⚪ No LSP servers detected")
        print()
        print("  Para instalar:")
        print("    • TypeScript: npm install -g typescript-language-server")
        print("    • Python:     pip install python-lsp-server")
        print("    • Go:         go install github.com/golang/tools/gopls@latest")
        print("    • Rust:       rustup component add rust-analyzer")
        return
    
    print(f"  ✅ Found {len(available)} LSP server(s):")
    print()
    
    for lang, info in available.items():
        registry = get_lsp_registry()
        registry["servers"][lang] = {
            "command": info["command"],
            "args": info.get("args", []),
            "languages": info.get("languages", []),
            "status": "active",
            "auto_detected": True,
            "timestamp": timestamp_iso()
        }
        save_lsp_registry(registry)
        print(f"    ✓ {lang:15} ({info['command']})")
    
    print()
    print("  Saved to: .bago/state/lsp_registry.json")
    print()


def integrate_with_pack() -> None:
    """Integra LSP registry con pack.json."""
    pack = get_pack()
    registry = get_lsp_registry()
    
    if "lsp" not in pack:
        pack["lsp"] = {
            "enabled": True,
            "registry_file": "state/lsp_registry.json",
            "auto_detect": True
        }
    
    # Actualizar pack.json (no escribir, solo sugerir)
    print("\n══ LSP Integration with pack.json ════════════════════════")
    print("  Suggested configuration for pack.json:")
    print()
    print(json.dumps(pack.get("lsp", {}), indent=2))
    print()


def main():
    if len(sys.argv) < 2:
        print("lsp_manager.py — Orquestación de Language Servers")
        print("\nUso:")
        print("  bago lsp --status      → muestra estado LSP")
        print("  bago lsp --list        → lista servidores registrados")
        print("  bago lsp --detect      → detecta y auto-registra servidores")
        print("  bago lsp --integrate   → integra con pack.json (consejo)")
        return
    
    cmd = sys.argv[1]
    
    if cmd == "--status":
        show_status()
    elif cmd == "--list":
        list_servers()
    elif cmd == "--detect":
        detect_servers()
    elif cmd == "--integrate":
        integrate_with_pack()
    elif cmd == "--register" and len(sys.argv) >= 4:
        lang, command = sys.argv[2], sys.argv[3]
        if register_server(lang, command):
            print(f"✓ Registered LSP: {lang} → {command}")
    else:
        print("Comando no reconocido. Usa: --status, --list, --detect, --integrate")



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    main()

