#!/usr/bin/env python3
"""bago_update.py — actualiza BAGO desde GitHub releases.

Uso:
    bago update [--yes] [--dry-run] [--beta] [--stable] [--list]
    bago update --local [--with-local]  # mantenimiento antiguo: modelos/deps/heal/env
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import zipfile
import os
import json
from pathlib import Path
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = Path(__file__).resolve().parent
PYTHON = sys.executable
GITHUB_REPO = "MarcValls/BAGO"
GITHUB_RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _info(msg: str) -> None:
    print(f"  -> {msg}")


def _ok(msg: str) -> None:
    print(f"  OK {msg}")


def _warn(msg: str) -> None:
    print(f"  WARN {msg}")


def _err(msg: str) -> None:
    print(f"  ERR {msg}")


def _run(cmd: list[str], *, cwd: Path | None = None, dry_run: bool = False, timeout: int = 300) -> int:
    shown = " ".join(cmd)
    _info(shown)
    if dry_run:
        return 0
    try:
        proc = subprocess.run(cmd, cwd=str(cwd or PROJECT_ROOT), timeout=timeout)
        return proc.returncode
    except subprocess.TimeoutExpired:
        _err(f"timeout: {shown}")
        return 124
    except Exception as exc:
        _err(f"{shown}: {exc}")
        return 1


def _ollama_models() -> list[str]:
    ollama = shutil.which("ollama")
    if not ollama:
        return []
    try:
        proc = subprocess.run([ollama, "list"], capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace")
    except Exception:
        return []
    models: list[str] = []
    for line in proc.stdout.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        model = line.split()[0].strip()
        if model and model.upper() != "NAME":
            models.append(model)
    seen: set[str] = set()
    unique: list[str] = []
    for model in models:
        if model not in seen:
            seen.add(model)
            unique.append(model)
    return unique


def _confirm() -> bool:
    try:
        answer = input(f"Buscar releases en GitHub {GITHUB_REPO} e instalar si procede? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer in {"y", "yes", "s", "si"}


def _confirm_beta(tag: str, stable_tag: str | None) -> bool:
    suffix = f" (estable: {stable_tag})" if stable_tag else ""
    try:
        answer = input(f"Hay beta disponible {tag}{suffix}. Instalar beta? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer in {"y", "yes", "s", "si"}


def _normalize_tag(value: str | None) -> str:
    tag = (value or "").strip().lower()
    return tag[1:] if tag.startswith("v") else tag


def _user_bago_home() -> Path:
    value = os.environ.get("BAGO_USER_HOME") or os.environ.get("BAGO_USER_DIR")
    if value:
        return Path(value).expanduser()
    return Path.home() / ".bago"


def _current_version() -> str:
    pack = PROJECT_ROOT / ".bago" / "pack.json"
    if pack.exists():
        try:
            import json

            data = json.loads(pack.read_text(encoding="utf-8"))
            value = str(data.get("version", "")).strip()
            if value:
                return value if value.startswith("v") else f"v{value}"
        except Exception:
            pass

    for marker in (
        _user_bago_home() / "active_version.txt",
        Path.home() / ".bago" / "active_version.txt",
    ):
        if marker.exists():
            try:
                value = marker.read_text(encoding="utf-8").strip()
                if value:
                    return value
            except Exception:
                pass
    return ""


def _write_active_version(tag: str) -> None:
    marker = _user_bago_home() / "active_version.txt"
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(tag, encoding="utf-8")
    except Exception:
        pass


def _sync_state_version(tag: str) -> None:
    version = _normalize_tag(tag)
    state_path = PROJECT_ROOT / ".bago" / "state" / "global_state.json"
    if not state_path.exists():
        return
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
        data["bago_version"] = version
        state_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _github_api(url: str) -> dict | list:
    req = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "bago-update",
        },
    )
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_releases(limit: int = 30) -> list[dict]:
    _info(f"consultando GitHub releases: {GITHUB_REPO}")
    try:
        data = _github_api(f"{GITHUB_RELEASES_API}?per_page={limit}")
    except Exception as exc:
        _err(f"no se pudieron listar releases de {GITHUB_REPO}: {exc}")
        return []
    return [
        {
            "tag": r["tag_name"],
            "name": r.get("name") or r["tag_name"],
            "published": r.get("published_at", ""),
            "prerelease": bool(r.get("prerelease")),
            "assets": [
                {
                    "name": a["name"],
                    "url": a["browser_download_url"],
                    "size": a.get("size", 0),
                }
                for a in r.get("assets", [])
            ],
        }
        for r in data
        if not r.get("draft")
    ]


def _print_releases(releases: list[dict]) -> None:
    from bago_core import installer

    print(f"\n  Releases GitHub: {GITHUB_REPO}")
    print("  " + "-" * 58)
    for release in releases[:10]:
        channel = "BETA" if installer._is_beta_release(release) else "STABLE"
        installable = "" if installer._is_installable_release(release) else " SIN ZIP"
        print(f"  {release['tag']:<16} [{channel}]{installable}  {release.get('name', '')}")


def _release_index(releases: list[dict], tag: str) -> int | None:
    wanted = _normalize_tag(tag)
    for idx, release in enumerate(releases):
        if _normalize_tag(release.get("tag")) == wanted:
            return idx
    return None


def _is_newer(target: dict, current: str, releases: list[dict]) -> bool:
    if not current:
        return True
    if _normalize_tag(target.get("tag")) == _normalize_tag(current):
        return False
    target_idx = _release_index(releases, str(target.get("tag", "")))
    current_idx = _release_index(releases, current)
    if target_idx is None or current_idx is None:
        return _normalize_tag(target.get("tag")) != _normalize_tag(current)
    return target_idx < current_idx


def _latest_beta_installable(releases: list[dict]) -> dict | None:
    from bago_core import installer

    for release in releases:
        if installer._is_beta_release(release) and installer._is_installable_release(release):
            return release
    return None


def _latest_beta_seen(releases: list[dict]) -> dict | None:
    from bago_core import installer

    for release in releases:
        if installer._is_beta_release(release):
            return release
    return None


def _zip_members(zip_path: Path) -> list[tuple[str, str, int]]:
    members: list[tuple[str, str, int]] = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            raw = info.filename.replace("\\", "/")
            if not raw or raw.endswith("/") or raw.startswith("__MACOSX/"):
                continue
            parts = [p for p in raw.split("/") if p]
            if any(p == ".." for p in parts) or raw.startswith("/"):
                raise ValueError(f"ruta insegura en ZIP: {info.filename}")
            members.append((raw, raw, info.file_size))

    top_levels = {name.split("/", 1)[0] for name, _, _ in members if "/" in name}
    root_files = [name for name, _, _ in members if "/" not in name]
    if len(top_levels) == 1 and not root_files and ".bago" not in top_levels:
        prefix = next(iter(top_levels)) + "/"
        members = [(name[len(prefix):], raw, size) for name, raw, size in members]
    return [(name, raw, size) for name, raw, size in members if name]


def _is_bago_payload(members: list[tuple[str, str, int]]) -> bool:
    names = {name for name, _, _ in members}
    return ".bago/pack.json" in names or "bago.cmd" in names or "bago.ps1" in names or any(n.startswith("bago_core/") for n in names)


def _backup_existing_files(root: Path, members: list[tuple[str, str, int]], current: str) -> Path | None:
    existing = [root / name for name, _, _ in members if (root / name).exists()]
    if not existing:
        return None
    safe_version = _normalize_tag(current or "unknown").replace("/", "_").replace("\\", "_") or "unknown"
    backup_dir = root / ".bago" / "backups" / f"update-{safe_version}"
    if backup_dir.exists():
        import time

        backup_dir = root / ".bago" / "backups" / f"update-{safe_version}-{int(time.time())}"
    for path in existing:
        rel = path.relative_to(root)
        dest = backup_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
    return backup_dir


def _apply_zip_to_current_install(release: dict, *, dry_run: bool, current: str) -> bool:
    from bago_core import installer

    asset = installer._find_zip_asset(release)
    if not asset:
        _err(f"{release['tag']} no tiene ZIP descargable")
        return False

    with tempfile.TemporaryDirectory(prefix="bago-update-") as tmp:
        zip_path = Path(tmp) / f"{release['tag']}.zip"
        if not installer._download(asset["url"], zip_path, "Descargando release"):
            return False

        try:
            members = _zip_members(zip_path)
        except Exception as exc:
            _err(str(exc))
            return False

        if not _is_bago_payload(members):
            _err("el ZIP no parece un payload BAGO instalable")
            return False

        total_mb = sum(size for _, _, size in members) / 1_048_576
        _info(f"payload: {len(members)} archivos, {total_mb:.1f} MB")
        if dry_run:
            for name, _, _ in members[:8]:
                _info(f"DRY-RUN escribiria: {PROJECT_ROOT / name}")
            if len(members) > 8:
                _info(f"DRY-RUN ... y {len(members) - 8} archivos mas")
            return True

        backup_dir = _backup_existing_files(PROJECT_ROOT, members, current)
        if backup_dir:
            _info(f"backup previo: {backup_dir}")

        with zipfile.ZipFile(zip_path, "r") as zf:
            for name, raw, _ in members:
                dest = PROJECT_ROOT / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(raw, "r") as src, open(dest, "wb") as out:
                    shutil.copyfileobj(src, out)

    _ok(f"BAGO actualizado a {release['tag']}")
    _write_active_version(str(release["tag"]))
    _sync_state_version(str(release["tag"]))
    return True


def _run_release_update(argv: list[str], *, dry_run: bool, assume_yes: bool) -> int:
    from bago_core import installer

    want_beta = "--beta" in argv
    force_stable = "--stable" in argv
    list_only = "--list" in argv

    releases = _get_releases(limit=30)
    if not releases:
        return 1
    if list_only:
        _print_releases(releases)
        return 0

    current = _current_version()
    stable = installer._latest_installable(releases, include_beta=False)
    beta = _latest_beta_installable(releases)
    seen_beta = _latest_beta_seen(releases)

    _info(f"version instalada: {current or 'desconocida'}")
    if stable:
        _info(f"ultima estable instalable: {stable['tag']}")
    else:
        _warn("no hay release estable instalable con ZIP")
    if seen_beta and not beta:
        _warn(f"beta detectada sin ZIP instalable: {seen_beta['tag']}")
    elif beta:
        _info(f"ultima beta instalable: {beta['tag']}")

    target = stable
    if want_beta:
        if not beta:
            _err("no hay beta instalable con ZIP descargable")
            return 1
        target = beta
    elif not force_stable and beta and _is_newer(beta, current, releases):
        if assume_yes:
            _warn("hay beta nueva; usa --beta para instalarla sin prompt")
        elif _confirm_beta(beta["tag"], stable["tag"] if stable else None):
            target = beta

    if not target:
        return 1

    if not _is_newer(target, current, releases):
        _ok(f"ya estas en {current}; no hay update aplicable en este canal")
        return 0

    if not dry_run and not assume_yes and not _confirm():
        _warn("cancelado")
        return 0

    _info(f"actualizando BAGO a {target['tag']}")
    ok = _apply_zip_to_current_install(target, dry_run=dry_run, current=current)
    return 0 if ok else 1


def _run_local_maintenance(*, dry_run: bool) -> int:
    failures = 0

    models = _ollama_models()
    if models:
        _info(f"modelos locales detectados: {', '.join(models)}")
        ollama = shutil.which("ollama") or "ollama"
        for model in models:
            rc = _run([ollama, "pull", model], dry_run=dry_run, timeout=1800)
            if rc != 0:
                failures += 1
    else:
        _warn("sin modelos locales activos; no hay pulls que ejecutar")

    rc = _run([PYTHON, str(TOOLS_DIR / "outdated_check.py")], dry_run=dry_run, timeout=180)
    if rc not in (0, 1):
        failures += 1

    deps_args = [PYTHON, str(TOOLS_DIR / "deps_check.py")]
    if not dry_run:
        deps_args.append("--install")
    rc = _run(deps_args, dry_run=dry_run, timeout=300)
    if rc not in (0, 1, 2):
        failures += 1

    heal_args = [PYTHON, str(TOOLS_DIR / "auto_heal.py"), "--dry-run" if dry_run else "--fix"]
    rc = _run(heal_args, dry_run=False, timeout=300)
    if rc != 0:
        failures += 1

    rc = _run([PYTHON, str(TOOLS_DIR / "env.py"), "check"], dry_run=dry_run, timeout=180)
    if rc not in (0, 1):
        failures += 1

    if failures:
        _warn(f"update finalizado con incidencias: {failures}")
        return 1
    _ok("update finalizado")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    dry_run = "--dry-run" in argv
    assume_yes = "--yes" in argv
    local_only = "--local" in argv
    with_local = "--with-local" in argv

    if "--test" in argv:
        required = [
            TOOLS_DIR / "outdated_check.py",
            TOOLS_DIR / "deps_check.py",
            TOOLS_DIR / "auto_heal.py",
            TOOLS_DIR / "env.py",
            PROJECT_ROOT / "bago_core" / "installer.py",
            Path(__file__),
        ]
        missing = [str(p) for p in required if not p.exists()]
        if missing:
            _err("faltan archivos: " + ", ".join(missing))
            return 1
        if GITHUB_REPO != "MarcValls/BAGO" or "MarcValls/BAGO" not in GITHUB_RELEASES_API:
            _err("origen GitHub incorrecto para releases")
            return 1
        _ok("self-test OK")
        return 0

    print()
    print("  BAGO Update")
    print(f"  Origen releases: {GITHUB_REPO}")
    print("  ----------------------------------------------")

    if local_only:
        if not dry_run and not assume_yes and not _confirm():
            _warn("cancelado")
            return 0
        return _run_local_maintenance(dry_run=dry_run)

    rc = _run_release_update(argv, dry_run=dry_run, assume_yes=assume_yes)
    if rc == 0 and with_local:
        local_rc = _run_local_maintenance(dry_run=dry_run)
        if local_rc != 0:
            return local_rc
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
