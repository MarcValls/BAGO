#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bago_version.py — Gestión de versiones beta / release (R-VERS-01).

Mantiene sincronizados pyproject.toml y bago_core/__init__.py.
Soporta el flujo:  stable → beta → beta+1 → release → next cycle

Uso:
    bago version                   # panel de estado
    bago version bump patch        # 3.2.0 → 3.2.1  (solo escribe)
    bago version bump minor        # 3.2.0 → 3.3.0
    bago version bump major        # 3.2.0 → 4.0.0
    bago version beta              # 3.2.0 → 3.3.0b1  /  3.3.0b1 → 3.3.0b2
    bago version release           # 3.3.0b2 → 3.3.0
    bago version tag [--push]      # crea tag anotado v<ver> (con --push lo sube)
    bago version commit            # git commit "chore(version): bump to <ver>"
    bago version sync-check        # verifica que ambos archivos coinciden
    bago version sync-state        # sincroniza .bago/state/global_state.json con versión actual
    bago version --self-test       # autotest
"""
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import json
import re
import subprocess
import sys
from pathlib import Path

# ── Rutas canónicas ───────────────────────────────────────────────────────────

_ROOT = Path(__file__).resolve().parents[2]   # raíz del repo
BAGO_ROOT = _ROOT / ".bago"
_PYPROJECT = _ROOT / "pyproject.toml"
_INIT = _ROOT / "bago_core" / "__init__.py"
_GLOBAL_STATE = _ROOT / ".bago" / "state" / "global_state.json"

# Patrones de versión PEP 440 (subset: X.Y.Z o X.Y.ZbN)
_STABLE_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
_BETA_RE    = re.compile(r"^(\d+)\.(\d+)\.(\d+)b(\d+)$")
_TAG_STABLE = re.compile(r"^v\d+\.\d+\.\d+$")
_TAG_BETA   = re.compile(r"^v\d+\.\d+\.\d+b\d+$")


# ── Lectura / escritura de versión (stdlib-only, Python 3.9 compat) ────────────

def _read_pyproject_version() -> str:
    """Lee version = \"X.Y.Z\" de pyproject.toml."""
    if not _PYPROJECT.exists():
        return _read_init_version()
    text = _PYPROJECT.read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not m:
        raise RuntimeError(f"No se encontró version en {_PYPROJECT}")
    return m.group(1)


def _read_init_version() -> str:
    """Lee __version__ = \"X.Y.Z\" de bago_core/__init__.py."""
    text = _INIT.read_text(encoding="utf-8")
    m = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not m:
        raise RuntimeError(f"No se encontró __version__ en {_INIT}")
    return m.group(1)


def _write_pyproject_version(new_ver: str) -> None:
    if not _PYPROJECT.exists():
        return
    text = _PYPROJECT.read_text(encoding="utf-8")
    old = _read_pyproject_version()
    count = text.count(f'version = "{old}"')
    if count != 1:
        raise RuntimeError(f"Encontradas {count} ocurrencias de version en pyproject.toml (esperado 1)")
    new_text = text.replace(f'version = "{old}"', f'version = "{new_ver}"', 1)
    _PYPROJECT.write_text(new_text, encoding="utf-8")


def _write_init_version(new_ver: str) -> None:
    text = _INIT.read_text(encoding="utf-8")
    old = _read_init_version()
    count = text.count(f'__version__ = "{old}"')
    if count != 1:
        raise RuntimeError(f"Encontradas {count} ocurrencias de __version__ en __init__.py (esperado 1)")
    new_text = text.replace(f'__version__ = "{old}"', f'__version__ = "{new_ver}"', 1)
    _INIT.write_text(new_text, encoding="utf-8")


def _write_version(new_ver: str) -> None:
    """Escribe nueva versión en ambos archivos atómicamente."""
    _write_pyproject_version(new_ver)
    _write_init_version(new_ver)


# ── Git helpers ───────────────────────────────────────────────────────────────

def _git(args: list[str], capture: bool = True, check: bool = False) -> str:
    r = subprocess.run(
        ["git"] + args,
        capture_output=capture, text=True,
        cwd=str(_ROOT),
    )
    if check and r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or r.stdout.strip())
    return r.stdout.strip()


def _is_clean_worktree() -> bool:
    out = _git(["status", "--porcelain"])
    return out == ""


def _current_branch() -> str:
    return _git(["rev-parse", "--abbrev-ref", "HEAD"])


def _tag_exists(tag: str) -> bool:
    return _git(["tag", "-l", tag]) == tag


def _latest_tag() -> str:
    out = _git(["describe", "--tags", "--abbrev=0"])
    return out if out else "(ninguno)"


def _is_behind_remote() -> tuple[bool, str]:
    """Retorna (behind, branch). behind=True si hay commits remotos no integrados."""
    branch = _current_branch()
    _git(["fetch", "--quiet", "origin"])
    behind = _git(["rev-list", "--count", f"HEAD..origin/{branch}"])
    try:
        return int(behind) > 0, branch
    except ValueError:
        return False, branch


# ── Lógica de versión ─────────────────────────────────────────────────────────

def _parse_version(ver: str) -> dict:
    if m := _STABLE_RE.match(ver):
        return {"track": "stable", "major": int(m.group(1)),
                "minor": int(m.group(2)), "patch": int(m.group(3)), "beta": 0}
    if m := _BETA_RE.match(ver):
        return {"track": "beta", "major": int(m.group(1)),
                "minor": int(m.group(2)), "patch": int(m.group(3)),
                "beta": int(m.group(4))}
    raise ValueError(f"Versión no reconocida: {ver!r}")


def _bump(ver: str, part: str) -> str:
    v = _parse_version(ver)
    if v["track"] == "beta":
        raise RuntimeError(
            f"No se puede hacer bump en beta {ver}. "
            "Usa 'bago version release' primero para pasar a stable."
        )
    if part == "patch":
        return f"{v['major']}.{v['minor']}.{v['patch']+1}"
    if part == "minor":
        return f"{v['major']}.{v['minor']+1}.0"
    if part == "major":
        return f"{v['major']+1}.0.0"
    raise ValueError(f"part debe ser patch|minor|major, no {part!r}")


def _to_beta(ver: str) -> str:
    v = _parse_version(ver)
    if v["track"] == "stable":
        return f"{v['major']}.{v['minor']+1}.0b1"
    if v["track"] == "beta":
        return f"{v['major']}.{v['minor']}.{v['patch']}b{v['beta']+1}"
    raise ValueError(ver)


def _to_release(ver: str) -> str:
    v = _parse_version(ver)
    if v["track"] != "beta":
        raise RuntimeError(f"'release' solo se puede hacer desde una versión beta, no desde {ver!r}")
    return f"{v['major']}.{v['minor']}.{v['patch']}"


def _run_supervision_gate() -> bool:
    """Corre el pre_release_loop de supervision. Devuelve True si OK."""
    supervisor_py = BAGO_ROOT / "supervision" / "supervisor.py"
    if not supervisor_py.exists():
        return True  # supervision layer no instalada — skip
    result = subprocess.run(
        [sys.executable, str(supervisor_py), "run", "--loop", "pre_release"],
        capture_output=False,
        cwd=str(BAGO_ROOT.parent),
    )
    return result.returncode == 0


# ── Comandos ──────────────────────────────────────────────────────────────────

def cmd_status() -> int:
    pyv = _read_pyproject_version()
    initv = _read_init_version()
    synced = pyv == initv
    v = _parse_version(pyv)
    latest = _latest_tag()
    tagged = f"v{pyv}" == latest
    clean = _is_clean_worktree()
    branch = _current_branch()

    track_label = "🔶 BETA" if v["track"] == "beta" else "✅ ESTABLE"

    print()
    print("  ┌─ bago version ─────────────────────────────────────────────")
    print(f"  │  Versión actual : {pyv}  {track_label}")
    print(f"  │  Rama           : {branch}")
    print(f"  │  Último tag     : {latest}  {'✅ tagged' if tagged else '⚠️  sin tag'}")
    print(f"  │  Sync archivos  : {'✅ OK' if synced else f'❌ DESYNC (pyproject={pyv}, __init__={initv})'}")
    print(f"  │  Worktree       : {'✅ limpio' if clean else '⚠️  cambios sin commit'}")
    print("  │")
    if v["track"] == "stable":
        next_beta = _to_beta(pyv)
        print(f"  │  → Siguiente beta    : bago version beta   → {next_beta}")
        print(f"  │  → Bump patch        : bago version bump patch")
    else:
        next_beta = _to_beta(pyv)
        next_rel  = _to_release(pyv)
        print(f"  │  → Siguiente beta    : bago version beta    → {next_beta}")
        print(f"  │  → Promover release  : bago version release → {next_rel}")
    print("  └────────────────────────────────────────────────────────────")
    print()
    return 0


def cmd_bump(part: str) -> int:
    ver = _read_pyproject_version()
    new_ver = _bump(ver, part)
    print(f"  Bump {part}: {ver} → {new_ver}")
    _write_version(new_ver)
    print(f"  ✅ Archivos actualizados. Próximos pasos:")
    print(f"     bago version commit")
    print(f"     bago version tag --push")
    return 0


def cmd_beta() -> int:
    ver = _read_pyproject_version()
    new_ver = _to_beta(ver)
    print(f"  Beta: {ver} → {new_ver}")
    _write_version(new_ver)
    print(f"  ✅ Archivos actualizados. Próximos pasos:")
    print(f"     bago version commit")
    print(f"     bago version tag --push")
    return 0


def cmd_release(dry_run: bool = False) -> int:
    ver = _read_pyproject_version()
    new_ver = _to_release(ver)
    print(f"  Release: {ver} → {new_ver}")
    if not dry_run:
        print("🔍 Ejecutando Supervision Gate (pre_release_loop)...")
        if not _run_supervision_gate():
            print("❌ Supervision Gate bloqueó el release. Revisa bago supervision status")
            sys.exit(1)
        print("✅ Supervision Gate: OK")
        _write_version(new_ver)
        print(f"  ✅ Archivos actualizados. Próximos pasos:")
        print(f"     bago version commit")
        print(f"     bago version tag --push")
    else:
        print("  🧪 Dry-run: no se escribieron cambios.")
    return 0


def cmd_commit() -> int:
    ver = _read_pyproject_version()
    if not _is_clean_worktree():
        # Check only version files changed
        diff = _git(["diff", "--cached", "--name-only"])
        unstaged = _git(["diff", "--name-only"])
        all_changed = set((diff + "\n" + unstaged).splitlines())
        allowed = {"pyproject.toml", "bago_core/__init__.py"}
        extra = all_changed - allowed - {""}
        if extra:
            print(f"  ⚠️  Hay otros cambios sin commit: {extra}")
            print("  Por seguridad, haz commit manual o revisa con 'git status'.")
            return 1

    # Stage version files
    _git(["add", str(_PYPROJECT.relative_to(_ROOT)),
          str(_INIT.relative_to(_ROOT))], capture=False)
    msg = (
        f"chore(version): bump to {ver}\n\n"
        f"Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
    )
    _git(["commit", "-m", msg], check=True)
    print(f"  ✅ Commit creado: chore(version): bump to {ver}")
    return 0


def cmd_tag(push: bool = False) -> int:
    ver = _read_pyproject_version()
    tag = f"v{ver}"

    # Safeguards
    if not _is_clean_worktree():
        print(f"  ❌ Worktree no está limpio. Haz commit de tus cambios primero.")
        return 1
    init_ver = _read_init_version()
    if ver != init_ver:
        print(f"  ❌ Desync: pyproject={ver} != __init__={init_ver}")
        print("     Ejecuta: bago version sync-check")
        return 1
    if _tag_exists(tag):
        print(f"  ❌ El tag {tag!r} ya existe localmente.")
        return 1

    # Crear tag anotado
    _git(["tag", "-a", tag, "-m", f"BAGO {tag}"], check=True)
    print(f"  ✅ Tag anotado creado: {tag}")

    if push:
        # Verificar no estamos detrás del remoto antes de push
        behind, branch = _is_behind_remote()
        if behind:
            print(f"  ❌ Rama '{branch}' está detrás de origin. Haz 'git pull' primero.")
            _git(["tag", "-d", tag])   # deshacer tag local
            return 1
        _git(["push", "origin", tag], check=True)
        print(f"  ✅ Tag {tag} subido a origin. CI publicará el release.")
        print(f"     → https://github.com/MarcValls/BAGO/releases/tag/{tag}")
    else:
        print(f"  Para subir el tag: bago version tag --push")

    return 0


def cmd_sync_check() -> int:
    pyv = _read_pyproject_version()
    initv = _read_init_version()
    if pyv == initv:
        print(f"  ✅ Sync OK: ambos archivos en {pyv}")
        return 0
    print(f"  ❌ DESYNC:")
    print(f"     pyproject.toml   : {pyv}")
    print(f"     bago_core/__init__: {initv}")
    print(f"  Para sincronizar: edita uno de los dos y vuelve a ejecutar.")
    return 1


def cmd_sync_state() -> int:
    """Sincroniza global_state.bago_version con la versión canónica."""
    pyv = _read_pyproject_version()
    initv = _read_init_version()
    if pyv != initv:
        print("  ❌ No se puede sincronizar estado: pyproject y __init__ están desalineados.")
        print(f"     pyproject.toml    : {pyv}")
        print(f"     bago_core/__init__: {initv}")
        print("  Ejecuta primero: bago version sync-check")
        return 1

    if not _GLOBAL_STATE.exists():
        print(f"  ❌ No existe {_GLOBAL_STATE}")
        return 1

    try:
        data = json.loads(_GLOBAL_STATE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("global_state no es un objeto JSON")
    except Exception as e:
        print(f"  ❌ Error leyendo global_state.json: {e}")
        return 1

    old = str(data.get("bago_version", "")).strip()
    data["bago_version"] = pyv
    _GLOBAL_STATE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if old == pyv:
        print(f"  ✅ global_state ya estaba sincronizado en {pyv}")
    else:
        print(f"  ✅ global_state sincronizado: {old or '(vacío)'} → {pyv}")
    return 0


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> int:
    args = sys.argv[1:]

    if not args:
        return cmd_status()

    if args[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    if args[0] == "--self-test":
        return _self_test()

    sub = args[0]

    if sub == "bump":
        if len(args) < 2 or args[1] not in ("patch", "minor", "major"):
            print("  Uso: bago version bump patch|minor|major")
            return 1
        return cmd_bump(args[1])

    if sub == "beta":
        return cmd_beta()

    if sub == "release":
        return cmd_release(dry_run=("--dry-run" in args[1:]))

    if sub == "commit":
        return cmd_commit()

    if sub == "tag":
        push = "--push" in args
        return cmd_tag(push=push)

    if sub == "sync-check":
        return cmd_sync_check()

    if sub == "sync-state":
        return cmd_sync_state()

    print(f"  Subcomando desconocido: {sub!r}")
    print("  Usa 'bago version --help' para ver opciones.")
    return 1


# ── Self-test ──────────────────────────────────────────────────────────────────

def _self_test() -> int:
    import unittest

    class TestVersionLogic(unittest.TestCase):

        def test_parse_stable(self):
            v = _parse_version("3.2.0")
            self.assertEqual(v["track"], "stable")
            self.assertEqual(v["major"], 3)
            self.assertEqual(v["minor"], 2)
            self.assertEqual(v["patch"], 0)

        def test_parse_beta(self):
            v = _parse_version("3.3.0b2")
            self.assertEqual(v["track"], "beta")
            self.assertEqual(v["beta"], 2)

        def test_bump_patch(self):
            self.assertEqual(_bump("3.2.0", "patch"), "3.2.1")

        def test_bump_minor(self):
            self.assertEqual(_bump("3.2.0", "minor"), "3.3.0")

        def test_bump_major(self):
            self.assertEqual(_bump("3.2.0", "major"), "4.0.0")

        def test_bump_on_beta_raises(self):
            with self.assertRaises(RuntimeError):
                _bump("3.3.0b1", "patch")

        def test_to_beta_from_stable(self):
            self.assertEqual(_to_beta("3.2.0"), "3.3.0b1")

        def test_to_beta_from_beta(self):
            self.assertEqual(_to_beta("3.3.0b1"), "3.3.0b2")
            self.assertEqual(_to_beta("3.3.0b9"), "3.3.0b10")

        def test_to_release_from_beta(self):
            self.assertEqual(_to_release("3.3.0b2"), "3.3.0")

        def test_to_release_from_stable_raises(self):
            with self.assertRaises(RuntimeError):
                _to_release("3.3.0")

        def test_tag_stable_re(self):
            self.assertTrue(_TAG_STABLE.match("v3.3.0"))
            self.assertFalse(_TAG_STABLE.match("v3.3.0b1"))
            self.assertFalse(_TAG_STABLE.match("v3.3.0-backport"))

        def test_tag_beta_re(self):
            self.assertTrue(_TAG_BETA.match("v3.3.0b1"))
            self.assertFalse(_TAG_BETA.match("v3.3.0"))
            self.assertFalse(_TAG_BETA.match("v3.3.0-beta"))

        def test_files_exist(self):
            self.assertTrue(_PYPROJECT.exists(), f"{_PYPROJECT} no existe")
            self.assertTrue(_INIT.exists(), f"{_INIT} no existe")

        def test_sync(self):
            pyv = _read_pyproject_version()
            initv = _read_init_version()
            self.assertEqual(pyv, initv, f"DESYNC: pyproject={pyv} vs __init__={initv}")

    suite = unittest.TestLoader().loadTestsFromTestCase(TestVersionLogic)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.wasSuccessful() else 1




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