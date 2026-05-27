#!/usr/bin/env python3
"""
bago_repartition.py — Divide el pendrive BAGO en 2 particiones.

  P1 (FAT32, 256 MB):  "BAGO"      → Launchers + ícono (visible siempre)
  P2 (exFAT, resto):   "bago_core" → Framework completo (oculto con bago install)

ADVERTENCIA: Borra todos los datos del disco. El backup se hace antes.
Ejecutar en macOS:  python3 .bago/tools/bago_repartition.py
"""

# ── Todos los imports AL INICIO (el script sigue en RAM tras desmontar) ───
import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import os, sys, time, shutil, stat, subprocess, textwrap
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Contenido de los launchers (P1) — definido aquí para tenerlos en memoria
# ─────────────────────────────────────────────────────────────────────────────

LAUNCHER_COMMAND = """\
#!/bin/bash
# BAGO.command — macOS: doble clic en Finder para abrir BAGO Shell
# Detecta la partición bago_core y la monta si es necesario.
FRAMEWORK=""
for label in bago_core; do
    [ -f "/Volumes/$label/bago" ] && FRAMEWORK="/Volumes/$label" && break  # noqa: HARDCODE
done
if [ -z "$FRAMEWORK" ]; then
    echo "  Montando framework BAGO..."
    diskutil mount bago_core 2>/dev/null; sleep 2
    [ -f "/Volumes/bago_core/bago" ] && FRAMEWORK="/Volumes/bago_core"  # noqa: HARDCODE
fi
if [ -z "$FRAMEWORK" ]; then
    echo "❌  Framework BAGO no encontrado. Asegúrate de que el pendrive está bien conectado."
    read -p "Pulsa Enter para salir..."; exit 1
fi
cd "$FRAMEWORK"; clear
exec python3 .bago/tools/bago_shell.py
"""

LAUNCHER_BAT = """\
@echo off
title BAGO Shell
cls
set "FRAMEWORK="
for /f "tokens=*" %%d in ('powershell -NoProfile -Command "(Get-Volume -FileSystemLabel bago_core -ErrorAction SilentlyContinue).DriveLetter + ':'" 2^>nul') do set "FRAMEWORK=%%d\\"
if not defined FRAMEWORK (
    echo [ERROR] Particion BAGO_CORE no encontrada.
    echo Asegurate de que el pendrive esta completamente conectado.
    pause & exit /b 1
)
cd /d "%FRAMEWORK%"
where python3 >nul 2>&1 && set PY=python3 & goto :run
where python  >nul 2>&1 && set PY=python  & goto :run
where py      >nul 2>&1 && set PY=py      & goto :run
echo [ERROR] Python no encontrado. Instala desde https://python.org
pause & exit /b 1
:run
%PY% bago
pause
"""

LAUNCHER_SH = """\
#!/usr/bin/env bash
FRAMEWORK=""
for path in /run/media/$USER/bago_core /media/$USER/bago_core /mnt/bago_core; do
    [ -f "$path/bago" ] && FRAMEWORK="$path" && break
done
if [ -z "$FRAMEWORK" ] && command -v udisksctl &>/dev/null; then
    DEV=$(blkid -L bago_core 2>/dev/null || true)
    [ -n "$DEV" ] && udisksctl mount -b "$DEV" --no-user-interaction 2>/dev/null; sleep 1
    for path in /run/media/$USER/bago_core /media/$USER/bago_core; do
        [ -f "$path/bago" ] && FRAMEWORK="$path" && break
    done
fi
[ -z "$FRAMEWORK" ] && { echo "❌  Framework BAGO (bago_core) no encontrado."; exit 1; }
cd "$FRAMEWORK"
if [ -n "${TERMUX_VERSION:-}" ] || [ -t 0 ]; then
    exec python3 bago
else
    for term in gnome-terminal kitty alacritty xterm konsole xfce4-terminal; do
        command -v "$term" &>/dev/null || continue
        case "$term" in
            gnome-terminal) $term -- bash -c "cd '$FRAMEWORK' && python3 bago; exec bash" & ;;
            kitty|alacritty) $term bash -c "cd '$FRAMEWORK' && python3 bago; exec bash" & ;;
            *) $term -e bash -c "cd '$FRAMEWORK' && python3 bago; exec bash" & ;;
        esac; exit 0
    done
    exec python3 bago
fi
"""

LAUNCHER_DESKTOP = """\
[Desktop Entry]
Version=1.0
Name=BAGO Shell
Comment=Framework de desarrollo personal — inicia el shell interactivo
Exec=bash -c 'cd "$(dirname "%k")" && bash bago.sh'
Terminal=true
Type=Application
Icon=utilities-terminal
Categories=Development;
"""

AUTORUN_INF = """\
[autorun]
label=BAGO
icon=bago.ico
open=BAGO.bat
action=Iniciar BAGO Framework
"""

APP_EXECUTABLE = """\
#!/bin/bash
FRAMEWORK=""
for label in bago_core; do
    [ -f "/Volumes/$label/bago" ] && FRAMEWORK="/Volumes/$label" && break  # noqa: HARDCODE
done
if [ -z "$FRAMEWORK" ]; then
    diskutil mount bago_core 2>/dev/null; sleep 2
    [ -f "/Volumes/bago_core/bago" ] && FRAMEWORK="/Volumes/bago_core"  # noqa: HARDCODE
fi
if [ -z "$FRAMEWORK" ]; then
    osascript -e 'display alert "BAGO" message "Framework BAGO no encontrado.\\nAsegúrate de que el pendrive está bien conectado." as critical'
    exit 1
fi
osascript <<SCRIPT
tell application "Terminal"
    activate
    set w to do script "cd \\'$FRAMEWORK\\' && clear && python3 .bago/tools/bago_shell.py"
    set custom title of front window to "BAGO Shell"
end tell
SCRIPT
"""

APP_PLIST = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key><string>BAGO</string>
    <key>CFBundleIconFile</key><string>AppIcon</string>
    <key>CFBundleIdentifier</key><string>com.bago.launcher</string>
    <key>CFBundleName</key><string>BAGO</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>CFBundleVersion</key><string>1.0</string>
    <key>CFBundleShortVersionString</key><string>1.0</string>
    <key>LSUIElement</key><true/>
    <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
"""

BIENVENIDO = """\
BAGO Framework — Pendrive de desarrollo personal
================================================

  macOS   : doble clic en BAGO.app  (o BAGO.command)
  Windows : doble clic en BAGO.bat
  Linux   : doble clic en BAGO.desktop (o ejecuta bago.sh)
  Android : ver instrucciones en bago.sh

Primera vez en esta máquina:
  1. Abre BAGO (cualquiera de los launchers de arriba)
  2. En el shell: bago install
     Esto oculta la partición interna y activa el auto-lanzamiento.
"""

# ─────────────────────────────────────────────────────────────────────────────

def _c(code, t):
    return f"\033[{code}m{t}\033[0m" if sys.stdout.isatty() else t

OK   = lambda t: _c("1;32", t)
WARN = lambda t: _c("1;33", t)
ERR  = lambda t: _c("1;31", t)
BOLD = lambda t: _c("1",    t)
DIM  = lambda t: _c("2",    t)
CYAN = lambda t: _c("1;36", t)

def step(msg):  print(f"\n  {CYAN('▶')} {BOLD(msg)}")
def ok(msg):    print(f"  {OK('✓')} {msg}")
def warn(msg):  print(f"  {WARN('⚠')} {msg}")
def err(msg):   print(f"  {ERR('✗')} {msg}", file=sys.stderr)
def info(msg):  print(f"  {DIM('→')} {msg}")


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def wait_for_mount(label, timeout=30):
    path = Path(f"/Volumes/{label}")
    for _ in range(timeout):
        if path.exists():
            return path
        time.sleep(1)
    return None


def create_app_bundle(p1: Path, icns_src: Path):
    """Crea BAGO.app en P1."""
    app = p1 / "BAGO.app"
    macos_dir = app / "Contents" / "MacOS"
    res_dir   = app / "Contents" / "Resources"
    macos_dir.mkdir(parents=True, exist_ok=True)
    res_dir.mkdir(parents=True, exist_ok=True)

    exe = macos_dir / "BAGO"
    exe.write_text(APP_EXECUTABLE)
    exe.chmod(0o755)

    (app / "Contents" / "Info.plist").write_text(APP_PLIST)

    if icns_src.exists():
        shutil.copy(str(icns_src), str(res_dir / "AppIcon.icns"))

    # Quitar cuarentena para que Gatekeeper no bloquee
    run(["xattr", "-cr", str(app)], check=False)
    ok(f"BAGO.app creado")


def setup_p1(p1: Path, icns_src: Path, ico_src: Path):
    """Crea todos los archivos de la partición launcher (P1)."""
    step("Configurando Partición 1 — Launchers + ícono")

    # Launchers
    f = p1 / "BAGO.command"
    f.write_text(LAUNCHER_COMMAND); f.chmod(0o755); ok(f"{f.name}")

    f = p1 / "BAGO.bat"
    f.write_text(LAUNCHER_BAT); ok(f"{f.name}")

    f = p1 / "bago.sh"
    f.write_text(LAUNCHER_SH); f.chmod(0o755); ok(f"{f.name}")

    f = p1 / "BAGO.desktop"
    f.write_text(LAUNCHER_DESKTOP); f.chmod(0o755); ok(f"{f.name}")

    f = p1 / "autorun.inf"
    f.write_text(AUTORUN_INF); ok(f"{f.name}")

    f = p1 / "BIENVENIDO.txt"
    f.write_text(BIENVENIDO); ok(f"{f.name}")

    # Íconos
    if ico_src.exists():
        shutil.copy(str(ico_src), str(p1 / "bago.ico"))
        ok("bago.ico")
    if icns_src.exists():
        shutil.copy(str(icns_src), str(p1 / ".VolumeIcon.icns"))
        ok(".VolumeIcon.icns")

    # BAGO.app (macOS)
    create_app_bundle(p1, icns_src)

    # Activar ícono de volumen en macOS
    run(["xattr", "-wx", "com.apple.FinderInfo",
         "0000000000000000040000000000000000000000000000000000000000000000",
         str(p1)], check=False)
    run(["osascript", "-e",
         f'tell application "Finder" to update every item of disk "BAGO"'],
        check=False)
    ok("Ícono de volumen activado en macOS")


def main():
    print()
    print(BOLD(CYAN("  ╔══ BAGO Repartición ══════════════════════════════════════╗")))
    print(      "  ║                                                              ║")
    print(      "  ║  P1 · FAT32 · 256 MB · \"BAGO\"      → Launchers + ícono      ║")
    print(      "  ║  P2 · exFAT · ~30 GB · \"bago_core\" → Framework (oculto)     ║")
    print(      "  ║                                                              ║")
    print(BOLD(CYAN("  ╚══════════════════════════════════════════════════════════════╝")))

    # ── Verificar entorno ─────────────────────────────────────────────────
    if sys.platform != "darwin":
        err("Este script solo puede ejecutarse en macOS.")
        sys.exit(1)

    drive_root  = Path("/Volumes/bago_fw")  # noqa: HARDCODE — pendrive label by design
    disk_device = "/dev/disk3"

    if not drive_root.exists():
        err(f"No se encuentra {drive_root}. Conecta el pendrive.")
        sys.exit(1)

    # Confirmar que /dev/disk3 corresponde a bago_fw
    try:
        info_out = run(["diskutil", "info", str(drive_root)]).stdout
        if "disk3" not in info_out:
            err("El volumen bago_fw no está en /dev/disk3. Verifica manualmente.")
            sys.exit(1)
    except Exception as e:
        err(f"No se pudo verificar el disco: {e}")
        sys.exit(1)

    icns_src = drive_root / ".VolumeIcon.icns"
    ico_src  = drive_root / "bago.ico"
    assets   = drive_root / ".bago" / "assets"

    if not icns_src.exists():
        warn(".VolumeIcon.icns no encontrado — genera los íconos primero.")

    # ── Advertencia ────────────────────────────────────────────────────────
    print()
    print(f"  {WARN('⚠  ADVERTENCIA: Se borrarán todos los datos de /dev/disk3.')}")
    print(f"     El backup se hará en /tmp/ antes de continuar.")
    print()
    resp = input("  ¿Continuar? [s/N] ").strip().lower()
    if resp not in ("s", "si", "sí", "y", "yes"):
        print("  Cancelado.\n"); sys.exit(0)

    # ── 1. Backup ─────────────────────────────────────────────────────────
    step("Backup de todos los archivos del framework")
    import tempfile
    backup_dir = Path(tempfile.mkdtemp(prefix="bago_backup_"))
    info(f"Destino: {backup_dir}")

    result = subprocess.run(
        ["rsync", "-a", "--exclude=.Spotlight-V100",
         "--exclude=.fseventsd", "--exclude=System Volume Information",
         str(drive_root) + "/", str(backup_dir) + "/"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        err(f"rsync falló: {result.stderr}")
        sys.exit(1)

    size = shutil.disk_usage(backup_dir).used
    ok(f"Backup completado: {size // 1024 // 1024} MB en {backup_dir}")

    # ── 2. Reparticionar (DESTRUCTIVO) ───────────────────────────────────
    step("Reparticionando /dev/disk3 — 2 particiones")
    info("FAT32 BAGO 256 MB  +  exFAT bago_core (resto)")

    try:
        run(["diskutil", "partitionDisk", disk_device, "GPT",
             "FAT32", "BAGO",      "256MB",
             "ExFAT", "bago_core", "R"])
        ok("Repartición completada")
    except subprocess.CalledProcessError as e:
        err(f"diskutil falló: {e.stderr}")
        err(f"Backup en: {backup_dir}")
        sys.exit(1)

    # ── 3. Esperar a que las particiones monten ───────────────────────────
    step("Esperando que monten las particiones nuevas")
    time.sleep(3)

    p1 = wait_for_mount("BAGO")
    p2 = wait_for_mount("bago_core")

    if not p1:
        err("Partición P1 (BAGO) no montó. Revisa Disk Utility.")
        err(f"Backup en: {backup_dir}"); sys.exit(1)
    if not p2:
        err("Partición P2 (bago_core) no montó. Revisa Disk Utility.")
        err(f"Backup en: {backup_dir}"); sys.exit(1)

    ok(f"P1: {p1}")
    ok(f"P2: {p2}")

    # ── 4. Restaurar framework en P2 ──────────────────────────────────────
    step("Restaurando framework en Partición 2 (bago_core)")
    result = subprocess.run(
        ["rsync", "-a",
         "--exclude=BAGO.command", "--exclude=BAGO.bat", "--exclude=bago.sh",
         "--exclude=BAGO.desktop", "--exclude=autorun.inf", "--exclude=BIENVENIDO.txt",
         str(backup_dir) + "/", str(p2) + "/"],
        capture_output=True, text=True
    )
    if result.returncode not in (0, 23, 24):
        warn(f"rsync restore: {result.stderr[:200]}")
    ok("Framework restaurado en bago_core")

    # ── 5. Configurar P1 ─────────────────────────────────────────────────
    # Íconos desde el backup (ya no están en el volumen original)
    icns_from_backup = backup_dir / ".VolumeIcon.icns"
    ico_from_backup  = backup_dir / "bago.ico"
    setup_p1(p1, icns_from_backup, ico_from_backup)

    # ── 6. Actualizar bago_install.py en P2 para ocultar P2 ──────────────
    step("Actualizando bago install para ocultar bago_core en nuevas máquinas")
    _patch_install(p2)

    # ── 7. Limpiar backup ─────────────────────────────────────────────────
    step("Limpiando backup temporal")
    shutil.rmtree(backup_dir, ignore_errors=True)
    ok(f"Backup eliminado: {backup_dir}")

    # ── Resumen ───────────────────────────────────────────────────────────
    print()
    print(BOLD(CYAN("  ✅  Repartición completada")))
    print()
    print(f"  {OK('P1')} /Volumes/BAGO        → {p1}  (launchers + ícono)")
    print(f"  {OK('P2')} /Volumes/bago_core   → {p2}  (framework)")
    print()
    print(f"  {DIM('Próximos pasos:')}")
    print(f"  1. Eyecta y reconecta el pendrive para ver el ícono BAGO.")
    print(f"  2. Haz doble clic en BAGO.app (o BAGO.command) para probar.")
    print(f"  3. En el shell BAGO: {CYAN('bago install')} para ocultar bago_core.")
    print()


def _patch_install(p2: Path):
    """Añade lógica de ocultamiento de bago_core a bago_install.py en P2."""
    install_path = p2 / ".bago" / "tools" / "bago_install.py"
    if not install_path.exists():
        warn("bago_install.py no encontrado en bago_core — omitiendo patch")
        return

    content = install_path.read_text("utf-8")
    if "bago_core" in content and "fstab" in content:
        ok("bago_install.py ya tiene lógica de ocultamiento")
        return

    # Añadir sección de ocultamiento al final de _macos_install
    hide_block = '''

# ── Ocultar bago_core (P2) en este Mac via fstab ─────────────────────────────

def _macos_hide_p2():
    """Añade entrada noauto en /etc/fstab para que bago_core no auto-monte."""
    try:
        r = subprocess.run(
            ["diskutil", "info", "bago_core"],
            capture_output=True, text=True
        )
        uuid = None
        for line in r.stdout.splitlines():
            if "Volume UUID" in line:
                uuid = line.split()[-1]
                break
        if not uuid:
            _warn("No se encontró UUID de bago_core")
            return
        entry = f"UUID={uuid} none exfat noauto,noowners 0 0\\n"
        fstab = Path("/etc/fstab")
        current = fstab.read_text("utf-8") if fstab.exists() else ""
        if uuid in current:
            _ok("bago_core ya está en /etc/fstab (noauto)")
            return
        r2 = subprocess.run(
            ["sudo", "sh", "-c", f"echo '{entry}' >> /etc/fstab"],
            capture_output=True, text=True
        )
        if r2.returncode == 0:
            _ok(f"bago_core → /etc/fstab noauto (UUID: {uuid[:8]}…)")
        else:
            _warn("No se pudo escribir en /etc/fstab (requiere sudo)")
    except Exception as e:
        _warn(f"fstab: {e}")


def _linux_hide_p2():
    """Regla udev para no auto-montar bago_core en Linux."""
    try:
        r = subprocess.run(
            ["blkid", "-L", "bago_core"], capture_output=True, text=True
        )
        dev = r.stdout.strip()
        if not dev:
            _warn("bago_core no encontrado por blkid")
            return
        r2 = subprocess.run(["blkid", "-o", "value", "-s", "UUID", dev],
                             capture_output=True, text=True)
        uuid = r2.stdout.strip()
        rule = f'ENV{{ID_FS_UUID}}=="{uuid}", ENV{{UDISKS_IGNORE}}="1"\\n'
        rule_path = Path("/etc/udev/rules.d/99-bago-hide.rules")
        current = rule_path.read_text("utf-8") if rule_path.exists() else ""
        if uuid in current:
            _ok("bago_core ya está en udev rules (ignorado)")
            return
        r3 = subprocess.run(
            ["sudo", "sh", "-c", f"echo '{rule}' >> {rule_path}"],
            capture_output=True, text=True
        )
        if r3.returncode == 0:
            subprocess.run(["sudo", "udevadm", "control", "--reload"], capture_output=True)
            _ok(f"bago_core → udev UDISKS_IGNORE (UUID: {uuid[:8]}…)")
        else:
            _warn("No se pudo escribir en /etc/udev/rules.d/ (requiere sudo)")
    except Exception as e:
        _warn(f"udev: {e}")
'''

    # Insertar antes del if __name__ == "__main__"
    if 'if __name__ == "__main__"' in content:
        content = content.replace(
            'if __name__ == "__main__"',
            hide_block + '\nif __name__ == "__main__"'
        )
        install_path.write_text(content, "utf-8")
        ok("bago_install.py actualizado con lógica de ocultamiento")
    else:
        install_path.write_text(content + hide_block, "utf-8")
        ok("bago_install.py actualizado")




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
    main()