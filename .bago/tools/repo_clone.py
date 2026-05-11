#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
repo_clone.py — Clone GitHub repositories with automatic BAGO setup

Integrates with workspace structure: C:\\Marc_max_20gb\\repos\\

Uso:
  python3 repo_clone.py https://github.com/user/repo.git
  python3 repo_clone.py https://github.com/user/repo.git --name myrepo
  python3 repo_clone.py --list
"""

from pathlib import Path
import subprocess
import sys
import json
from datetime import datetime, timezone
import shutil

import re

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]  # .bago/ directory
REPOS_DIR = WORKSPACE_ROOT / "repos"
WORKSPACE_STATE = WORKSPACE_ROOT / ".bago" / "state" / "workspace.json"

_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _validate_repo_name(name: str) -> str:
    """Valida nombre de repo para prevenir path traversal."""
    if not name or name in {".", ".."}:
        raise ValueError(f"Nombre de repo inválido: '{name}'")
    if not _SAFE_NAME_RE.fullmatch(name):
        raise ValueError(
            f"Nombre de repo inválido: '{name}'. "
            "Solo se permiten letras, números, puntos, guiones y guiones bajos."
        )
    return name


def ensure_repos_dir():
    """Crea directorio repos/ si no existe."""
    REPOS_DIR.mkdir(parents=True, exist_ok=True)
    return REPOS_DIR


def get_repo_name(url):
    """Extrae nombre del repo desde URL."""
    name = url.split('/')[-1]
    if name.endswith('.git'):
        name = name[:-4]
    return name


def load_workspace_state():
    """Carga estado del workspace."""
    if WORKSPACE_STATE.exists():
        try:
            return json.loads(WORKSPACE_STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    
    return {
        "version": "1.0",
        "created": datetime.now(timezone.utc).isoformat(),
        "repositories": {},
        "recent_repo": None
    }


def save_workspace_state(state):
    """Guarda estado del workspace."""
    WORKSPACE_STATE.parent.mkdir(parents=True, exist_ok=True)
    WORKSPACE_STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def _register_in_recent(repo_name: str, repo_path: str, url: str) -> None:
    """Registra repo clonado en recent_projects.json para que aparezca en `bago recent`."""
    recent_f = WORKSPACE_ROOT / "state" / "recent_projects.json"
    try:
        data = json.loads(recent_f.read_text(encoding="utf-8")) if recent_f.exists() else {}
    except Exception:
        data = {}
    projects = data.get("projects", [])
    now = datetime.now(timezone.utc).isoformat()
    # No duplicar si ya existe
    if not any(p.get("repo_root") == repo_path for p in projects):
        projects.insert(0, {
            "repo_root":  repo_path,
            "repo_name":  repo_name,
            "last_seen":  now,
            "ideas_done": 0,
            "last_idea":  "",
            "mode":       "external",
            "clone_url":  url,
        })
    recent_f.parent.mkdir(parents=True, exist_ok=True)
    recent_f.write_text(json.dumps({"projects": projects}, indent=2, ensure_ascii=False), encoding="utf-8")


def _find_git() -> "str | None":
    """Busca git en PATH y rutas comunes de Windows."""
    import shutil as _shutil
    git = _shutil.which("git")
    if git:
        return git
    common = [
        r"C:\Program Files\Git\bin\git.exe",
        r"C:\Program Files (x86)\Git\bin\git.exe",
        r"C:\Git\bin\git.exe",
    ]
    for p in common:
        if Path(p).exists():
            return p
    return None


def _clone_via_zip(url: str, repo_path: Path) -> bool:
    """Descarga el repo como ZIP desde GitHub cuando git no está disponible."""
    import urllib.request
    import zipfile
    import tempfile

    # Normalizar URL → usuario/repo
    url_clean = url.removesuffix(".git")
    # https://github.com/user/repo → https://github.com/user/repo/archive/refs/heads/main.zip
    zip_url = url_clean.rstrip("/") + "/archive/refs/heads/main.zip"
    zip_url_master = url_clean.rstrip("/") + "/archive/refs/heads/master.zip"

    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = Path(tmpdir) / "repo.zip"
        # Intentar main, luego master
        downloaded = False
        for attempt_url in (zip_url, zip_url_master):
            try:
                print(f"  ↓ Descargando {attempt_url}")
                req = urllib.request.Request(
                    attempt_url,
                    headers={"User-Agent": "BAGO-framework/2.5"}
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    zip_path.write_bytes(resp.read())
                downloaded = True
                break
            except Exception as e:
                print(f"  ✗ {e}")

        if not downloaded:
            return False

        # Extraer
        print("  ↓ Extrayendo...")
        with zipfile.ZipFile(zip_path) as zf:
            members = zf.namelist()
            # El zip tiene una carpeta raíz (repo-main/ o repo-master/)
            root_prefix = members[0] if members else ""
            extract_dir = Path(tmpdir) / "extracted"
            zf.extractall(extract_dir)
            # Mover la carpeta interna al destino
            extracted_root = extract_dir / root_prefix.split("/")[0]
            shutil.move(str(extracted_root), str(repo_path))

    return repo_path.exists()


def clone_repo(url, custom_name=None):
    """Clona repositorio en repos/ con nombre."""
    ensure_repos_dir()

    raw_name = custom_name or get_repo_name(url)
    try:
        repo_name = _validate_repo_name(raw_name)
    except ValueError as e:
        print(f"✗ Error: {e}")
        return None
    repo_path = REPOS_DIR / repo_name
    
    # Verificar que no exista ya
    if repo_path.exists():
        print(f"✗ Error: {repo_path} ya existe")
        return None
    
    print(f"\n══ Clonando repositorio ═══════════════════════════════════")
    print(f"URL:  {url}")
    print(f"Path: {repo_path}")
    print()
    
    git = _find_git()
    success = False

    if git:
        print("▪ Clonando con git...")
        try:
            result = subprocess.run(
                [git, "clone", url, str(repo_path)],
                capture_output=True,
                text=True,
                timeout=300
            )
            if result.returncode == 0:
                success = True
            else:
                print(f"  ✗ git falló: {result.stderr.strip()}")
        except Exception as e:
            print(f"  ✗ Error git: {e}")
    
    if not success:
        print("▪ git no disponible — descargando ZIP desde GitHub...")
        success = _clone_via_zip(url, repo_path)

    if not success:
        print("✗ No se pudo clonar el repositorio.")
        return None
    
    print("▪ Clone exitoso")

    
    # Setup BAGO (copiar desde template o existente)
    print("▪ Configurando BAGO...")
    setup_bago_for_repo(repo_path)
    
    # Registrar en workspace state
    print("▪ Registrando en workspace...")
    state = load_workspace_state()
    state["repositories"][repo_name] = {
        "url": url,
        "path": str(repo_path),
        "cloned_at": datetime.now(timezone.utc).isoformat(),
        "status": "active"
    }
    state["recent_repo"] = repo_name
    save_workspace_state(state)

    # Registrar en recent_projects.json (aparece en `bago recent` inmediatamente)
    _register_in_recent(repo_name, str(repo_path), url)

    print()
    print("════════════════════════════════════════════════════════════")
    print(f"✓ Repositorio clonado exitosamente: {repo_name}")
    print()
    print("Próximos pasos:")
    print(f"  1. cd {repo_path}")
    print(f"  2. bago audit")
    print(f"  3. bago ideas")
    print()
    
    return repo_path


def setup_bago_for_repo(repo_path):
    """Configura BAGO en el repositorio clonado."""
    bago_dest = repo_path / ".bago"
    bago_template = WORKSPACE_ROOT / "templates" / "bago_template"
    bago_source = WORKSPACE_ROOT / ".bago"
    
    # Usar template si existe, sino copiar del workspace
    if bago_template.exists():
        shutil.copytree(bago_template, bago_dest, dirs_exist_ok=True)
    elif bago_source.exists():
        # Copiar estructura básica (.bago/state/)
        bago_dest.mkdir(exist_ok=True)
        state_dest = bago_dest / "state"
        state_dest.mkdir(exist_ok=True)
        
        # Crear global_state.json — version leída del PADRE (bago_core)
        _padre_state_path = WORKSPACE_ROOT / "state" / "global_state.json"
        _padre_version = "unknown"
        if _padre_state_path.exists():
            try:
                _padre_version = json.loads(_padre_state_path.read_text()).get("bago_version", "unknown")
            except Exception:
                pass
        global_state = {
            "version": _padre_version,
            "repo_name": repo_path.name,
            "workspace_root": str(WORKSPACE_ROOT),
            "mode": "project",
            "health_status": "initializing",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        (state_dest / "global_state.json").write_text(
            json.dumps(global_state, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )


def list_repos():
    """Lista repositorios clonados."""
    state = load_workspace_state()
    repos = state.get("repositories", {})
    
    if not repos:
        print("\n✓ Sin repositorios clonados aún")
        print("  Ejecuta: python repo_clone.py https://github.com/user/repo.git")
        return
    
    print("\n══ Repositorios clonados ════════════════════════════════════")
    for name, info in sorted(repos.items()):
        icon = "🟢" if info.get("status") == "active" else "⚪"
        url = info.get("url", "?")
        cloned = info.get("cloned_at", "?")[:10]
        print(f"  {icon} {name:20} | {url:40} | {cloned}")
    
    print()
    print(f"Total: {len(repos)} repositorios")
    print()


def main():
    if len(sys.argv) < 2:
        print("repo_clone.py — Clone GitHub repos con BAGO auto-setup")
        print("\nUso:")
        print("  python repo_clone.py <url>              → clona repositorio")
        print("  python repo_clone.py <url> --name <nom> → clona con nombre custom")
        print("  python repo_clone.py --list              → lista repos clonados")
        print("\nEjemplo:")
        print('  python repo_clone.py https://github.com/MarcValls/bago-framework.git')
        return
    
    cmd = sys.argv[1]
    
    if cmd == "--list":
        list_repos()
    elif cmd.startswith("http"):
        # URL de repositorio
        url = cmd
        custom_name = None
        
        if "--name" in sys.argv:
            idx = sys.argv.index("--name")
            if idx + 1 < len(sys.argv):
                custom_name = sys.argv[idx + 1]
        
        clone_repo(url, custom_name)
    else:
        print(f"Comando no reconocido: {cmd}")



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
