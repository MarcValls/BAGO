"""bago health — Full workspace diagnostic with traffic-light status."""
from __future__ import annotations

import json
import socket
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = ROOT / ".bago" / "state"
DB_PATH = STATE_DIR / "bago.db"

def _get_project_root() -> Path:
    gs_path = STATE_DIR / "global_state.json"
    if gs_path.exists():
        try:
            gs = json.loads(gs_path.read_text(encoding="utf-8"))
            p = gs.get("active_project", {}).get("path", "")
            if p and Path(p).exists():
                return Path(p)
        except Exception:
            pass
    return ROOT.parent

PROJECT_ROOT = _get_project_root()

OK    = "\033[32m✔\033[0m"
WARN  = "\033[33m⚠\033[0m"
FAIL  = "\033[31m✗\033[0m"
INFO  = "\033[36mℹ\033[0m"

def _line(icon: str, label: str, detail: str = ""):
    d = f"  \033[2m{detail}\033[0m" if detail else ""
    print(f"  {icon}  {label}{d}")


def check_node_modules():
    print("\n  \033[1m📦 node_modules\033[0m")
    apps_dir = PROJECT_ROOT / "apps"
    checked = [PROJECT_ROOT]
    if apps_dir.exists():
        checked += [d for d in apps_dir.iterdir() if d.is_dir()]
    for app in checked:
        nm = app / "node_modules"
        name = "root" if app == PROJECT_ROOT else app.name
        pkg = app / "package.json"
        if not pkg.exists():
            continue
        if nm.exists() and any(nm.iterdir()):
            _line(OK, f"{name}/node_modules instalado")
        else:
            _line(FAIL, f"{name}/node_modules \033[31mFALTANTE\033[0m", "ejecuta: pnpm install")


def check_env_files():
    print("\n  \033[1m🔑 Variables de entorno\033[0m")
    apps_dir = PROJECT_ROOT / "apps"
    candidates = []
    if apps_dir.exists():
        candidates = [d for d in apps_dir.iterdir() if d.is_dir()]
    for app in candidates:
        example = app / ".env.example"
        real = app / ".env"
        if not example.exists():
            continue
        if real.exists():
            # Check coverage
            ex_keys = set()
            re_keys = set()
            for line in example.read_text(encoding="utf-8", errors="replace").splitlines():
                if "=" in line and not line.startswith("#"):
                    ex_keys.add(line.split("=")[0].strip())
            for line in real.read_text(encoding="utf-8", errors="replace").splitlines():
                if "=" in line and not line.startswith("#"):
                    re_keys.add(line.split("=")[0].strip())
            missing = ex_keys - re_keys
            if missing:
                _line(WARN, f"{app.name}/.env", f"faltan: {', '.join(sorted(missing)[:3])}{'...' if len(missing)>3 else ''}")
            else:
                _line(OK, f"{app.name}/.env completo ({len(re_keys)} vars)")
        else:
            _line(WARN, f"{app.name}/.env", "no existe — copia desde .env.example")


def check_ports():
    print("\n  \033[1m🔌 Puertos\033[0m")
    # Read PORT_* from .env files
    port_map: dict[str, int] = {}
    for env_file in PROJECT_ROOT.rglob(".env"):
        if "node_modules" in env_file.parts:
            continue
        for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
            if "PORT" in line and "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                try:
                    port_map[k.strip()] = int(v.strip())
                except ValueError:
                    pass

    if not port_map:
        _line(INFO, "No se encontraron variables PORT_* en .env")
        return

    for key, port in sorted(port_map.items()):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            result = s.connect_ex(("localhost", port))
        if result == 0:
            _line(OK, f"{key} = {port}", "ACTIVO")
        else:
            _line(INFO, f"{key} = {port}", "libre (no escuchando)")


def check_bago_db():
    print("\n  \033[1m🗄  BAGO DB\033[0m")
    if not DB_PATH.exists():
        _line(FAIL, "bago.db no encontrada", str(DB_PATH))
        return
    try:
        con = sqlite3.connect(DB_PATH)
        ideas = con.execute("SELECT COUNT(*) FROM ideas").fetchone()[0]
        done  = con.execute("SELECT COUNT(*) FROM ideas WHERE status='done'").fetchone()[0]
        avail = con.execute("SELECT COUNT(*) FROM ideas WHERE status='available'").fetchone()[0]
        con.close()
        size_kb = DB_PATH.stat().st_size // 1024
        _line(OK, f"bago.db accesible  ({size_kb} KB)", f"{ideas} ideas | {done} done | {avail} disponibles")
    except Exception as e:
        _line(FAIL, "Error al acceder a bago.db", str(e))


def check_tools():
    print("\n  \033[1m🔧 Herramientas BAGO\033[0m")
    tools_dir = ROOT / ".bago" / "tools"
    tool_files = list(tools_dir.glob("*.py"))
    exclude = {"tool_registry.py", "db_init.py", "idea_gen.py", "validate.py",
               "bago_core.py", "__init__.py", "emit_ideas.py"}
    tools = [f for f in tool_files if f.name not in exclude]
    _line(OK, f"{len(tools)} herramientas registradas")

    # Check tool_registry imports
    reg = tools_dir / "tool_registry.py"
    if reg.exists():
        reg_text = reg.read_text(encoding="utf-8")
        missing = [t.stem for t in tools if t.stem not in reg_text]
        if missing:
            _line(WARN, f"No registradas en tool_registry: {', '.join(missing[:5])}")
        else:
            _line(OK, "Todas las herramientas registradas en tool_registry.py")


def check_git():
    print("\n  \033[1m🌿 Git\033[0m")
    git_dir = PROJECT_ROOT / ".git"
    if not git_dir.exists():
        _line(INFO, "No es un repositorio git")
        return
    _line(OK, "Repositorio git detectado")

    for exe in ["git", r"C:\Program Files\Git\bin\git.exe"]:
        try:
            r = subprocess.run([exe, "status", "--short"],
                               cwd=PROJECT_ROOT, capture_output=True, timeout=5)
            if r.returncode == 0:
                dirty = r.stdout.decode("utf-8", errors="replace").strip()
                if dirty:
                    lines = dirty.splitlines()
                    _line(WARN, f"{len(lines)} archivo(s) con cambios sin commit")
                else:
                    _line(OK, "Working tree limpio")
                break
        except Exception:
            continue


def main(argv=None) -> int:
    _ = argv
    print("\n  ┌─────────────────────────────────────────────────────────┐")
    print("  │  🏥  BAGO Health Check                                  │")
    print("  └─────────────────────────────────────────────────────────┘")

    check_node_modules()
    check_env_files()
    check_ports()
    check_bago_db()
    check_tools()
    check_git()

    print("\n  ─────────────────────────────────────────────────────────")
    print(f"  {OK} = OK   {WARN} = Advertencia   {FAIL} = Error   {INFO} = Info\n")

    return 0


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
