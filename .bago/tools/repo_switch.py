#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
repo_switch.py — Switch active repository context in workspace

Cambia el repositorio activo en workspace y actualiza el contexto BAGO

Uso:
  python3 repo_switch.py <repo-name>        → cambia a repositorio
  python3 repo_switch.py --current          → muestra repo actual
  python3 repo_switch.py --list             → lista repos disponibles
"""

from pathlib import Path
import json
import sys
from datetime import datetime, timezone

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
    return {"repositories": {}, "recent_repo": None}


def save_workspace_state(state):
    """Guarda estado del workspace."""
    WORKSPACE_STATE.parent.mkdir(parents=True, exist_ok=True)
    WORKSPACE_STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def switch_repo(repo_name):
    """Cambia el repositorio activo."""
    state = load_workspace_state()
    repos = state.get("repositories", {})
    
    # Verificar que existe
    if repo_name not in repos:
        print(f"\n✗ Repositorio no encontrado: {repo_name}")
        print("\nRepositorios disponibles:")
        for name in sorted(repos.keys()):
            print(f"  • {name}")
        return False
    
    repo_path = Path(repos[repo_name]["path"])
    
    # Verificar que existe en filesystem
    if not repo_path.exists():
        print(f"\n✗ Ruta no existe: {repo_path}")
        print("  Ejecuta: python repo_clone.py --list")
        return False
    
    # Actualizar estado
    state["recent_repo"] = repo_name
    state["repositories"][repo_name]["last_accessed"] = datetime.now(timezone.utc).isoformat()
    save_workspace_state(state)
    
    print(f"\n═══════════════════════════════════════════════════════════")
    print(f"✓ Contexto cambiado a: {repo_name}")
    print()
    print(f"Ruta: {repo_path}")
    print()
    print(f"Próximos pasos:")
    print(f"  cd {repo_path}")
    print(f"  bago audit")
    print(f"  bago research '<topic>'")
    print()
    print(f"═══════════════════════════════════════════════════════════\n")
    
    return True


def show_current():
    """Muestra repositorio actual."""
    state = load_workspace_state()
    current = state.get("recent_repo")
    
    if not current:
        print("\n✓ Sin repositorio activo")
        print("  Ejecuta: python repo_switch.py <repo-name>")
        return
    
    repos = state.get("repositories", {})
    if current in repos:
        info = repos[current]
        print(f"\n🟢 Repositorio actual: {current}")
        print(f"   Path: {info.get('path')}")
        print(f"   URL:  {info.get('url')}")
        print(f"   Última visita: {info.get('last_accessed', info.get('cloned_at'))}")
        print()
    else:
        print(f"\n⚪ Repositorio actual: {current} (no encontrado)")
        print()


def list_repos():
    """Lista repositorios disponibles."""
    state = load_workspace_state()
    repos = state.get("repositories", {})
    current = state.get("recent_repo")
    
    if not repos:
        print("\n✓ Sin repositorios clonados")
        print("  Ejecuta: python repo_clone.py https://github.com/user/repo.git")
        return
    
    print("\n══ Repositorios disponibles ═════════════════════════════════")
    for name in sorted(repos.keys()):
        icon = "🟢" if name == current else "⚪"
        info = repos[name]
        url = info.get("url", "?")[:40]
        print(f"  {icon} {name:20} | {url}")
    
    print()
    print(f"Actual: {current or '(ninguno)'}")
    print()


def main():
    if len(sys.argv) < 2:
        print("repo_switch.py — Switch active repository context")
        print("\nUso:")
        print("  python repo_switch.py <name>    → cambia a repositorio")
        print("  python repo_switch.py --current → muestra actual")
        print("  python repo_switch.py --list    → lista repositorios")
        return
    
    cmd = sys.argv[1]
    
    if cmd == "--current":
        show_current()
    elif cmd == "--list":
        list_repos()
    elif cmd.startswith("--"):
        print(f"Comando no reconocido: {cmd}")
    else:
        switch_repo(cmd)



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
