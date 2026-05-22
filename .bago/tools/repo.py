#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unified repository tool for BAGO.

Usage:
  python repo.py                 -> list repositories
  python repo.py list [--detail|--health]
  python repo.py clone <url> [--name NAME]
  python repo.py switch <name>
  python repo.py switch --current|--list
  python repo.py guard check|sync
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
import hashlib

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

TOOLS_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
REPOS_DIR = WORKSPACE_ROOT / "repos"
WORKSPACE_STATE = WORKSPACE_ROOT / ".bago" / "state" / "workspace.json"
ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT / ".bago" / "state" / "repo_context.json"
_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_workspace_state():
    return _load_json(
        WORKSPACE_STATE,
        {
            "version": "1.0",
            "created": datetime.now(timezone.utc).isoformat(),
            "repositories": {},
            "recent_repo": None,
        },
    )


def save_workspace_state(state) -> None:
    _save_json(WORKSPACE_STATE, state)


def ensure_repos_dir():
    REPOS_DIR.mkdir(parents=True, exist_ok=True)
    return REPOS_DIR


def _validate_repo_name(name: str) -> str:
    if not name or name in {".", ".."}:
        raise ValueError(f"Nombre de repo inválido: '{name}'")
    if not _SAFE_NAME_RE.fullmatch(name):
        raise ValueError(
            f"Nombre de repo inválido: '{name}'. Solo se permiten letras, números, puntos, guiones y guiones bajos."
        )
    return name


def get_repo_name(url):
    name = url.split("/")[-1]
    return name[:-4] if name.endswith(".git") else name


def _register_in_recent(repo_name: str, repo_path: str, url: str) -> None:
    recent_f = WORKSPACE_ROOT / "state" / "recent_projects.json"
    data = _load_json(recent_f, {})
    projects = data.get("projects", [])
    now = datetime.now(timezone.utc).isoformat()
    if not any(p.get("repo_root") == repo_path for p in projects):
        projects.insert(0, {
            "repo_root": repo_path,
            "repo_name": repo_name,
            "last_seen": now,
            "ideas_done": 0,
            "last_idea": "",
            "mode": "external",
            "clone_url": url,
        })
    _save_json(recent_f, {"projects": projects})


def _find_git() -> str | None:
    git = shutil.which("git")
    if git:
        return git
    for candidate in (
        r"C:\Program Files\Git\bin\git.exe",
        r"C:\Program Files (x86)\Git\bin\git.exe",
        r"C:\Git\bin\git.exe",
    ):
        if Path(candidate).exists():
            return candidate
    return None


def _clone_via_zip(url: str, repo_path: Path) -> bool:
    import tempfile
    import urllib.request
    import zipfile

    url_clean = url.removesuffix(".git").rstrip("/")
    for attempt_url in (
        url_clean + "/archive/refs/heads/main.zip",
        url_clean + "/archive/refs/heads/master.zip",
    ):
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "repo.zip"
            try:
                print(f"  ↓ Descargando {attempt_url}")
                req = urllib.request.Request(attempt_url, headers={"User-Agent": "BAGO-framework/2.5"})
                with urllib.request.urlopen(req, timeout=60) as response:
                    zip_path.write_bytes(response.read())
                extract_dir = Path(tmpdir) / "extracted"
                with zipfile.ZipFile(zip_path) as zf:
                    zf.extractall(extract_dir)
                roots = [p for p in extract_dir.iterdir() if p.is_dir()]
                if not roots:
                    continue
                shutil.move(str(roots[0]), str(repo_path))
                return repo_path.exists()
            except Exception as exc:
                print(f"  ✗ {exc}")
    return False


def setup_bago_for_repo(repo_path: Path) -> None:
    bago_dest = repo_path / ".bago"
    bago_template = WORKSPACE_ROOT / "templates" / "bago_template"
    bago_source = WORKSPACE_ROOT / ".bago"
    if bago_template.exists():
        shutil.copytree(bago_template, bago_dest, dirs_exist_ok=True)
        return
    if not bago_source.exists():
        return
    bago_dest.mkdir(exist_ok=True)
    state_dest = bago_dest / "state"
    state_dest.mkdir(exist_ok=True)
    parent_state = WORKSPACE_ROOT / "state" / "global_state.json"
    parent_version = _load_json(parent_state, {}).get("bago_version", "unknown") if parent_state.exists() else "unknown"
    _save_json(
        state_dest / "global_state.json",
        {
            "version": parent_version,
            "repo_name": repo_path.name,
            "workspace_root": str(WORKSPACE_ROOT),
            "mode": "project",
            "health_status": "initializing",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def clone_repo(url, custom_name=None):
    ensure_repos_dir()
    try:
        repo_name = _validate_repo_name(custom_name or get_repo_name(url))
    except ValueError as exc:
        print(f"✗ Error: {exc}")
        return None
    repo_path = REPOS_DIR / repo_name
    if repo_path.exists():
        print(f"✗ Error: {repo_path} ya existe")
        return None
    print("\n══ Clonando repositorio ═══════════════════════════════════")
    print(f"URL:  {url}")
    print(f"Path: {repo_path}\n")
    git = _find_git()
    success = False
    if git:
        print("▪ Clonando con git...")
        try:
            result = subprocess.run([git, "clone", url, str(repo_path)], capture_output=True, text=True, timeout=300)
            success = result.returncode == 0
            if not success:
                print(f"  ✗ git falló: {result.stderr.strip()}")
        except Exception as exc:
            print(f"  ✗ Error git: {exc}")
    if not success:
        print("▪ git no disponible — descargando ZIP desde GitHub...")
        success = _clone_via_zip(url, repo_path)
    if not success:
        print("✗ No se pudo clonar el repositorio.")
        return None
    print("▪ Clone exitoso")
    print("▪ Configurando BAGO...")
    setup_bago_for_repo(repo_path)
    print("▪ Registrando en workspace...")
    state = load_workspace_state()
    for info in state.get("repositories", {}).values():
        if info.get("status") == "active":
            info["status"] = "inactive"
    state.setdefault("repositories", {})[repo_name] = {
        "url": url,
        "path": str(repo_path),
        "cloned_at": datetime.now(timezone.utc).isoformat(),
        "status": "active",
    }
    state["recent_repo"] = repo_name
    save_workspace_state(state)
    _register_in_recent(repo_name, str(repo_path), url)
    print("\n════════════════════════════════════════════════════════════")
    print(f"✓ Repositorio clonado exitosamente: {repo_name}\n")
    print("Próximos pasos:")
    print(f"  1. cd {repo_path}")
    print("  2. bago audit")
    print("  3. bago ideas\n")
    return repo_path


def get_repo_health(repo_path):
    bago_state = repo_path / ".bago" / "state" / "global_state.json"
    if not bago_state.exists():
        return "⚪ unknown"
    state = _load_json(bago_state, {})
    health = str(state.get("health_status", "?"))
    if health == "initializing":
        return "🟡 initializing"
    if health.startswith("80") or health.startswith("90"):
        return f"🟢 {health}"
    return f"⚪ {health}" if health else "⚪ error"


def list_repos(detail=False, health=False):
    state = load_workspace_state()
    repos = state.get("repositories", {})
    if not repos:
        print("\n✓ Sin repositorios clonados")
        print("  Ejecuta: python repo.py clone https://github.com/user/repo.git")
        return
    print("\n══ Workspace Repositories ════════════════════════════════════")
    if health:
        print(f"{'Nombre':<20} {'Status':<15} {'Salud':<20} {'URL':<40}")
        print("─" * 95)
    else:
        print(f"{'Nombre':<20} {'Status':<15} {'Clonado':<15} {'URL':<40}")
        print("─" * 90)
    for name, info in sorted(repos.items()):
        status = f"{'🟢' if info.get('status') == 'active' else '⚪'} {info.get('status', '?')}"
        repo_path = Path(info.get("path", ""))
        url = str(info.get("url", "?"))[:38]
        if health:
            print(f"{name:<20} {status:<15} {get_repo_health(repo_path) if repo_path.exists() else '⚪ missing':<20} {url:<40}")
        else:
            print(f"{name:<20} {status:<15} {str(info.get('cloned_at', '?'))[:10]:<15} {url:<40}")
    print()
    if detail:
        print("\nDetalle de cada repositorio:\n")
        for name, info in sorted(repos.items()):
            print(f"📦 {name}")
            print(f"   URL:   {info.get('url')}")
            print(f"   Path:  {info.get('path')}")
            print(f"   Clone: {info.get('cloned_at')}")
            print(f"   Status: {info.get('status')}\n")
    print(f"Total: {len(repos)} repositorios\n")


def list_available_repos():
    state = load_workspace_state()
    repos = state.get("repositories", {})
    current = state.get("recent_repo")
    if not repos:
        print("\n✓ Sin repositorios clonados")
        print("  Ejecuta: python repo.py clone https://github.com/user/repo.git")
        return
    print("\n══ Repositorios disponibles ═════════════════════════════════")
    for name in sorted(repos):
        info = repos[name]
        print(f"  {'🟢' if name == current else '⚪'} {name:20} | {str(info.get('url', '?'))[:40]}")
    print(f"\nActual: {current or '(ninguno)'}\n")


def switch_repo(repo_name):
    state = load_workspace_state()
    repos = state.get("repositories", {})
    if repo_name not in repos:
        print(f"\n✗ Repositorio no encontrado: {repo_name}\n\nRepositorios disponibles:")
        for name in sorted(repos):
            print(f"  • {name}")
        return False
    repo_path = Path(repos[repo_name].get("path", ""))
    if not repo_path.exists():
        print(f"\n✗ Ruta no existe: {repo_path}")
        print("  Ejecuta: python repo.py list")
        return False
    for name, info in repos.items():
        info["status"] = "active" if name == repo_name else "inactive"
    state["recent_repo"] = repo_name
    state["repositories"][repo_name]["last_accessed"] = datetime.now(timezone.utc).isoformat()
    save_workspace_state(state)
    print("\n═══════════════════════════════════════════════════════════")
    print(f"✓ Contexto cambiado a: {repo_name}\n")
    print(f"Ruta: {repo_path}\n")
    print("Próximos pasos:")
    print(f"  cd {repo_path}")
    print("  bago audit")
    print("  bago research '<topic>'\n")
    print("═══════════════════════════════════════════════════════════\n")
    return True


def show_current():
    state = load_workspace_state()
    current = state.get("recent_repo")
    if not current:
        print("\n✓ Sin repositorio activo")
        print("  Ejecuta: python repo.py switch <repo-name>")
        return
    repos = state.get("repositories", {})
    if current not in repos:
        print(f"\n⚪ Repositorio actual: {current} (no encontrado)\n")
        return
    info = repos[current]
    print(f"\n🟢 Repositorio actual: {current}")
    print(f"   Path: {info.get('path')}")
    print(f"   URL:  {info.get('url')}")
    print(f"   Última visita: {info.get('last_accessed', info.get('cloned_at'))}\n")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def detect_repo_root() -> Path:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        return Path(result.stdout.strip()).resolve()
    except Exception:
        return ROOT.resolve()


def repo_fingerprint(repo_root: Path) -> str:
    marker = [str(repo_root), str(ROOT.resolve())]
    try:
        marker.extend(sorted(p.name for p in repo_root.iterdir() if p.name != ".bago")[:200])
    except Exception:
        pass
    return hashlib.sha256("\n".join(marker).encode("utf-8")).hexdigest()


def detect_working_mode(repo_root: Path) -> str:
    return "self" if repo_root.resolve() == ROOT.resolve() else "external"


def current_context() -> dict:
    repo_root = detect_repo_root()
    return {
        "repo_root": str(repo_root),
        "bago_host_root": str(ROOT.resolve()),
        "repo_fingerprint": repo_fingerprint(repo_root),
        "working_mode": detect_working_mode(repo_root),
        "recorded_at": now_iso(),
    }


def load_previous() -> dict | None:
    return None if not STATE_PATH.exists() else _load_json(STATE_PATH, None)


def save_context(ctx: dict) -> None:
    existing = _load_json(STATE_PATH, {}) if STATE_PATH.exists() else {}
    for key in {"role", "note"}:
        if key in existing:
            ctx[key] = existing[key]
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(ctx, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def compare_context(previous: dict | None, current: dict) -> str:
    if previous is None:
        return "new"
    if previous.get("repo_root") == current.get("repo_root") and previous.get("repo_fingerprint") == current.get("repo_fingerprint"):
        return "match"
    return "mismatch"


def guard_main(argv: list[str]) -> int:
    if not argv or argv[0] not in {"check", "sync"}:
        print("Uso: python repo.py guard check|sync")
        return 1
    prev = load_previous()
    cur = current_context()
    status = compare_context(prev, cur)
    if argv[0] == "sync":
        save_context(cur)
        print(json.dumps({"status": "synced", "context": cur}, indent=2, ensure_ascii=False))
        return 0
    print(json.dumps({"status": status, "previous": prev, "current": cur}, indent=2, ensure_ascii=False))
    return 0 if status == "match" else 3


def _usage() -> None:
    print(__doc__)
    print("Subcomandos disponibles: list, clone, switch, guard")


def _self_test() -> None:
    assert _validate_repo_name("demo-repo") == "demo-repo"
    assert compare_context(None, {"repo_root": "x"}) == "new"
    print("  2/2 tests pasaron")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--test" in args:
        _self_test()
        return 0
    if not args:
        list_repos()
        return 0
    if args[0] in {"-h", "--help", "help"}:
        _usage()
        return 0
    sub = args[0].lower()
    rest = args[1:]
    if sub in {"list", "ls"}:
        list_repos(detail=("--detail" in rest or "-v" in rest), health=("--health" in rest or "-h" in rest))
        return 0
    if sub == "clone":
        if not rest or rest[0] in {"-h", "--help"}:
            print("Uso: python repo.py clone <url> [--name NAME] | python repo.py clone --list")
            return 0
        if "--list" in rest:
            list_repos()
            return 0
        url = rest[0]
        custom_name = rest[rest.index("--name") + 1] if "--name" in rest and rest.index("--name") + 1 < len(rest) else None
        return 0 if clone_repo(url, custom_name) else 1
    if sub in {"switch", "sw"}:
        if "--current" in rest:
            show_current()
            return 0
        if "--list" in rest:
            list_available_repos()
            return 0
        target = next((item for item in rest if not item.startswith("-")), None)
        if not target:
            print("Uso: python repo.py switch <name> | --current | --list")
            return 1
        return 0 if switch_repo(target) else 1
    if sub == "guard":
        return guard_main(rest)
    if sub == "current":
        show_current()
        return 0
    _usage()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
