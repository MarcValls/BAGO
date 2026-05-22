"""bago_core.installer — Instalacion remota de BAGO desde GitHub releases.

Uso:
    bago install                → instala la ultima version
    bago install --version 3.4.5 → instala version especifica
    bago install --upgrade      → actualiza a la ultima version
    bago install --list         → lista releases disponibles
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.request import urlopen, Request

# ── Config ────────────────────────────────────────────────────────────────────
REPO = "MarcValls/BAGO"
API_RELEASES = f"https://api.github.com/repos/{REPO}/releases"
DEFAULT_INSTALL_DIR = Path.home() / ".bago"
VERSIONS_DIR = DEFAULT_INSTALL_DIR / "versions"
ACTIVE_DIR = DEFAULT_INSTALL_DIR / "active"
ACTIVE_MARKER = DEFAULT_INSTALL_DIR / "active_version.txt"

# ── Helpers ─────────────────────────────────────────────────────────────────

def _github_api(url: str) -> dict | list:
    req = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "bago-installer"})
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_releases(limit: int = 10) -> list[dict]:
    try:
        data = _github_api(f"{API_RELEASES}?per_page={limit}")
        return [
            {
                "tag": r["tag_name"],
                "name": r["name"],
                "published": r["published_at"],
                "assets": [
                    {"name": a["name"], "url": a["browser_download_url"], "size": a["size"]}
                    for a in r.get("assets", [])
                ],
            }
            for r in data
            if not r.get("draft")
        ]
    except Exception as exc:
        print(f"[ERROR] No se pudieron listar releases: {exc}", file=sys.stderr)
        return []


def _find_zip_asset(release: dict) -> dict | None:
    for a in release["assets"]:
        if a["name"].endswith(".zip") and "install" not in a["name"]:
            return a
    return None


def _download(url: str, dest: Path, label: str = "Descargando") -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  [{label}] {url}")
    try:
        req = Request(url, headers={"User-Agent": "bago-installer"})
        with urlopen(req, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            chunk_size = 65536
            downloaded = 0
            with open(dest, "wb") as fh:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    fh.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded * 100 // total
                        print(f"\r  {pct}%  ({downloaded//1024} KB / {total//1024} KB)", end="", flush=True)
            print()  # newline
            return True
    except Exception as exc:
        print(f"\n[ERROR] Descarga fallida: {exc}", file=sys.stderr)
        return False


def _extract(zip_path: Path, dest: Path) -> Path | None:
    dest.mkdir(parents=True, exist_ok=True)
    print(f"  [Extrayendo] {zip_path.name} → {dest}")
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(dest)
        # Find actual root (ZIP may have BAGO-x.y.z/ root folder)
        candidates = [d for d in dest.iterdir() if d.is_dir()]
        if len(candidates) == 1 and (candidates[0] / "bago").exists():
            return candidates[0]
        if (dest / "bago").exists():
            return dest
        return dest
    except Exception as exc:
        print(f"[ERROR] Extraccion fallida: {exc}", file=sys.stderr)
        return None


def _bootstrap_state(bago_root: Path) -> bool:
    bs = bago_root / ".bago" / "tools" / "bootstrap_state.py"
    if not bs.exists():
        print(f"  [WARN] bootstrap_state.py no encontrado en {bs}")
        return True  # non-blocking
    print(f"  [Bootstrap] Inicializando estado limpio...")
    r = subprocess.run([sys.executable, str(bs), str(bago_root)], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  [KO] Bootstrap fallo:\n{r.stderr}", file=sys.stderr)
        return False
    print(f"  [OK] Bootstrap completado")
    return True


def _validate(bago_root: Path) -> bool:
    validate_script = bago_root / "bago"
    if not validate_script.exists():
        print(f"[ERROR] Script 'bago' no encontrado en {bago_root}")
        return False
    print(f"  [Validando] bago validate...")
    r = subprocess.run([sys.executable, str(validate_script), "validate"], cwd=str(bago_root), capture_output=True, text=True)
    ok = r.returncode == 0 and "GO manifest" in r.stdout and "GO state" in r.stdout and "GO pack" in r.stdout
    if ok:
        print(f"  [OK] validate → GO manifest / GO state / GO pack")
    else:
        print(f"  [KO] validate fallo (rc={r.returncode})")
        if r.stdout:
            print(r.stdout[:500])
    return ok


def _register_shell_command(bago_root: Path) -> None:
    """Register 'bago' command in user's shell profile (PowerShell / bash / zsh)."""
    if sys.platform == "win32":
        _register_ps(bago_root)
    else:
        _register_unix(bago_root)


def _register_ps(bago_root: Path) -> None:
    profile_path = Path.home() / "Documents" / "WindowsPowerShell" / "Microsoft.PowerShell_profile.ps1"
    if not profile_path.exists():
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        profile_path.write_text("", encoding="utf-8")

    func_line = f'function bago {{ & "{sys.executable}" "{bago_root / "bago"}" @args }}'
    content = profile_path.read_text(encoding="utf-8")
    if "function bago" in content:
        # update existing
        content = content.replace(
            [l for l in content.splitlines() if "function bago" in l][0],
            func_line
        )
        profile_path.write_text(content, encoding="utf-8")
    else:
        profile_path.write_text(content + f"\n# BAGO Framework\n{func_line}\n", encoding="utf-8")
    print(f"  [OK] Comando 'bago' registrado en PowerShell profile")
    print(f"       Recarga tu terminal o ejecuta: . $PROFILE")


def _register_unix(bago_root: Path) -> None:
    shell = os.environ.get("SHELL", "/bin/bash")
    rc_file = Path.home() / ".bashrc"
    if "zsh" in shell:
        rc_file = Path.home() / ".zshrc"
    alias_line = f'alias bago="{sys.executable} {bago_root / "bago"}"'
    content = rc_file.read_text(encoding="utf-8") if rc_file.exists() else ""
    if "alias bago=" in content:
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if "alias bago=" in line:
                lines[i] = alias_line
        content = "\n".join(lines) + "\n"
    else:
        content = content + f"\n# BAGO Framework\n{alias_line}\n"
    rc_file.write_text(content, encoding="utf-8")
    print(f"  [OK] Alias 'bago' registrado en {rc_file.name}")
    print(f"       Recarga tu terminal: source {rc_file.name}")


# ── Public API ────────────────────────────────────────────────────────────────

def cmd_install(version: str | None = None, upgrade: bool = False, dry_run: bool = False) -> bool:
    releases = _get_releases(limit=15)
    if not releases:
        return False

    target_release = None
    if upgrade or version is None:
        target_release = releases[0]  # latest
    else:
        target_release = next((r for r in releases if r["tag"] == version or r["tag"] == f"v{version}"), None)
        if not target_release:
            print(f"[ERROR] Version '{version}' no encontrada.")
            print(f"  Versiones disponibles: {', '.join(r['tag'] for r in releases[:5])}")
            return False

    tag = target_release["tag"]
    print(f"  Version objetivo: {tag}")

    asset = _find_zip_asset(target_release)
    if not asset:
        print(f"[ERROR] No hay ZIP descargable en release {tag}")
        return False

    version_dir = VERSIONS_DIR / tag.lstrip("v")
    active_root = ACTIVE_DIR

    if version_dir.exists() and not upgrade:
        print(f"  Version {tag} ya esta instalada en {version_dir}")
        print(f"  Usa --upgrade para reinstalar o selecciona otra version.")
        return True

    if dry_run:
        print(f"  [DRY-RUN] Se descargaria: {asset['url']} ({asset['size'] // 1024} KB)")
        print(f"  [DRY-RUN] Se extraeria en: {version_dir}")
        print(f"  [DRY-RUN] Se activaria en: {active_root}")
        return True

    # Download
    zip_path = DEFAULT_INSTALL_DIR / "tmp" / f"{tag}.zip"
    if not _download(asset["url"], zip_path, "Descargando"):
        return False

    # Clean previous
    if version_dir.exists():
        shutil.rmtree(version_dir)
    if active_root.exists():
        shutil.rmtree(active_root)

    # Extract
    extracted = _extract(zip_path, version_dir)
    if not extracted:
        return False

    # Validate ZIP size (anti-recursive guard)
    size_mb = zip_path.stat().st_size / 1_048_576
    if size_mb > 100:
        print(f"[ERROR] ZIP demasiado grande ({size_mb:.1f} MB). Posible inclusion recursiva.")
        zip_path.unlink(missing_ok=True)
        shutil.rmtree(version_dir, ignore_errors=True)
        return False

    # Activate (copy/symlink)
    active_root.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform != "win32":
        active_root.symlink_to(extracted, target_is_directory=True)
    else:
        shutil.copytree(extracted, active_root, dirs_exist_ok=True)
    ACTIVE_MARKER.write_text(tag, encoding="utf-8")

    # Bootstrap + Validate
    ok = _bootstrap_state(active_root) and _validate(active_root)
    if not ok:
        print("[KO] Instalacion fallida en validacion. Revisa el paquete.")
        return False

    # Cleanup temp zip
    zip_path.unlink(missing_ok=True)

    # Register shell command
    _register_shell_command(active_root)

    print(f"\n  [OK] BAGO {tag} instalado correctamente en {active_root}")
    print(f"       Ejecuta 'bago' (recarga terminal primero) o:")
    print(f'       {sys.executable} "{active_root / "bago"}" help')
    return True


def cmd_list() -> None:
    releases = _get_releases(limit=10)
    if not releases:
        return
    print("\n  Releases disponibles:")
    print("  " + "-" * 50)
    for r in releases:
        tag = r["tag"]
        installed = "[INSTALADO]" if (VERSIONS_DIR / tag.lstrip("v")).exists() else ""
        active = "[ACTIVO]" if ACTIVE_MARKER.exists() and ACTIVE_MARKER.read_text().strip() == tag else ""
        print(f"  {tag:<12} {r['name'][:40]:<40} {installed} {active}")
    print()


def main() -> int:
    p = argparse.ArgumentParser(description="BAGO Remote Installer")
    p.add_argument("--version", default=None, help="Version especifica (ej: 3.4.5 o v3.4.5)")
    p.add_argument("--upgrade", action="store_true", help="Reinstalar / actualizar")
    p.add_argument("--list", action="store_true", help="Listar releases disponibles")
    p.add_argument("--dry-run", action="store_true", help="Simular sin instalar")
    args = p.parse_args()

    if args.list:
        cmd_list()
        return 0

    ok = cmd_install(version=args.version, upgrade=args.upgrade, dry_run=args.dry_run)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
