#!/usr/bin/env python3
"""
bago install — configura auto-lanzamiento de BAGO al insertar el pendrive.

Plataformas soportadas:
  macOS   — LaunchAgent com.bago.autolaunch  (launchd WatchPaths + debounce)
  Linux   — systemd user path unit            (sin necesitar root)
  Windows — entrada en Startup (monitoreo en background via PowerShell)
  Android — instrucciones para Termux ~/.bashrc
  iPad    — instrucciones para a-Shell / Shortcuts

Uso:
  bago install            # instala auto-lanzamiento en este sistema
  bago install --remove   # elimina la instalación
  bago install --status   # muestra estado actual
"""

import os
import platform
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

BAGO_ROOT  = Path(__file__).resolve().parent.parent
DRIVE_ROOT = BAGO_ROOT.parent
VOLUME_LABEL = DRIVE_ROOT.name          # "bago_fw"
BAGO_BIN   = DRIVE_ROOT / "bago"

# ─── Colores ──────────────────────────────────────────────────────────────────

def _c(code: str, t: str) -> str:
    if sys.platform == "win32" or not sys.stdout.isatty():
        return t
    return f"\033[{code}m{t}\033[0m"

OK    = lambda t: _c("1;32", t)
WARN  = lambda t: _c("1;33", t)
ERR   = lambda t: _c("1;31", t)
DIM   = lambda t: _c("2",    t)
BOLD  = lambda t: _c("1",    t)
CYAN  = lambda t: _c("1;36", t)

def _ok(msg):   print(f"  {OK('✓')} {msg}")
def _warn(msg): print(f"  {WARN('⚠')} {msg}")
def _err(msg):  print(f"  {ERR('✗')} {msg}")
def _info(msg): print(f"  {DIM('→')} {msg}")


# ─── macOS ────────────────────────────────────────────────────────────────────

_MACOS_SCRIPT_DIR  = Path.home() / "Library" / "Scripts"
_MACOS_AGENT_DIR   = Path.home() / "Library" / "LaunchAgents"
_MACOS_SCRIPT_PATH = _MACOS_SCRIPT_DIR / "bago_autolaunch.sh"
_MACOS_PLIST_PATH  = _MACOS_AGENT_DIR  / "com.bago.autolaunch.plist"
_MACOS_LOCK_PATH   = Path.home() / ".bago_last_launch"

_MACOS_SCRIPT = """\
#!/bin/bash
# bago_autolaunch.sh — lanzado por launchd cuando se monta el pendrive BAGO
# Incluye debounce (30s) y protección contra doble apertura.

DRIVE="/Volumes/{label}"  # noqa: HARDCODE
LOG="$HOME/Library/Logs/BAGO/autolaunch.log"
LOCK="$HOME/.bago_last_launch"
mkdir -p "$(dirname "$LOG")"

# Debounce: ignorar si se disparó hace menos de 30s
NOW=$(date +%s)
if [ -f "$LOCK" ]; then
    LAST=$(cat "$LOCK" 2>/dev/null || echo 0)
    [ $((NOW - LAST)) -lt 30 ] && exit 0
fi
echo "$NOW" > "$LOCK"

# Verificar que el pendrive está montado y tiene bago_shell.py
if [ ! -f "$DRIVE/.bago/tools/bago_shell.py" ]; then
    echo "[$(date)] Drive no listo: $DRIVE" >> "$LOG"
    exit 0
fi

# No abrir si ya hay una sesión BAGO activa
if pgrep -f "bago_shell.py" > /dev/null 2>&1; then
    echo "[$(date)] Shell ya activo, ignorando." >> "$LOG"
    exit 0
fi

echo "[$(date)] Abriendo BAGO Shell" >> "$LOG"

# Preferir iTerm2 si está instalado
if [ -d "/Applications/iTerm.app" ]; then
    osascript <<'OSASCRIPT'
tell application "iTerm"
    activate
    create window with default profile command "cd /Volumes/{label} && python3 .bago/tools/bago_shell.py"
end tell
OSASCRIPT
else
    # Terminal.app — abre una nueva ventana
    osascript <<'OSASCRIPT'
tell application "Terminal"
    activate
    do script "cd /Volumes/{label} && python3 .bago/tools/bago_shell.py"
    set custom title of front window to "BAGO Shell"
end tell
OSASCRIPT
fi
"""

_MACOS_PLIST = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.bago.autolaunch</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>{script}</string>
    </array>
    <key>WatchPaths</key>
    <array>
        <string>/Volumes/{label}</string>
    </array>
    <key>RunAtLoad</key>
    <false/>
    <key>StandardOutPath</key>
    <string>{home}/Library/Logs/BAGO/autolaunch.log</string>
    <key>StandardErrorPath</key>
    <string>{home}/Library/Logs/BAGO/autolaunch.err</string>
</dict>
</plist>
"""


def _macos_install() -> bool:
    _MACOS_SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    _MACOS_AGENT_DIR.mkdir(parents=True, exist_ok=True)
    (Path.home() / "Library" / "Logs" / "BAGO").mkdir(parents=True, exist_ok=True)

    # Escribir script de lanzamiento
    _MACOS_SCRIPT_PATH.write_text(
        _MACOS_SCRIPT.format(label=VOLUME_LABEL), encoding="utf-8"
    )
    _MACOS_SCRIPT_PATH.chmod(0o755)
    _ok(f"Script: {_MACOS_SCRIPT_PATH}")

    # Escribir plist
    _MACOS_PLIST_PATH.write_text(
        _MACOS_PLIST.format(
            script=str(_MACOS_SCRIPT_PATH),
            label=VOLUME_LABEL,
            home=str(Path.home()),
        ),
        encoding="utf-8",
    )
    _ok(f"LaunchAgent: {_MACOS_PLIST_PATH}")

    # Descargar plist previo si existe, luego cargar
    uid = os.getuid()
    target = f"gui/{uid}"
    subprocess.run(
        ["launchctl", "bootout", target, str(_MACOS_PLIST_PATH)],
        capture_output=True,
    )
    r = subprocess.run(
        ["launchctl", "bootstrap", target, str(_MACOS_PLIST_PATH)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        _warn(f"launchctl bootstrap: {r.stderr.strip() or 'posible error de permisos'}")
        _info("Intenta: bago install  (en una sesión de usuario completa, no remota)")
    else:
        _ok("LaunchAgent activado — el shell se abrirá al conectar el pendrive")

    return True


def _macos_remove() -> bool:
    uid = os.getuid()
    target = f"gui/{uid}"
    subprocess.run(
        ["launchctl", "bootout", target, str(_MACOS_PLIST_PATH)],
        capture_output=True,
    )
    for p in [_MACOS_PLIST_PATH, _MACOS_SCRIPT_PATH, _MACOS_LOCK_PATH]:
        if p.exists():
            p.unlink()
            _ok(f"Eliminado: {p}")
    return True


def _macos_status() -> str:
    installed = _MACOS_PLIST_PATH.exists() and _MACOS_SCRIPT_PATH.exists()
    return "instalado" if installed else "no instalado"


# ─── Linux ────────────────────────────────────────────────────────────────────

_LINUX_BIN_DIR      = Path.home() / ".local" / "bin"
_LINUX_SCRIPT_PATH  = _LINUX_BIN_DIR / "bago_autolaunch.sh"
_LINUX_SYSTEMD_DIR  = Path.home() / ".config" / "systemd" / "user"
_LINUX_PATH_UNIT    = _LINUX_SYSTEMD_DIR / "bago-watch.path"
_LINUX_SVC_UNIT     = _LINUX_SYSTEMD_DIR / "bago-watch.service"

# Posibles puntos de montaje según distro
_LINUX_MOUNT_PATHS = [
    f"/run/media/$USER/{VOLUME_LABEL}",   # GNOME/KDE moderno (udisks2)
    f"/media/$USER/{VOLUME_LABEL}",       # Ubuntu legacy
    f"/mnt/{VOLUME_LABEL}",              # sistemas mínimos
]

_LINUX_SCRIPT = """\
#!/bin/bash
# bago_autolaunch.sh — lanzado por systemd cuando se monta el pendrive BAGO

DRIVE=""
for mp in {mounts}; do
    eval _mp="$mp"
    if [ -f "$_mp/.bago/tools/bago_shell.py" ]; then
        DRIVE="$_mp"
        break
    fi
done

[ -z "$DRIVE" ] && exit 0

# No abrir si ya hay sesión activa
pgrep -f "bago_shell.py" > /dev/null 2>&1 && exit 0

# Abrir en el mejor emulador disponible
for term in gnome-terminal kitty alacritty xterm konsole xfce4-terminal; do
    if command -v "$term" &>/dev/null; then
        CMD="bash -c 'cd \\"$DRIVE\\" && python3 .bago/tools/bago_shell.py; exec bash'"
        case "$term" in
            gnome-terminal) $term -- bash -c "cd '$DRIVE' && python3 .bago/tools/bago_shell.py; exec bash" &
                            ;;
            kitty|alacritty) $term bash -c "cd '$DRIVE' && python3 .bago/tools/bago_shell.py; exec bash" &
                             ;;
            *)               $term -e bash -c "cd '$DRIVE' && python3 .bago/tools/bago_shell.py; exec bash" &
                             ;;
        esac
        exit 0
    fi
done
"""

_LINUX_PATH_TPL = """\
[Unit]
Description=Detectar pendrive BAGO

[Path]
{path_exists}

[Install]
WantedBy=default.target
"""

_LINUX_SVC_TPL = """\
[Unit]
Description=Abrir BAGO Shell al insertar pendrive

[Service]
Type=oneshot
ExecStart={script}
"""


def _linux_install() -> bool:
    _LINUX_BIN_DIR.mkdir(parents=True, exist_ok=True)
    _LINUX_SYSTEMD_DIR.mkdir(parents=True, exist_ok=True)

    mounts = " ".join(f'"{m}"' for m in _LINUX_MOUNT_PATHS)
    _LINUX_SCRIPT_PATH.write_text(
        _LINUX_SCRIPT.format(mounts=mounts), encoding="utf-8"
    )
    _LINUX_SCRIPT_PATH.chmod(0o755)
    _ok(f"Script: {_LINUX_SCRIPT_PATH}")

    path_exists_lines = "\n".join(
        f"PathExists={m}" for m in _LINUX_MOUNT_PATHS
    )
    _LINUX_PATH_UNIT.write_text(
        _LINUX_PATH_TPL.format(path_exists=path_exists_lines), encoding="utf-8"
    )
    _ok(f"Path unit: {_LINUX_PATH_UNIT}")

    _LINUX_SVC_UNIT.write_text(
        _LINUX_SVC_TPL.format(script=str(_LINUX_SCRIPT_PATH)), encoding="utf-8"
    )
    _ok(f"Service unit: {_LINUX_SVC_UNIT}")

    r = subprocess.run(
        ["systemctl", "--user", "daemon-reload"], capture_output=True, text=True
    )
    if r.returncode != 0:
        _warn("daemon-reload falló — systemd user session puede no estar disponible")
    else:
        subprocess.run(
            ["systemctl", "--user", "enable", "--now", "bago-watch.path"],
            capture_output=True,
        )
        _ok("systemd user path unit activado")

    return True


def _linux_remove() -> bool:
    subprocess.run(
        ["systemctl", "--user", "disable", "--now", "bago-watch.path"],
        capture_output=True,
    )
    for p in [_LINUX_PATH_UNIT, _LINUX_SVC_UNIT, _LINUX_SCRIPT_PATH]:
        if p.exists():
            p.unlink()
            _ok(f"Eliminado: {p}")
    subprocess.run(
        ["systemctl", "--user", "daemon-reload"], capture_output=True
    )
    return True


def _linux_status() -> str:
    return "instalado" if _LINUX_PATH_UNIT.exists() else "no instalado"


# ─── Windows ──────────────────────────────────────────────────────────────────

def _win_script_dir() -> Path:
    base = os.environ.get("APPDATA", str(Path.home()))
    return Path(base) / "BAGO"


_WIN_SCRIPT_NAME = "bago_monitor.ps1"
_WIN_RUN_KEY     = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
_WIN_RUN_NAME    = "BAGOFramework"

_WIN_PS1 = r"""
# bago_monitor.ps1 — monitorea el pendrive BAGO en background (Windows Startup)
$label = "{label}"
$alreadyOpen = $false

while ($true) {{
    $vol = Get-WmiObject -Class Win32_Volume | Where-Object {{ $_.Label -eq $label }}
    if ($vol) {{
        $drive = $vol[0].DriveLetter
        if (-not $alreadyOpen) {{
            # Verificar que existe el shell
            if (Test-Path "$drive\.bago\tools\bago_shell.py") {{
                # Detectar Python
                $py = @("python3","python","py") | Where-Object {{ Get-Command $_ -ErrorAction SilentlyContinue }} | Select-Object -First 1  # noqa: HARDCODE
                if ($py) {{
                    Start-Process -FilePath "cmd.exe" -ArgumentList "/K title BAGO Shell && cd /d $drive && $py bago"
                }}
            }}
            $alreadyOpen = $true
        }}
        Start-Sleep -Seconds 30
    }} else {{
        $alreadyOpen = $false
        Start-Sleep -Seconds 5
    }}
}}
"""


def _win_install() -> bool:
    import winreg

    script_dir  = _win_script_dir()
    script_dir.mkdir(parents=True, exist_ok=True)
    script_path = script_dir / _WIN_SCRIPT_NAME
    script_path.write_text(
        _WIN_PS1.format(label=VOLUME_LABEL), encoding="utf-8"
    )
    _ok(f"Script: {script_path}")

    ps_cmd = (
        f'powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass '
        f'-File "{script_path}"'
    )
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _WIN_RUN_KEY, 0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, _WIN_RUN_NAME, 0, winreg.REG_SZ, ps_cmd)
        winreg.CloseKey(key)
        _ok(f"Registro Startup: {_WIN_RUN_NAME}")
        _info("El monitor se activará en el próximo inicio de sesión de Windows")
        _info("Para activarlo ahora: ejecuta bago_monitor.ps1 manualmente")
    except Exception as e:
        _warn(f"No se pudo escribir en el registro: {e}")

    return True


def _win_remove() -> bool:
    import winreg

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _WIN_RUN_KEY, 0, winreg.KEY_SET_VALUE
        )
        winreg.DeleteValue(key, _WIN_RUN_NAME)
        winreg.CloseKey(key)
        _ok(f"Registro Startup eliminado: {_WIN_RUN_NAME}")
    except FileNotFoundError:
        pass
    except Exception as e:
        _warn(f"Registro: {e}")

    script_path = _win_script_dir() / _WIN_SCRIPT_NAME
    if script_path.exists():
        script_path.unlink()
        _ok(f"Eliminado: {script_path}")

    return True


def _win_status() -> str:
    script_path = _win_script_dir() / _WIN_SCRIPT_NAME
    return "instalado" if script_path.exists() else "no instalado"


# ─── Android / iPad — solo instrucciones ─────────────────────────────────────

_ANDROID_HELP = """
  Android (Termux)
  ─────────────────────────────────────────────────────────────────
  1. Instala Termux desde F-Droid o Google Play.
  2. Conecta el pendrive por USB OTG.
  3. En Termux: termux-setup-storage
  4. El pendrive aparece en /storage/<ID>/
     Busca el path con: ls /storage/*/bago
  5. Añade al final de ~/.bashrc:

       for _bago in /storage/*/bago; do
           [ -f "$_bago" ] && alias bago="$_bago" && break
       done

  6. Ahora escribe bago en cualquier sesión Termux.
"""

_IPAD_HELP = """
  iPad (iPadOS 13+)
  ─────────────────────────────────────────────────────────────────
  1. Instala a-Shell (gratis, App Store) — interprete Python real.
  2. Conecta el pendrive. Aparece en la app Archivos.
  3. En a-Shell:
       pickFolder        # selecciona la raíz del pendrive
       python3 bago
  4. Atajo rápido (Shortcuts.app):
       Nueva acción → "Ejecutar script a-Shell" →
       script: "python3 bago"
     Agrega el atajo al Dock o como widget para acceso directo.
"""


# ─── CLI principal ────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    args   = argv or sys.argv[1:]
    remove = "--remove" in args or "--uninstall" in args
    status = "--status" in args

    plat = platform.system()

    print()
    print(BOLD(CYAN("  ╔══ BAGO Install ══════════════════════════════════╗")))
    print(f"  ║  Pendrive: {VOLUME_LABEL}   Sistema: {plat}")
    print(BOLD(CYAN("  ╚════════════════════════════════════════════════════╝")))
    print()

    if status:
        if plat == "Darwin":
            print(f"  macOS LaunchAgent: {_macos_status()}")
        elif plat == "Linux":
            print(f"  Linux systemd:     {_linux_status()}")
        elif plat == "Windows":
            print(f"  Windows Startup:   {_win_status()}")
        print()
        return 0

    if plat == "Darwin":
        print(f"  {BOLD('macOS')} — LaunchAgent (auto-lanzamiento al insertar el pendrive)\n")
        if remove:
            _macos_remove()
            print(f"\n  {OK('Auto-lanzamiento desactivado.')}\n")
        else:
            _macos_install()
            print()
            _info("Eyecta y vuelve a conectar el pendrive para probar.")

    elif plat == "Linux":
        print(f"  {BOLD('Linux')} — systemd user path unit (sin necesitar root)\n")
        if remove:
            _linux_remove()
            print(f"\n  {OK('Auto-lanzamiento desactivado.')}\n")
        else:
            _linux_install()
            print()
            _info("Reconecta el pendrive para probar.")

    elif plat == "Windows":
        print(f"  {BOLD('Windows')} — Script de monitoreo en Startup\n")
        if remove:
            _win_remove()
            print(f"\n  {OK('Auto-lanzamiento desactivado.')}\n")
        else:
            _win_install()

    else:
        # Android, iPad, otros
        print(f"  Sistema {plat} — sin auto-instalación automática.\n")
        print(_ANDROID_HELP)
        print(_IPAD_HELP)

    if not remove and plat in ("Darwin", "Linux", "Windows"):
        print()
        print(f"  {DIM('Launcher de doble clic disponible en la raíz del pendrive:')}")
        if plat == "Darwin":
            _info("BAGO.command  — doble clic en Finder")
        elif plat == "Linux":
            _info("bago.sh       — doble clic en gestor de archivos")
        elif plat == "Windows":
            _info("BAGO.bat      — doble clic en Explorador")
        print()
        print(f"  {DIM('Para desinstalar:')} bago install --remove")

    print()
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        print("bago_install --test: PASS (platform detection loadable)")
        raise SystemExit(0)
    sys.exit(main())
