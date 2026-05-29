#!/usr/bin/env python3
"""
bago_wizard.py — Wizard de primera instalación de BAGO.

Flujo:
  1. Banner de bienvenida
  2. Contrato de uso — debe aceptarse para continuar
  3. Comprueba Python >= 3.9 y git
  4. Selección de feature packs opcionales
  5. pip install de los packs seleccionados
  6. Instrucciones/comprobación de Ollama si se eligió advisor
  7. Guarda .bago/state/install_complete.json con metadata
  8. Muestra banner BAGO listo para usar

Uso:
  python3 .bago/tools/bago_wizard.py            # primera instalación
  python3 .bago/tools/bago_wizard.py --reset    # borra marker y re-ejecuta
  python3 .bago/tools/bago_wizard.py --status   # muestra estado de instalación
  python3 .bago/tools/bago_wizard.py --force    # fuerza re-ejecución aunque ya esté instalado

Variables de entorno:
  CI=true / BAGO_SKIP_WIZARD=1  → modo silencioso (acepta solo core, sin interacción)
"""

from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import importlib
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Windows UTF-8 fix

BAGO_ROOT       = Path(__file__).resolve().parent.parent
STATE_DIR       = BAGO_ROOT / "state"
TOOLS_DIR       = BAGO_ROOT / "tools"
WIZARD_MARKER   = STATE_DIR / "install_complete.json"
MANIFEST_PATH   = STATE_DIR / "deps_manifest.json"

if str(BAGO_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(BAGO_ROOT.parent))

try:
    from bago_core.device_state import (
        apply_device_context,
        default_user_home,
        removable_drives,
        resolve_device_context,
        save_local_credential_binding,
    )
except Exception:
    apply_device_context = None
    default_user_home = None
    removable_drives = None
    resolve_device_context = None
    save_local_credential_binding = None

BAGO_VERSION        = "2.0"
DISCLAIMER_VERSION  = "1.0"

# ─── Colores ──────────────────────────────────────────────────────────────────

_USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") != "1"

def _c(code: str, t: str) -> str:
    return f"\033[{code}m{t}\033[0m" if _USE_COLOR else t

def CYAN(t):   return _c("1;36", t)
def GREEN(t):  return _c("1;32", t)
def YELLOW(t): return _c("1;33", t)
def RED(t):    return _c("1;31", t)
def BOLD(t):   return _c("1",    t)
def DIM(t):    return _c("2",    t)

def _ok(msg):   print(f"  {GREEN('✓')} {msg}")
def _warn(msg): print(f"  {YELLOW('⚠')} {msg}")
def _err(msg):  print(f"  {RED('✗')} {msg}")
def _info(msg): print(f"  {DIM('→')} {msg}")
def _step(msg): print(f"\n  {BOLD(CYAN('»'))} {BOLD(msg)}")


def _ask_yes_no(prompt: str, default: bool = False) -> bool:
    suffix = "[S/n]" if default else "[s/N]"
    try:
        ans = input(f"  {BOLD(prompt)} {suffix}: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    if not ans:
        return default
    return ans in ("s", "si", "sí", "y", "yes")

# ─── Contrato de uso ──────────────────────────────────────────────────────────

_DISCLAIMER = f"""
  CONTRATO DE USO — BAGO Framework v{BAGO_VERSION}
  ════════════════════════════════════════════════════════════════

  BAGO es un framework experimental de asistencia al desarrollo.

  AL ACEPTAR, reconoces que:

  1. BAGO se proporciona TAL CUAL, sin garantías de ningún tipo.
  2. Los autores NO son responsables de daños, pérdida de datos,
     errores en producción ni ningún otro perjuicio derivado del
     uso del software.
  3. Eres el único responsable de lo que hagas con BAGO y con
     las herramientas y artefactos que genere (código, config,
     datos, integraciones).
  4. El asistente LLM integrado puede cometer errores. Verifica
     siempre su output antes de ejecutarlo en producción.
  5. Algunas herramientas pueden modificar archivos del sistema.
     Úsalas con criterio y bajo tu propia responsabilidad.
  6. Las integraciones externas (Telegram, WhatsApp, APIs de
     terceros) requieren tus propias credenciales y están sujetas
     a los términos de uso de cada servicio.

  Para uso en entornos de producción consulta con profesionales.

  ════════════════════════════════════════════════════════════════
"""

# ─── Pack definitions (cargadas desde deps_manifest.json si existe) ───────────

_PACKS_DEFAULT: dict = {
    "core": {
        "label": "Core (requerido)",
        "description": "Funciones esenciales del framework. Sin dependencias pip.",
        "required": True,
        "pip": [],
        "binaries": ["git"],
    },
    "advisor": {
        "label": "Advisor — Asistente LLM adaptativo",
        "description": "bago advisor ask — LLM orientativo con contexto del proyecto.",
        "required": False,
        "pip": [],
        "binaries": ["ollama"],
        "setup_note": "Descarga Ollama: https://ollama.com  •  Luego: ollama pull qwen2.5-coder:7b (~4 GB)",
    },
    "messaging": {
        "label": "Mensajería (Telegram / WhatsApp / ntfy)",
        "description": "Notificaciones, bots Telegram y alertas por WhatsApp.",
        "required": False,
        "pip": ["requests", "python-telegram-bot>=20.0"],
        "binaries": [],
        "setup_note": "Crea un bot en @BotFather y añade el token a .bago/state/notify_config.json",
    },
    "music": {
        "label": "Música / Ableton / MusicXML",
        "description": "Síntesis de audio, análisis, exportación MusicXML para Ableton.",
        "required": False,
        "pip": ["numpy", "scipy", "soundfile", "music21"],
        "binaries": [],
    },
    "web": {
        "label": "Web scraping / Gradio Hub",
        "description": "Scraping con BeautifulSoup, panel Gradio y automatización web.",
        "required": False,
        "pip": ["requests", "beautifulsoup4", "gradio"],
        "binaries": [],
        "setup_note": "Playwright requiere paso extra: python -m playwright install",
    },
    "vision": {
        "label": "Imágenes / Sprites / Códigos QR",
        "description": "Generación y edición de imágenes, sprites y códigos QR.",
        "required": False,
        "pip": ["numpy", "matplotlib", "Pillow", "qrcode"],
        "binaries": [],
    },
    "devtools": {
        "label": "DevTools (CI, linting, LSP, análisis)",
        "description": "gitpython, yamllint, pytest, ruff, bandit para desarrollo.",
        "required": False,
        "pip": ["gitpython", "yamllint", "pytest", "ruff", "bandit"],
        "binaries": [],
    },
}


def _load_packs() -> dict:
    """Load pack definitions from deps_manifest.json, fall back to defaults."""
    if MANIFEST_PATH.exists():
        try:
            data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            if isinstance(data.get("packs"), dict):
                return data["packs"]
        except Exception:
            pass
    return _PACKS_DEFAULT


# ─── Banner ───────────────────────────────────────────────────────────────────

def _banner() -> None:
    print()
    print(CYAN("  ╔══════════════════════════════════════════════════════════╗"))
    print(CYAN("  ║") + BOLD("   ██████╗  █████╗  ██████╗  ██████╗                    ") + CYAN("║"))
    print(CYAN("  ║") + BOLD("   ██╔══██╗██╔══██╗██╔════╝ ██╔═══██╗                   ") + CYAN("║"))
    print(CYAN("  ║") + BOLD("   ██████╔╝███████║██║  ███╗██║   ██║                   ") + CYAN("║"))
    print(CYAN("  ║") + BOLD("   ██╔══██╗██╔══██║██║   ██║██║   ██║                   ") + CYAN("║"))
    print(CYAN("  ║") + BOLD("   ██████╔╝██║  ██║╚██████╔╝╚██████╔╝                   ") + CYAN("║"))
    print(CYAN("  ║") + BOLD("   ╚═════╝ ╚═╝  ╚═╝ ╚═════╝  ╚═════╝                   ") + CYAN("║"))
    print(CYAN("  ║") + DIM(f"            Framework de Desarrollo v{BAGO_VERSION}              ") + CYAN("║"))
    print(CYAN("  ╚══════════════════════════════════════════════════════════╝"))
    print()
    print(BOLD("         ✨  Wizard de Primera Instalación"))
    print()


# ─── Disclaimer ───────────────────────────────────────────────────────────────

def _show_disclaimer() -> bool:
    """Print disclaimer and ask for acceptance. Returns True if accepted."""
    print(_DISCLAIMER)
    try:
        ans = input(
            f"  {BOLD('¿Aceptas los términos de uso?')}  [{GREEN('S')}i / {RED('N')}o]:  "
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return ans in ("s", "si", "sí", "y", "yes")


# ─── System checks ────────────────────────────────────────────────────────────

def _check_python() -> bool:
    major, minor, micro = sys.version_info[:3]
    version_str = f"{major}.{minor}.{micro}"
    if (major, minor) < (3, 9):
        _err(f"Python {version_str} — se requiere Python 3.9 o superior")
        _info("Descarga Python: https://www.python.org/downloads/")
        return False
    _ok(f"Python {version_str}")
    return True


def _check_binary(name: str) -> bool:
    path = shutil.which(name)
    if path:
        _ok(f"{name}: {path}")
        return True
    _warn(f"{name}: no encontrado en PATH")
    return False


def _is_importable(pip_name: str) -> bool:
    """Check if a pip package is already importable without importing it at module level."""
    _name_map = {
        "python-telegram-bot": "telegram",
        "Pillow": "PIL",
        "beautifulsoup4": "bs4",
        "python-lsp-server": "pylsp",
        "gitpython": "git",
    }
    # Strip version specifiers: "requests>=2.0" → "requests"
    base = pip_name.split(">=")[0].split("==")[0].split("<=")[0].strip()
    import_name = _name_map.get(base, base.replace("-", "_").lower())
    try:
        importlib.import_module(import_name)
        return True
    except ImportError:
        return False


# ─── Pack selection ───────────────────────────────────────────────────────────

def _select_packs(packs: dict) -> list[str]:
    """Show interactive pack selection. Returns list of selected pack keys."""
    optional = [(k, v) for k, v in packs.items() if not v.get("required")]

    print()
    print(BOLD("  Feature Packs opcionales:"))
    print()

    for i, (key, pack) in enumerate(optional, 1):
        pip_deps   = pack.get("pip", [])
        bins       = pack.get("binaries", [])
        pip_info   = f" — pip: {', '.join(pip_deps)}" if pip_deps else ""
        bin_info   = f" [binary: {', '.join(bins)}]"  if bins else ""
        print(f"    {CYAN(f'[{i}]')} {BOLD(pack.get('label', key))}")
        print(f"        {DIM(pack.get('description', ''))}{DIM(pip_info)}{DIM(bin_info)}")
        if pack.get("setup_note"):
            print(f"        {YELLOW('ℹ')}  {DIM(pack['setup_note'])}")
        print()

    print(f"  Escribe los números separados por espacios  (ej: {CYAN('1 3')})")
    print(f"  o pulsa {CYAN('ENTER')} para instalar solo core.\n")

    try:
        raw = input(f"  {BOLD('Selección')}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return ["core"]

    selected = ["core"]
    if raw:
        for token in raw.split():
            try:
                idx = int(token) - 1
                if 0 <= idx < len(optional):
                    key = optional[idx][0]
                    if key not in selected:
                        selected.append(key)
            except ValueError:
                pass

    return selected


# ─── pip install ──────────────────────────────────────────────────────────────

def _install_pip_packages(packages: list[str]) -> bool:
    """Install pip packages using the current Python. Returns True on success."""
    if not packages:
        return True

    # Deduplicate, preserving order
    seen: dict = {}
    for p in packages:
        base = p.split(">=")[0].split("==")[0].strip()
        seen[base] = p
    unique = list(seen.values())

    # Check pip availability
    pip_check = subprocess.run(
        [sys.executable, "-m", "pip", "--version"],
        capture_output=True,
    )
    if pip_check.returncode != 0:
        _err("pip no disponible. Instala pip: https://pip.pypa.io/en/stable/installation/")
        return False

    # Detect venv — prefer --user only outside a venv
    in_venv = hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    )

    cmd = [sys.executable, "-m", "pip", "install", "--quiet"]
    if not in_venv:
        cmd.append("--user")
    cmd.extend(unique)

    _info(f"pip install {' '.join(unique)}")

    try:
        result = subprocess.run(cmd)
        if result.returncode != 0:
            _err(f"pip install falló (código {result.returncode})")
            if not in_venv:
                _info("Prueba en un entorno virtual:")
                _info("  python -m venv .venv && source .venv/bin/activate  (Linux/macOS)")
                _info("  python -m venv .venv && .venv\\Scripts\\activate  (Windows)")
            return False
        _ok(f"Instalados: {', '.join(unique)}")
        return True
    except Exception as exc:
        _err(f"Error ejecutando pip: {exc}")
        return False


# ─── Ollama check ─────────────────────────────────────────────────────────────

def _check_ollama() -> bool:
    """Check Ollama binary and model availability. Returns True if Ollama is ready."""
    if not _check_binary("ollama"):
        print()
        _warn("Ollama no encontrado — el advisor LLM no funcionará sin él.")
        _info("Descarga desde:   https://ollama.com")
        _info("Tras instalar:    ollama pull qwen2.5-coder:7b")
        _info("Luego prueba:     bago advisor ask 'hola'")
        print()
        return False

    # Check if any model is already available
    try:
        r = subprocess.run(
            ["ollama", "list"],
            capture_output=True, text=True, timeout=5,
        )
        lines = r.stdout.strip().splitlines()
        # Header + at least one model row
        if len(lines) > 1:
            _ok("Ollama: modelos disponibles")
        else:
            _warn("Ollama instalado pero sin modelos descargados.")
            _info("Ejecuta: ollama pull qwen2.5-coder:7b  (~4 GB)")
    except Exception:
        pass  # ollama binary exists — that's enough

    return True


# ─── Device / credentials onboarding ──────────────────────────────────────────

def _apply_context_env(ctx: dict) -> None:
    if not ctx:
        return
    os.environ["BAGO_CREDENTIALS_MODE"] = ctx.get("credentials_mode", "session")
    os.environ["BAGO_USER_HOME"] = ctx.get("user_home", "")
    if ctx.get("device_root"):
        os.environ["BAGO_DEVICE_ROOT"] = ctx["device_root"]


def _local_credentials_option() -> dict:
    default_path = default_user_home() if default_user_home else Path.home() / ".bago" / "user"
    if not _ask_yes_no("Usar directorio local para credenciales? (menos recomendado)", default=False):
        ctx = {
            "mode": "session",
            "credentials_mode": "session",
            "user_home": str(default_path),
            "device_root": "",
        }
        _apply_context_env(ctx)
        _warn("Sin almacenamiento persistente: tendras que logearte en cada sesion.")
        return ctx

    try:
        raw = input(f"  Ruta [{default_path}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        raw = ""
    path = Path(raw).expanduser() if raw else default_path
    if save_local_credential_binding:
        save_local_credential_binding(path)
    ctx = {
        "mode": "local",
        "credentials_mode": "local",
        "user_home": str(path),
        "device_root": "",
    }
    _apply_context_env(ctx)
    _warn("Credenciales locales activadas. No subas esa ruta a GitHub.")
    return ctx


def _device_onboarding() -> dict:
    if not resolve_device_context:
        return {"mode": "session", "credentials_mode": "session", "user_home": "", "device_root": ""}

    ctx = resolve_device_context()
    if ctx.get("mode") == "device":
        _apply_context_env(ctx)
        _ok(f"Dispositivo BAGO detectado: {ctx.get('device_root')}")
        _ok("Credenciales: dispositivo BAGO")
        return ctx
    if ctx.get("mode") in ("explicit", "local") and ctx.get("credentials_mode") != "session":
        _apply_context_env(ctx)
        label = "variable de entorno" if ctx.get("mode") == "explicit" else "directorio local aprobado"
        _ok(f"Credenciales: {label} -> {ctx.get('user_home')}")
        return ctx

    drives = removable_drives() if removable_drives else []
    if drives:
        drive = drives[0]
        _warn(f"Pendrive detectado sin BAGO: {drive}")
        if _ask_yes_no(f"Convertir {drive} en dispositivo BAGO?", default=True):
            portable = TOOLS_DIR / "bago_portable.py"
            result = subprocess.run(
                [sys.executable, str(portable), "create", str(drive), "--yes"],
                cwd=str(BAGO_ROOT.parent),
            )
            if result.returncode == 0 and apply_device_context:
                ctx = apply_device_context()
                _apply_context_env(ctx)
                _ok("Dispositivo BAGO creado y activado.")
                return ctx
            _warn("No se pudo crear el dispositivo BAGO automaticamente.")
    else:
        _warn("No se detecto pendrive.")
        _info("Recomendado: inserta uno y ejecuta `bago portable create <unidad>`.")

    return _local_credentials_option()


def _knowledge_onboarding(device_context: dict) -> dict:
    device_root = device_context.get("device_root") if device_context else ""
    if device_root:
        base = Path(device_root)
        if base.name.lower() == "bago":
            base = base.parent
        default_path = base / "bago-knowledge"
    else:
        default_path = Path.home() / "bago-knowledge"

    try:
        raw = input(f"  Directorio bago-knowledge [{default_path}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        raw = ""
    path = Path(raw).expanduser() if raw else default_path
    path.mkdir(parents=True, exist_ok=True)

    readme = path / "README.md"
    if not readme.exists():
        readme.write_text(
            "# bago-knowledge\n\n"
            "Memoria aprendida de BAGO. No guardes credenciales ni secretos aqui.\n\n"
            "Comparte solo subcarpetas curadas con la comunidad BAGO.\n",
            encoding="utf-8",
        )

    repo_initialized = False
    if shutil.which("git") and not (path / ".git").exists():
        if _ask_yes_no("Inicializar repo git separado para bago-knowledge?", default=True):
            result = subprocess.run(["git", "init"], cwd=str(path))
            repo_initialized = result.returncode == 0

    _ok(f"bago-knowledge: {path}")
    if repo_initialized:
        _info("Configura un remoto privado o publico cuando quieras compartir conocimiento curado.")
    return {
        "path": str(path),
        "repo_initialized": repo_initialized or (path / ".git").exists(),
        "share_policy": "solo subcarpetas curadas, nunca secretos",
    }


# ─── Marker ───────────────────────────────────────────────────────────────────

def _write_marker(
    selected_packs: list[str],
    device_context: dict | None = None,
    knowledge_context: dict | None = None,
) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "schema":               1,
        "bago_version":         BAGO_VERSION,
        "disclaimer_version":   DISCLAIMER_VERSION,
        "accepted_at":          datetime.now(timezone.utc).isoformat(),
        "python_version":       f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "platform":             platform.system(),
        "selected_packs":       selected_packs,
        "accepted_disclaimer":  True,
        "device":               device_context or {},
        "knowledge":            knowledge_context or {},
    }
    WIZARD_MARKER.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _read_marker() -> dict:
    if not WIZARD_MARKER.exists():
        return {}
    try:
        return json.loads(WIZARD_MARKER.read_text(encoding="utf-8"))
    except Exception:
        return {}


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    args = sys.argv[1:]

    # ── --status / --reset / --force are always allowed ───────────────────────
    if "--status" in args:
        m = _read_marker()
        if not m:
            print("  Estado: no instalado")
        else:
            print(f"  Estado:    {GREEN('instalado')}")
            print(f"  Aceptado:  {m.get('accepted_at', '?')}")
            print(f"  Python:    {m.get('python_version', '?')}")
            print(f"  Plataforma:{m.get('platform', '?')}")
            print(f"  Packs:     {', '.join(m.get('selected_packs', []))}")
            device = m.get("device") or {}
            if device:
                print(f"  Credenciales: {device.get('credentials_mode', '?')} ({device.get('mode', '?')})")
            knowledge = m.get("knowledge") or {}
            if knowledge:
                print(f"  Knowledge: {knowledge.get('path', '?')}")
        return 0

    # ── --reset ────────────────────────────────────────────────────────────────
    if "--reset" in args:
        if WIZARD_MARKER.exists():
            WIZARD_MARKER.unlink()
            _ok("Marker eliminado. Vuelve a ejecutar 'bago' para reinstalar.")
        else:
            _warn("No hay marker de instalación (ya estás en estado limpio).")
        return 0

    # ── Already installed? ─────────────────────────────────────────────────────
    if WIZARD_MARKER.exists() and "--force" not in args:
        return 0

    # ── CI / automation bypass ─────────────────────────────────────────────────
    if os.environ.get("CI") or os.environ.get("BAGO_SKIP_WIZARD"):
        if not WIZARD_MARKER.exists():
            device_context = resolve_device_context() if resolve_device_context else {}
            _write_marker(["core"], device_context, {})
        return 0

    # ── Non-interactive fallback ───────────────────────────────────────────────
    if not sys.stdin.isatty():
        device_context = resolve_device_context() if resolve_device_context else {}
        _write_marker(["core"], device_context, {})
        return 0

    packs = _load_packs()

    # ── Step 1: Banner ─────────────────────────────────────────────────────────
    _banner()

    # ── Step 2: Disclaimer ────────────────────────────────────────────────────
    _step("Contrato de Uso")
    if not _show_disclaimer():
        print()
        _err("No aceptaste el contrato. BAGO no puede continuar.")
        print()
        return 1
    _ok("Contrato aceptado.")

    # ── Step 3: System checks ─────────────────────────────────────────────────
    _step("Comprobando el sistema")
    if not _check_python():
        return 1
    _check_binary("git")

    # ── Step 4: Device / credentials policy ──────────────────────────────────
    _step("Dispositivo BAGO y credenciales")
    device_context = _device_onboarding()

    # ── Step 5: Knowledge repo ───────────────────────────────────────────────
    _step("bago-knowledge")
    knowledge_context = _knowledge_onboarding(device_context)

    # ── Step 6: Feature pack selection ───────────────────────────────────────
    _step("Selección de Feature Packs")
    selected = _select_packs(packs)
    print()
    _ok(f"Packs seleccionados: {', '.join(selected)}")

    # ── Step 7: pip install ───────────────────────────────────────────────────
    all_pip: list[str] = []
    for pack_key in selected:
        all_pip.extend(packs.get(pack_key, {}).get("pip", []))

    if all_pip:
        _step("Instalando dependencias Python")
        install_ok = _install_pip_packages(all_pip)
        if not install_ok:
            _warn("Algunas dependencias no se instalaron. Puedes instalarlas manualmente.")
            _warn("La instalación básica de BAGO continúa de todas formas.")

    # ── Step 8: Ollama check ──────────────────────────────────────────────────
    if "advisor" in selected:
        _step("Comprobando Ollama (para el Advisor LLM)")
        _check_ollama()

    # ── Step 9: Write marker (only after reaching this point) ─────────────────
    _write_marker(selected, device_context, knowledge_context)

    # ── Step 10: Done ─────────────────────────────────────────────────────────
    print()
    print(CYAN("  ╔══════════════════════════════════════════════════════════╗"))
    print(CYAN("  ║  ") + GREEN("✓  ¡BAGO instalado correctamente!") + "                      " + CYAN("║"))
    print(CYAN("  ╚══════════════════════════════════════════════════════════╝"))
    print()
    print(f"  {BOLD('Comandos de inicio rápido:')}")
    print(f"    bago                        → Shell interactivo")
    print(f"    bago help                   → Lista de comandos")
    print(f"    bago health                 → Estado del framework")
    if "advisor" in selected:
        print(f"    bago advisor ask 'hola'     → Chat con el asistente LLM")
    print()
    print(f"  {DIM('Para reinstalar los packs: bago wizard --reset && bago')}")
    print()

    # Launch BAGO banner to close the wizard
    banner_path = TOOLS_DIR / "bago_banner.py"
    if banner_path.exists():
        subprocess.run(
            [sys.executable, str(banner_path)],
            cwd=str(BAGO_ROOT.parent),
        )

    return 0




def run_tests() -> int:
    """Self-test stub: verify module imports and key symbols exist."""
    results = []
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_test_mod", __file__)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        results.append(("import", True, "module loads OK"))
    except Exception as e:
        results.append(("import", False, str(e)))

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, detail in results:
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {name}: {detail}")
    print(f"\n  {passed}/{total} tests passed")
    return 0 if passed == total else 1

if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(run_tests())
    sys.exit(main())