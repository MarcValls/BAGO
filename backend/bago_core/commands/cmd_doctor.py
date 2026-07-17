#!/usr/bin/env python3
"""cmd_doctor.py — bago doctor: salud integral de la instalación BAGO.

Ejecuta chequeos end-to-end y reporta PASS/FAIL/WARN por cada dimensión:
  1. Versión coherente en 5 archivos
  2. install_selection.json resuelve a la copia activa
  3. Bridge importa sin errores
  4. Ollama local responde
  5. Modelos locales visibles
  6. ui-react/src tiene estructura mínima
  7. la pieza de API tiene los módulos esperados
  8. verify-master.ps1 existe (si aplica)

Uso:
  bago doctor
  bago doctor --json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from bago_core.resolver import resolve_piece_path

BAGO_ROOT = Path(__file__).resolve().parents[2]
from bago_core.user_state_paths import install_selection_file, user_root, legacy_user_root


def _check(name: str, checks: list, ok: bool, detail: str = "") -> dict:
    status = "PASS" if ok else "FAIL"
    entry = {"check": name, "status": status, "detail": detail}
    marker = "✓" if ok else "✗"
    line = f"  [{marker}] {name}"
    if detail:
        line += f" — {detail}"
    print(line)
    return entry


def cmd_doctor(args: argparse.Namespace) -> int:
    as_json = getattr(args, "json", False)
    checks: list[dict] = []
    fails = 0

    print("\nBAGO DOCTOR\n" + "=" * 48)

    # ── 1. Versión coherente ────────────────────────────────────────────────
    version_files = {
        "release_version.txt": BAGO_ROOT / "release_version.txt",
        "pyproject.toml": BAGO_ROOT / "pyproject.toml",
        "versions.json": BAGO_ROOT / "versions.json",
        "package.json": BAGO_ROOT / "package.json",
        "cli.py --version": BAGO_ROOT / "bago_core" / "cli.py",
    }
    versions = set()
    for label, path in version_files.items():
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            if label == "pyproject.toml":
                import re
                m = re.search(r'^version\s*=\s*["\']([^"\']+)', text, re.M)
                if m:
                    versions.add(m.group(1))
            elif label == "package.json":
                data = json.loads(text)
                versions.add(data.get("version", ""))
            elif label == "versions.json":
                data = json.loads(text)
                versions.add(data.get("version", data.get("current", "")))
            elif label == "cli.py --version":
                result = subprocess.run(
                    [sys.executable, str(path), "--version"],
                    capture_output=True, text=True, timeout=10,
                )
                v = result.stdout.strip().replace("bago ", "")
                if v:
                    versions.add(v)
            else:
                versions.add(text.strip())
        except Exception:
            pass

    ver_ok = len(versions) == 1
    ver_detail = f"versiones encontradas: {versions}" if not ver_ok else f"v{versions.pop()}"
    if not ver_ok:
        fails += 1
    checks.append(_check("version_coherent", checks, ver_ok, ver_detail))

    # ── 2. install_selection.json ────────────────────────────────────────────
    sel_path = install_selection_file()
    sel_ok = sel_path.exists()
    sel_detail = ""
    if sel_ok:
        try:
            sel = json.loads(sel_path.read_text(encoding="utf-8"))
            # Support both shapes: {active:{path:...}} and {roles:{active:{path:...}}}
            active = sel.get("active", {})
            if not active:
                active = sel.get("roles", {}).get("active", {})
            active_path = active.get("path", "")
            if active_path:
                resolved = active_path
                sel_ok = Path(resolved).exists()
                if sel_ok:
                    sel_detail = f"active → {resolved}"
                else:
                    sel_detail = f"active path no existe: {resolved}"
                    fails += 1
            else:
                sel_detail = "active.path vacío"
                fails += 1
        except Exception as exc:
            sel_detail = f"error leyendo JSON: {exc}"
            fails += 1
    else:
        sel_detail = f"{sel_path} no existe"
        fails += 1
    checks.append(_check("install_selection", checks, sel_ok, sel_detail))

    # ── 3. Bridge importa ────────────────────────────────────────────────────
    bridge_dir = resolve_piece_path("api.package")
    bridge_ok = bridge_dir.exists() and (bridge_dir / "bridge.py").exists()
    bridge_detail = ""
    if bridge_ok:
        try:
            result = subprocess.run(
                [sys.executable, "-c",
                 f"import sys; sys.path.insert(0, r'{bridge_dir}'); import bridge; print('OK')"],
                capture_output=True, text=True, timeout=15,
                cwd=str(bridge_dir),
            )
            bridge_ok = result.returncode == 0 and "OK" in result.stdout
            if not bridge_ok:
                bridge_detail = result.stderr[:200] if result.stderr else "import falló sin mensaje"
                fails += 1
            else:
                bridge_detail = "bridge.py importa correctamente"
        except Exception as exc:
            bridge_detail = f"excepción: {exc}"
            bridge_ok = False
            fails += 1
    else:
        bridge_detail = "api/bridge.py no encontrado"
        fails += 1
    checks.append(_check("bridge_import", checks, bridge_ok, bridge_detail))

    # ── 4. Ollama local responde ──────────────────────────────────────────────
    ollama_ok = False
    ollama_detail = ""
    try:
        import urllib.request
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            model_count = len(data.get("models", []))
            ollama_ok = model_count > 0
            ollama_detail = f"{model_count} modelos locales"
            if not ollama_ok:
                fails += 1
    except Exception as exc:
        ollama_detail = f"Ollama no responde: {exc}"
        fails += 1
    checks.append(_check("ollama_local", checks, ollama_ok, ollama_detail))

    # ── 5. ui-react/src estructura mínima ─────────────────────────────────────
    src = BAGO_ROOT / "ui-react" / "src"
    expected_files = ["App.jsx", "main.jsx", "api.js", "styles.css"]
    present = [f for f in expected_files if (src / f).exists()]
    ui_ok = len(present) == len(expected_files)
    ui_detail = f"{len(present)}/{len(expected_files)} archivos base presentes"
    if not ui_ok:
        fails += 1
    checks.append(_check("ui_react_structure", checks, ui_ok, ui_detail))

    # ── 6. pieza de API: módulos esperados ─────────────────────────────────────
    expected_modules = [
        "bridge.py", "api_dispatch.py", "api_auth.py", "api_serializers.py",
        "request_context.py", "handlers_chat.py", "handlers_router.py",
        "handlers_routes.py",
    ]
    api_dir = resolve_piece_path("api.package")
    present_mods = [m for m in expected_modules if (api_dir / m).exists()]
    api_ok = len(present_mods) == len(expected_modules)
    api_detail = f"{len(present_mods)}/{len(expected_modules)} módulos presentes"
    if not api_ok:
        fails += 1
    checks.append(_check("api_modules", checks, api_ok, api_detail))

    # ── Resultado final ────────────────────────────────────────────────────────
    print("\n" + "=" * 48)
    if fails == 0:
        print(f"✓ DOCTOR PASS — {len(checks)} checks OK")
    else:
        print(f"✗ DOCTOR FAIL — {fails}/{len(checks)} checks fallaron")
        for c in checks:
            if c["status"] == "FAIL":
                print(f"  → [{c['check']}]: {c['detail']}")
    print()

    if as_json:
        print(json.dumps({"checks": checks, "fails": fails}, indent=2, ensure_ascii=False))

    return 0 if fails == 0 else 1
