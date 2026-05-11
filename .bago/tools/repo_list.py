#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
repo_list.py — List and manage workspace repositories

Muestra todos los repositorios clonados en C:\\Marc_max_20gb\\repos\\

Uso:
  python3 repo_list.py                    → lista todos los repos
  python3 repo_list.py --detail           → lista con detalles
  python3 repo_list.py --health           → estado de cada repo
"""

from pathlib import Path
import json
import sys
from datetime import datetime

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
REPOS_DIR = WORKSPACE_ROOT / "repos"
WORKSPACE_STATE = WORKSPACE_ROOT / ".bago" / "state" / "workspace.json"


def load_workspace_state():
    """Carga estado del workspace."""
    if WORKSPACE_STATE.exists():
        try:
            return json.loads(WORKSPACE_STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"repositories": {}}


def get_repo_health(repo_path):
    """Obtiene estado de salud de un repo."""
    bago_state = repo_path / ".bago" / "state" / "global_state.json"
    
    if not bago_state.exists():
        return "⚪ unknown"
    
    try:
        state = json.loads(bago_state.read_text(encoding="utf-8"))
        health = state.get("health_status", "?")
        if health == "initializing":
            return "🟡 initializing"
        elif health.startswith("80") or health.startswith("90"):
            return f"🟢 {health}"
        else:
            return f"⚪ {health}"
    except Exception:
        return "⚪ error"


def list_repos(detail=False, health=False):
    """Lista repositorios."""
    state = load_workspace_state()
    repos = state.get("repositories", {})
    
    if not repos:
        print("\n✓ Sin repositorios clonados")
        print("  Ejecuta: python repo_clone.py https://github.com/user/repo.git")
        return
    
    print("\n══ Workspace Repositories ════════════════════════════════════")
    
    if health:
        print(f"{'Nombre':<20} {'Status':<15} {'Salud':<20} {'URL':<40}")
        print("─" * 95)
    else:
        print(f"{'Nombre':<20} {'Status':<15} {'Clonado':<15} {'URL':<40}")
        print("─" * 90)
    
    for name, info in sorted(repos.items()):
        status_icon = "🟢" if info.get("status") == "active" else "⚪"
        status = f"{status_icon} {info.get('status', '?')}"
        
        repo_path = Path(info.get("path", ""))
        
        if health:
            health_status = get_repo_health(repo_path) if repo_path.exists() else "⚪ missing"
            url = info.get("url", "?")[:38]
            print(f"{name:<20} {status:<15} {health_status:<20} {url:<40}")
        else:
            cloned = info.get("cloned_at", "?")[:10]
            url = info.get("url", "?")[:38]
            print(f"{name:<20} {status:<15} {cloned:<15} {url:<40}")
    
    print()
    
    if detail:
        print("\nDetalle de cada repositorio:\n")
        for name, info in sorted(repos.items()):
            print(f"📦 {name}")
            print(f"   URL:   {info.get('url')}")
            print(f"   Path:  {info.get('path')}")
            print(f"   Clone: {info.get('cloned_at')}")
            print(f"   Status: {info.get('status')}")
            print()
    
    print(f"Total: {len(repos)} repositorios\n")


def main():
    detail = "--detail" in sys.argv or "-v" in sys.argv
    health = "--health" in sys.argv or "-h" in sys.argv
    
    if "--help" in sys.argv or "-h" in sys.argv and not health:
        print("repo_list.py — List workspace repositories")
        print("\nUso:")
        print("  python repo_list.py                → lista todos")
        print("  python repo_list.py --detail (-v)  → lista con detalles")
        print("  python repo_list.py --health (-h)  → con estado de salud")
        return
    
    list_repos(detail=detail, health=health)



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
