#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unified environment tool for BAGO.

Usage:
  python env.py                 -> list env files
  python env.py list [-v]
  python env.py table
  python env.py diff [app] [--missing]
  python env.py check [--json]
  python env.py set <app> KEY=value
  python env.py setup [--path PATH] [--app NAME] [--dry-run] [--force]
"""
from __future__ import annotations

import json
import re
import os
import secrets
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / ".bago" / "state"
_PORT_RE = re.compile(r"PORT|_PORT$", re.I)
_URL_RE = re.compile(r"URL|HOST|ORIGIN|ENDPOINT", re.I)
_SECRET_RE = re.compile(r"SECRET|TOKEN|KEY|PASSWORD|PWD|PASS|AUTH|JWT", re.I)
_BOOL_RE = re.compile(r"ENABLE|DISABLE|FLAG|SECURE|TRUST|UPDATING", re.I)
_INT_RE = re.compile(r"MAX|LIMIT|SIZE|TTL|WINDOW|TIMEOUT|BYTES|ITEMS|SECONDS", re.I)
_MODE_RE = re.compile(r"ENV|ENVIRONMENT|NODE_ENV|MODE", re.I)
_DEV_DEFAULTS = {
    "DATABASE_URL": "postgres://postgres:tpvlocal@localhost:5432/tpv",
    "API_PORT": "8788",
    "API_HOST": "0.0.0.0",
    "API_DB_SEARCH_PATH": "public",
    "AUTH_JWT_SECRET": "",
    "AUTH_JWT_KID": "auth-v1",
    "AUTH_ACCESS_TTL_SECONDS": "600",
    "AUTH_REFRESH_TTL_SECONDS": "2592000",
    "AUTH_COOKIE_SECURE": "false",
    "API_CORS_ORIGINS": "http://localhost:3000,http://localhost:3001,http://localhost:5173,https://localhost,null",
    "API_JSON_LIMIT_BYTES": "1048576",
    "API_RATE_LIMIT_WINDOW_MS": "60000",
    "API_RATE_LIMIT_MAX_READS": "300",
    "API_RATE_LIMIT_MAX_WRITES": "60",
    "API_STATE_COLLECTION_MAX_ITEMS": "10000",
    "API_DOCUMENT_LINES_MAX_ITEMS": "500",
    "API_DOCUMENT_PAYMENTS_MAX_ITEMS": "200",
    "API_TRUST_PROXY": "false",
    "SERVER_UPDATING": "false",
    "NODE_ENV": "development",
    "NODE_VERSION": "22.16.0",
    "VITE_SERVER_MODE": "true",
    "VITE_API_URL": "/backend",
    "SUPERADMIN_MASTER_KEY": "",
    "API_TOKEN": "",
}


def GREEN(s: str) -> str: return f"\033[32m{s}\033[0m"
def RED(s: str) -> str: return f"\033[31m{s}\033[0m"
def YELLOW(s: str) -> str: return f"\033[33m{s}\033[0m"
def DIM(s: str) -> str: return f"\033[2m{s}\033[0m"
def BOLD(s: str) -> str: return f"\033[1m{s}\033[0m"
def CYAN(s: str) -> str: return f"\033[36m{s}\033[0m"


def _load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _load_project() -> Path | None:
    gs = _load_json(STATE / "global_state.json", {})
    if not isinstance(gs, dict):
        return None
    path = gs.get("active_project", {}).get("path", "")
    return Path(path) if path else None


def _get_project_root() -> Path:
    project = _load_project()
    return project if project and project.exists() else ROOT.parent


def _parse_env(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" in stripped:
            key, _, value = stripped.partition("=")
            result[key.strip()] = value.strip().split("  #", 1)[0].strip().strip('"').strip("'")
        else:
            result[stripped] = ""
    return result


def _find_env_files(project: Path) -> dict[str, dict[str, dict[str, str]]]:
    apps_dir = project / "apps"
    result: dict[str, dict[str, dict[str, str]]] = {}
    candidates = [project] + (list(apps_dir.iterdir()) if apps_dir.exists() else [])
    for app_path in candidates:
        if not app_path.is_dir():
            continue
        name = "root" if app_path == project else app_path.name
        files = {}
        for fname in (".env", ".env.example", ".env.local", ".env.production"):
            fp = app_path / fname
            if fp.exists():
                files[fname] = _parse_env(fp)
        if files:
            result[name] = files
    return result


def _all_keys(env_map) -> set[str]:
    keys: set[str] = set()
    for app_files in env_map.values():
        for vars_ in app_files.values():
            keys.update(vars_.keys())
    return keys


def cmd_list(env_map: dict, verbose: bool = False):
    print()
    for app, files in sorted(env_map.items()):
        for fname, vars_ in files.items():
            print(f"  {CYAN(app)}/{fname}  ({len(vars_)} vars)")
            if verbose:
                for key, value in sorted(vars_.items()):
                    masked = value[:4] + "***" if len(value) > 6 else ("***" if value else "")
                    print(f"      {DIM(key):<30} = {masked}")
    print()


def cmd_table(env_map: dict):
    keys = sorted(_all_keys(env_map))
    apps = sorted(env_map)
    if not keys:
        print("  (no env vars found)")
        return
    def _get(app: str, key: str) -> str | None:
        for fname in (".env", ".env.local", ".env.example", ".env.production"):
            if fname in env_map[app] and key in env_map[app][fname]:
                return fname
        return None
    col_w, app_w = 28, 14
    print()
    print(f"  {BOLD('VARIABLE'):<{col_w}}" + "".join(f"  {CYAN(app[:app_w]):<{app_w}}" for app in apps))
    print("  " + "─" * (col_w + len(apps) * (app_w + 2)))
    for key in keys:
        row = f"  {key:<{col_w}}"
        for app in apps:
            src = _get(app, key)
            if src:
                row += f"  {(GREEN('✔') if src == '.env' else YELLOW('○')):<{app_w}}"
            else:
                row += f"  {RED('✗'):<{app_w}}"
        print(row)
    print(f"\n  {GREEN('✔')} = .env real   {YELLOW('○')} = .env.example only   {RED('✗')} = missing\n")


def cmd_set(env_map: dict, app: str, assignment: str, project: Path):
    if "=" not in assignment:
        print("  ✖ Formato inválido. Usa: KEY=valor", file=sys.stderr)
        return 1
    key, _, value = assignment.partition("=")
    key = key.strip().upper()
    env_path = project / ".env" if app == "root" else project / "apps" / app / ".env"
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    updated = False
    for idx, line in enumerate(lines):
        if re.match(rf"^{re.escape(key)}\s*=", line):
            lines[idx] = f"{key}={value}"
            updated = True
            break
    if not updated:
        lines.append(f"{key}={value}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  {GREEN('✔')} {key} {'actualizado' if updated else 'añadido'} en {env_path.relative_to(project)}")
    return 0


def _check_app_diff(app_name: str, app_dir: Path, only_missing: bool) -> int:
    env_file = app_dir / ".env"
    example_file = app_dir / ".env.example"
    if not example_file.exists():
        print(f"  {YELLOW('⚠')} {BOLD(app_name):<16} sin .env.example")
        return 0
    env_keys = set(_parse_env(env_file))
    example_keys = set(_parse_env(example_file))
    missing = example_keys - env_keys
    extra = env_keys - example_keys
    if not missing and not extra:
        print(f"  {GREEN('✅')} {BOLD(app_name):<16} {DIM(str(len(env_keys)))} claves — OK")
        return 0
    print(f"  {(RED('❌') if missing else YELLOW('⚠'))} {BOLD(app_name):<16} {(RED(str(len(missing)) + ' faltantes') + '  ') if missing else ''}{YELLOW(str(len(extra)) + ' extras') if extra else ''}")
    if missing:
        print(f"    {RED('Faltan en .env')} (definidas en .env.example):")
        for key in sorted(missing):
            print(f"      {RED('─')} {key}")
    if extra and not only_missing:
        print(f"    {YELLOW('Extra en .env')} (no en .env.example):")
        for key in sorted(extra):
            print(f"      {YELLOW('+')} {DIM(key)}")
    return 1 if missing else 0


def diff_main(argv: list[str]) -> int:
    only_missing = "--missing" in argv
    filters = [arg for arg in argv if not arg.startswith("-")]
    project = _load_project()
    if not project:
        print(f"\n  {RED('❌')} No hay proyecto configurado. Ejecuta: bago config\n")
        return 1
    candidates = [("root", project), ("server", project / "apps" / "server"), ("web", project / "apps" / "web"), ("electron", project / "apps" / "electron")]
    apps = [(name, path) for name, path in candidates if path.exists()]
    if filters:
        apps = [(name, path) for name, path in apps if name in filters]
        if not apps:
            print(f"\n  {RED('❌')} App no encontrada: {', '.join(filters)}\n")
            return 1
    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Env Diff                                            │")
    print("  └─────────────────────────────────────────────────────────────┘")
    print(f"  Proyecto: {DIM(str(project))}\n")
    total_issues = sum(_check_app_diff(app_name, app_dir, only_missing) for app_name, app_dir in apps)
    print(f"\n  {GREEN('✅ Todo OK') if total_issues == 0 else RED(f'❌ {total_issues} app(s) con claves faltantes')}" + (" — sin claves faltantes" if total_issues == 0 else ""))
    print()
    return 0 if total_issues == 0 else 1


def _run(cmd: list[str], timeout: int = 5) -> tuple[int, str]:
    try:
        use_shell = sys.platform == "win32" and cmd[0].endswith(".cmd")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=use_shell)
        return result.returncode, (result.stdout + result.stderr).strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        if sys.platform == "win32" and not cmd[0].endswith(".cmd"):
            try:
                cmd_win = [cmd[0] + ".cmd"] + cmd[1:]
                result = subprocess.run(cmd_win, capture_output=True, text=True, timeout=timeout)
                return result.returncode, (result.stdout + result.stderr).strip()
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                pass
        return 1, ""


def _port_in_use(port: int) -> bool:
    try:
        raw = subprocess.run(["netstat", "-ano"], capture_output=True, timeout=5).stdout
        text = raw.decode("cp1252", errors="replace")
        return f":{port} " in text or f":{port}\t" in text
    except Exception:
        return False


def _check_node() -> dict:
    code, out = _run(["node", "--version"])
    if code == 0 and out.startswith("v"):
        major = int(out[1:].split(".")[0])
        if major >= 18:
            return {"name": "Node.js", "status": "ok", "detail": out}
        return {"name": "Node.js", "status": "warn", "detail": f"{out} (recomendado v18+)", "fix": "Actualiza Node.js"}
    return {"name": "Node.js", "status": "error", "detail": "no encontrado", "fix": "Instala Node.js en https://nodejs.org"}


def _check_npm() -> dict:
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    code, out = _run([npm_cmd, "--version"])
    if code == 0:
        return {"name": "npm", "status": "ok", "detail": f"v{out}", "installable": False}
    return {
        "name": "npm",
        "status": "error",
        "detail": "no encontrado",
        "fix": "Instala npm (viene con Node.js)",
        "installable": True,
        "install_hint": (
            "npm gestiona paquetes JavaScript/TypeScript. Lo necesitas si:\n"
            "  - Desarrollas proyectos web con React, Vite, Next.js...\n"
            "  - Quieres usar 'bago serve' o el servidor API local\n"
            "  - Trabajas con proyectos que tienen package.json\n"
            "  - Necesitas instalar dependencias con npm install\n\n"
            "  Si solo usas Python, puedes omitirlo."
        ),
    }


def _check_python() -> dict:
    version = f"v{sys.version.split()[0]}"
    return {"name": "Python", "status": "ok", "detail": version} if sys.version_info >= (3, 10) else {"name": "Python", "status": "warn", "detail": f"{version} (recomendado 3.10+)", "fix": "Actualiza Python"}


def _check_git() -> dict:
    code, out = _run(["git", "--version"])
    return {"name": "git", "status": "ok", "detail": out[:30]} if code == 0 else {"name": "git", "status": "warn", "detail": "no encontrado", "fix": "Instala git"}


def _check_postgres() -> dict:
    code, out = _run(["psql", "--version"])
    if code != 0:
        return {"name": "PostgreSQL", "status": "warn", "detail": "psql no encontrado (opcional)", "fix": "Instala PostgreSQL o usa DB remota"}
    return {"name": "PostgreSQL", "status": "ok", "detail": f"{out[:30]} · corriendo :5432"} if _port_in_use(5432) else {"name": "PostgreSQL", "status": "warn", "detail": f"{out[:30]} · no corriendo", "fix": "Ejecuta: bago db-local"}


def _check_ports() -> dict:
    ports = {3000: "web", 5173: "vite", 8788: "server", 4173: "preview"}
    in_use = [f":{port}({label})" for port, label in ports.items() if _port_in_use(port)]
    return {"name": "Puertos del proyecto", "status": "ok", "detail": "en uso: " + ", ".join(in_use) if in_use else "todos libres"}


def _check_env_files(project: Path | None) -> dict:
    if not project or not project.exists():
        return {"name": "Archivos .env", "status": "warn", "detail": "proyecto no configurado", "fix": "bago config"}
    apps_dir = project / "apps"
    if not apps_dir.exists():
        return {"name": "Archivos .env", "status": "ok", "detail": "no hay directorio apps/"}
    missing = [d.name for d in apps_dir.iterdir() if d.is_dir() and (d / ".env.example").exists() and not (d / ".env").exists()]
    return {"name": "Archivos .env", "status": "ok", "detail": "presentes en todas las apps"} if not missing else {"name": "Archivos .env", "status": "error", "detail": f"faltante en: {', '.join(missing)}", "fix": "Ejecuta: bago env setup"}


def _check_node_modules(project: Path | None) -> dict:
    if not project or not project.exists():
        return {"name": "node_modules", "status": "warn", "detail": "proyecto no configurado"}
    apps_dir = project / "apps"
    if not apps_dir.exists():
        return {"name": "node_modules", "status": "ok", "detail": "no hay directorio apps/"}
    missing = [d.name for d in apps_dir.iterdir() if d.is_dir() and (d / "package.json").exists() and not (d / "node_modules").exists()]
    return {"name": "node_modules", "status": "ok", "detail": "instalados en todas las apps"} if not missing else {"name": "node_modules", "status": "error", "detail": f"faltante en: {', '.join(missing)}", "fix": "Ejecuta: bago deps --install"}


def _check_bago_state() -> dict:
    essential = [STATE / "global_state.json", STATE / "implemented_ideas.json", STATE / "bago.db"]
    missing = [path.name for path in essential if not path.exists()]
    return {"name": "Estado BAGO", "status": "ok", "detail": "archivos de estado presentes"} if not missing else {"name": "Estado BAGO", "status": "warn", "detail": f"faltan: {', '.join(missing)}", "fix": "bago init"}


def _check_server() -> dict:
    try:
        with urllib.request.urlopen("http://localhost:8788/health", timeout=2) as response:
            if response.status < 400:
                return {"name": "Servidor local", "status": "ok", "detail": f"HTTP {response.status} en :8788"}
    except urllib.error.HTTPError as exc:
        return {"name": "Servidor local", "status": "warn", "detail": f"HTTP {exc.code} en :8788"}
    except Exception:
        pass
    return {"name": "Servidor local", "status": "warn", "detail": "no responde en :8788", "fix": "npm run dev en apps/server"}


def diagnostic_main(argv: list[str]) -> int:
    output_json = "--json" in argv
    project = _load_project()
    checks = [
        _check_node(), _check_npm(), _check_python(), _check_git(), _check_postgres(), _check_ports(),
        _check_env_files(project), _check_node_modules(project), _check_bago_state(), _check_server(),
    ]
    if output_json:
        print(json.dumps(checks, ensure_ascii=False, indent=2))
        return 1 if any(item["status"] == "error" for item in checks) else 0
    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Doctor — Diagnóstico del entorno                    │")
    print("  └─────────────────────────────────────────────────────────────┘")
    if project:
        print(f"  Proyecto : {project.name}")
    print()
    icons = {"ok": GREEN("✅"), "warn": YELLOW("⚠ "), "error": RED("❌")}
    errors = warnings = 0
    for item in checks:
        print(f"  {icons.get(item['status'], '?')} {BOLD(item['name']):<30}  {DIM(item.get('detail', ''))}")
        if item.get("fix") and item["status"] in {"warn", "error"}:
            print(f"       {CYAN('→')} {item['fix']}")
        errors += item["status"] == "error"
        warnings += item["status"] == "warn"
    print()
    if errors == 0 and warnings == 0:
        print(f"  {GREEN('✅  Entorno saludable — todo OK.')}\n")
    elif errors > 0:
        print(f"  {RED(f'❌  {errors} error(es) · {warnings} advertencia(s).')}\n")
    else:
        print(f"  {YELLOW(f'⚠  {warnings} advertencia(s). Entorno funcional.')}\n")

    # Interactive install prompt for missing tools
    installable = [c for c in checks if c.get("installable") and c["status"] == "error"]
    if installable and "--json" not in argv:
        for item in installable:
            name = item["name"]
            hint = item.get("install_hint", "")
            print(f"\n  {BOLD('Instalar ' + name + '?')} [y/N]")
            if hint:
                for line in hint.splitlines():
                    print(f"  {DIM(line)}")
            try:
                answer = input("  -> ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                answer = ""
            if answer in {"y", "yes", "s", "si"}:
                _install_missing(name)
            else:
                print(f"  {DIM(name + ': omitido. Puedes instalarlo más tarde con: bago env check')}")
                print()
    return 1 if errors else (2 if warnings else 0)


def _install_missing(name: str) -> None:
    """Install missing tool via winget (Windows) or brew/apt (macOS/Linux)."""
    print(f"\n  {BOLD('Instalando ' + name + '...')}")
    if name == "npm":
        _install_npm()
    else:
        print(f"  {YELLOW('\u26a0  Instalación autom\u00e1tica no disponible para ' + name)}")
        print(f"  Consulta la documentación para instalar {name}.")


def _install_npm() -> None:
    """Install npm via Node.js using winget or direct download."""
    if sys.platform == "win32":
        winget = shutil.which("winget")
        if winget:
            print(f"  {CYAN('→')} Usando winget para instalar Node.js LTS (incluye npm)...")
            rc = subprocess.run(
                [winget, "install", "OpenJS.NodeJS.LTS", "--accept-package-agreements", "--accept-source-agreements"],
                capture_output=True, text=True, timeout=300,
            )
            if rc.returncode == 0:
                print(f"  {GREEN('✅ Node.js + npm instalado via winget')}")
                _refresh_path()
                npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
                code, ver = _run([npm_cmd, "--version"])
                if code == 0:
                    print(f"  {GREEN('✅ npm v' + ver + ' disponible')}")
                print(f"  {DIM('Reinicia la terminal para usar npm en nuevas sesiones.')}")
                return
            print(f"  {YELLOW('\u26a0 winget falló, intentando descarga directa...')}")
        print(f"  {CYAN('→')} Descargando Node.js LTS...")
        try:
            arch = os.environ.get("PROCESSOR_ARCHITECTURE", "AMD64")
            arch_suffix = "x64" if "64" in arch else "x86"
            msi_url = f"https://nodejs.org/dist/v22.16.0/node-v22.16.0-{arch_suffix}.msi"
            msi_path = Path.home() / "Downloads" / "node-latest.msi"
            print(f"  {DIM('Descargando: ' + msi_url)}")
            urllib.request.urlretrieve(msi_url, str(msi_path))
            print(f"  {GREEN('✅')} Descargado en: {msi_path}")
            print(f"  {BOLD('Ejecuta el instalador para completar la instalación:')}")
            print(f"  {CYAN(str(msi_path))}")
            os.startfile(str(msi_path))
        except Exception as exc:
            print(f"  {RED('❌')} No se pudo descargar: {exc}")
            print(f"  {BOLD('Instala Node.js manualmente desde:')} https://nodejs.org")
    else:
        brew = shutil.which("brew")
        if brew:
            print(f"  {CYAN('→')} Usando Homebrew...")
            subprocess.run([brew, "install", "node"], timeout=300)
        else:
            print(f"  {BOLD('Instala Node.js manualmente desde:')} https://nodejs.org")


def _refresh_path() -> None:
    """Refresh PATH in current process after install (Windows)."""
    if sys.platform != "win32":
        return
    try:
        import winreg
        for key_path in [
            (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
            (winreg.HKEY_CURRENT_USER, r"Environment"),
        ]:
            try:
                key = winreg.OpenKey(key_path[0], key_path[1], 0, winreg.KEY_READ)
                path_val = winreg.QueryValueEx(key, "Path")[0]
                os.environ["PATH"] = path_val + ";" + os.environ.get("PATH", "")
                winreg.CloseKey(key)
            except Exception:
                pass
    except ImportError:
        pass



def _detect_type(key: str, example_val: str) -> str:
    if _PORT_RE.search(key): return "port"
    if _SECRET_RE.search(key): return "secret"
    if _URL_RE.search(key): return "url"
    if _BOOL_RE.search(key): return "bool"
    if _INT_RE.search(key): return "int"
    if _MODE_RE.search(key): return "mode"
    return "string"


def _safe_dev_value(key: str, example_val: str) -> tuple[str, str]:
    if key in _DEV_DEFAULTS:
        value = _DEV_DEFAULTS[key]
        if value == "":
            return (secrets.token_hex(32), "auto-generado") if _SECRET_RE.search(key) else ("", "opcional en dev")
        return value, "default dev"
    vtype = _detect_type(key, example_val)
    if vtype == "secret": return secrets.token_hex(32), "auto-generado (dev)"
    if vtype == "port": return example_val or "8080", "puerto dev"
    if vtype == "bool": return "false", "seguro en dev"
    if vtype == "int": return example_val or "0", "valor ejemplo"
    if vtype == "url": return example_val or "http://localhost:3000", "URL local"
    if vtype == "mode": return "development", "entorno dev"
    if example_val and "production" not in example_val.lower() and "secret" not in example_val.lower():
        return example_val, "del ejemplo"
    return "", "requiere valor manual"


def _parse_dotenv_example(path: Path) -> list[tuple[str, str, str]]:
    result = []
    pending_comment = ""
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                pending_comment = stripped
                continue
            if "=" in stripped and stripped:
                key, _, value = stripped.partition("=")
                result.append((key.strip(), value.strip(), pending_comment))
                pending_comment = ""
            else:
                pending_comment = ""
    except Exception as exc:
        print(f"  ⚠  No se pudo leer {path}: {exc}")
    return result


def _find_env_examples(project: Path, app_filter: str | None) -> list[Path]:
    if app_filter:
        candidate = project / "apps" / app_filter / ".env.example"
        return [candidate] if candidate.exists() else []
    root_example = [project / ".env.example"] if (project / ".env.example").exists() else []
    return root_example + sorted(project.glob("apps/*/.env.example"))


def _generate_env(entries: list[tuple[str, str, str]]) -> list[str]:
    lines = ["# Generated by bago env — safe development values", "# Edit secrets before using in production", ""]
    for key, ex_val, comment in entries:
        value, note = _safe_dev_value(key, ex_val)
        if comment:
            lines.append(comment)
        lines.append(f"{key}={value}  # {note}")
    return lines


def _col(text: str, width: int) -> str:
    return str(text).ljust(width)[:width]


def setup_main(argv: list[str]) -> int:
    dry_run = "--dry-run" in argv
    force = "--force" in argv
    project = None
    app_filter = None
    if "--path" in argv:
        idx = argv.index("--path")
        if idx + 1 < len(argv):
            project = Path(argv[idx + 1])
    if "--app" in argv:
        idx = argv.index("--app")
        if idx + 1 < len(argv):
            app_filter = argv[idx + 1]
    if project is None:
        project = _load_project()
    if project is None or not project.exists():
        print("  ⚠  No se encontró proyecto activo. Usa --path /ruta/al/proyecto")
        return 1
    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Generador de .env                                   │")
    print("  └─────────────────────────────────────────────────────────────┘")
    print(f"  Proyecto: {project}")
    examples = _find_env_examples(project, app_filter)
    if not examples:
        print("  ⚠  No se encontró ningún .env.example en el proyecto.")
        return 1
    for example_path in examples:
        app_dir = example_path.parent
        env_path = app_dir / ".env"
        label = f"{app_dir.relative_to(project)}" if app_dir != project else "."
        print(f"\n  📂  {label}.env.example  →  .env\n")
        if env_path.exists() and not force and not dry_run:
            print("  ℹ  .env ya existe (usa --force para sobreescribir)")
            continue
        entries = _parse_dotenv_example(example_path)
        if not entries:
            print("  ⚠  No se encontraron variables en el ejemplo.")
            continue
        w1, w2, w3 = 38, 20, 18
        print(f"  {'Variable'.ljust(w1)}  {'Valor dev'.ljust(w2)}  {'Nota'.ljust(w3)}")
        print("  " + "-" * (w1 + w2 + w3 + 4))
        for key, ex_val, _ in entries:
            value, note = _safe_dev_value(key, ex_val)
            display = value[:18] + "…" if len(value) > 18 else value
            print(f"  {_col(key, w1)}  {_col(display, w2)}  {_col(note, w3)}")
        if dry_run:
            print("\n  🔍  DRY-RUN: no se escribió .env")
            continue
        env_path.write_text("\n".join(_generate_env(entries)) + "\n", encoding="utf-8")
        print(f"\n  ✅  Escrito: {env_path.relative_to(project)}")
    return 0


def _self_test() -> int:
    assert _detect_type("API_PORT", "") == "port"
    assert _safe_dev_value("NODE_ENV", "production")[0] == "development"
    print("  2/2 tests pasaron")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--test" in args:
        return _self_test()
    project = _get_project_root()
    env_map = _find_env_files(project)
    if not args:
        cmd_list(env_map, verbose=False)
        return 0
    sub = args[0]
    rest = args[1:]
    if sub in {"-h", "--help", "help"}:
        print(__doc__)
        return 0
    if sub == "list":
        cmd_list(env_map, verbose=("--verbose" in rest or "-v" in rest))
        return 0
    if sub == "table":
        cmd_table(env_map)
        return 0
    if sub == "set":
        if len(rest) < 2:
            print("Uso: python env.py set <app> KEY=value")
            return 1
        return cmd_set(env_map, rest[0], rest[1], project)
    if sub == "diff":
        return diff_main(rest)
    if sub in {"check", "doctor"}:
        return diagnostic_main(rest)
    if sub == "setup":
        return setup_main(rest)
    if sub == "manager":
        return main(rest)
    if sub == "check-vars":
        return diff_main([*rest, "--missing"])
    return main(["list", *args])


if __name__ == "__main__":
    raise SystemExit(main())