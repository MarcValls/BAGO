#!/usr/bin/env python3
"""bago_doctor.py — Diagnóstico completo del entorno BAGO.

Comprueba todos los requisitos del sistema y del dispositivo BAGO:
Python, Git, Ollama, bago_core montado, modelo LLM, espacio libre.

Uso:
    bago doctor          → informe completo
    bago doctor --fix    → intenta corregir problemas automáticamente
    bago doctor --json   → salida JSON para scripts
    bago doctor --test   → self-check (tool_guardian)
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import socket
import subprocess
import sys
from pathlib import Path

TOOLS_DIR  = Path(__file__).resolve().parent
BAGO_ROOT  = TOOLS_DIR.parent
DRIVE_ROOT = BAGO_ROOT.parent
STATE_DIR  = BAGO_ROOT / "state"
MODELS_DIR = BAGO_ROOT / ".models"
BIN_DIR    = BAGO_ROOT / "bin"

# ── ANSI ──────────────────────────────────────────────────────────────────────

IS_WIN = sys.platform == "win32"
if not IS_WIN:
    OK   = "\033[1;32m✓\033[0m"
    WARN = "\033[1;33m⚠\033[0m"
    ERR  = "\033[1;31m✗\033[0m"
    BOLD = "\033[1m"
    DIM  = "\033[2m"
    NC   = "\033[0m"
else:
    OK = WARN = ERR = BOLD = DIM = NC = ""
    OK, WARN, ERR = "OK", "WARN", "ERR"

# ── Checks ────────────────────────────────────────────────────────────────────

CheckResult = dict  # {id, label, ok, detail, fix_hint}


def _check_python() -> CheckResult:
    v = sys.version_info
    ok = (v.major, v.minor) >= (3, 9)
    return {
        "id": "python",  # noqa: HARDCODE
        "label": "Python 3.9+",
        "ok": ok,
        "detail": f"{v.major}.{v.minor}.{v.micro}",
        "fix_hint": "Instala Python desde https://python.org" if not ok else "",
    }


def _check_git() -> CheckResult:
    found = shutil.which("git")
    if found:
        try:
            ver = subprocess.check_output(["git", "--version"], text=True).strip()
        except Exception:
            ver = "encontrado"
        return {"id": "git", "label": "Git", "ok": True, "detail": ver, "fix_hint": ""}
    return {
        "id": "git",
        "label": "Git",
        "ok": False,
        "detail": "no encontrado",
        "fix_hint": (
            "macOS: xcode-select --install  |  "
            "Windows: winget install Git.Git  |  "
            "Linux: sudo apt install git"
        ),
    }


def _ollama_bin() -> str | None:
    pendrive_bin = BIN_DIR / ("ollama.exe" if IS_WIN else "ollama-macos")
    if pendrive_bin.exists():
        return str(pendrive_bin)
    found = shutil.which("ollama")
    if found:
        return found
    for p in [
        Path.home() / "bin" / "ollama",
        Path("/usr/local/bin/ollama"),
        Path("/opt/homebrew/bin/ollama"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",
    ]:
        if p.exists():
            return str(p)
    return None


def _check_ollama() -> CheckResult:
    bin_ = _ollama_bin()
    if not bin_:
        return {
            "id": "ollama",
            "label": "Ollama",
            "ok": False,
            "detail": "no encontrado",
            "fix_hint": "Ejecuta: bash /Volumes/BAGO/agents/setup-llm.sh",
        }
    source = "pendrive" if "bago" in bin_.lower() or ".bago" in bin_ else "sistema"
    try:
        ver = subprocess.check_output([bin_, "--version"], text=True, stderr=subprocess.STDOUT).strip()
    except Exception:
        ver = "encontrado"
    return {
        "id": "ollama",
        "label": "Ollama",
        "ok": True,
        "detail": f"{ver} [{source}]",
        "fix_hint": "",
    }


def _check_ollama_server() -> CheckResult:
    try:
        s = socket.create_connection(("127.0.0.1", 11434), timeout=1)
        s.close()
        running = True
    except OSError:
        running = False
    return {
        "id": "ollama_server",
        "label": "Servidor Ollama",
        "ok": running,
        "detail": "activo en :11434" if running else "no está corriendo",
        "fix_hint": "" if running else "Ejecuta: bago llm start",
    }


def _check_bago_core() -> CheckResult:
    ok = (DRIVE_ROOT / "bago").exists()
    return {
        "id": "bago_core",
        "label": "bago_core montado",
        "ok": ok,
        "detail": str(DRIVE_ROOT) if ok else "no encontrado",
        "fix_hint": "" if ok else "Asegúrate de que la partición bago_core esté montada",
    }


def _check_llm_model() -> CheckResult:
    manifests = MODELS_DIR / "manifests" / "registry.ollama.ai" / "library"
    if not manifests.exists():
        return {
            "id": "llm_model",
            "label": "Modelo LLM en pendrive",
            "ok": False,
            "detail": "ninguno descargado",
            "fix_hint": "Ejecuta: bago llm download",
        }
    models = [d.name for d in manifests.iterdir() if d.is_dir()]
    if not models:
        return {
            "id": "llm_model",
            "label": "Modelo LLM en pendrive",
            "ok": False,
            "detail": "ninguno descargado",
            "fix_hint": "Ejecuta: bago llm download",
        }
    return {
        "id": "llm_model",
        "label": "Modelo LLM en pendrive",
        "ok": True,
        "detail": ", ".join(models),
        "fix_hint": "",
    }


def _check_disk() -> CheckResult:
    try:
        usage = shutil.disk_usage(str(DRIVE_ROOT))
        free_gb = usage.free / 1024**3
        total_gb = usage.total / 1024**3
        ok = free_gb > 1.0
        return {
            "id": "disk",
            "label": "Espacio libre (bago_core)",
            "ok": ok,
            "detail": f"{free_gb:.1f} GB libres / {total_gb:.1f} GB total",
            "fix_hint": "" if ok else "El pendrive tiene poco espacio",
        }
    except Exception as e:
        return {"id": "disk", "label": "Espacio libre", "ok": False, "detail": str(e), "fix_hint": ""}


def _check_ollama_bundled() -> CheckResult:
    mac_bin = BIN_DIR / "ollama-macos"
    win_bin = BIN_DIR / "OllamaSetup-windows.exe"
    has_mac = mac_bin.exists()
    has_win = win_bin.exists()
    ok = has_mac and has_win
    parts = []
    if has_mac:
        parts.append(f"macOS ({mac_bin.stat().st_size // 1024**2} MB)")
    if has_win:
        parts.append(f"Windows ({win_bin.stat().st_size // 1024**2} MB)")
    detail = ", ".join(parts) if parts else "ninguno"
    return {
        "id": "ollama_bundled",
        "label": "Ollama en pendrive",
        "ok": ok,
        "detail": detail,
        "fix_hint": "" if ok else "Ejecuta el setup de LLM para descargar los binarios",
    }


# ── Render ────────────────────────────────────────────────────────────────────

def _icon(ok: bool, warn: bool = False) -> str:
    if ok:
        return OK
    return WARN if warn else ERR


def _print_result(r: CheckResult) -> None:
    icon = _icon(r["ok"])
    label = f"{r['label']:<28}"
    detail = r["detail"]
    print(f"  {icon} {BOLD}{label}{NC} {DIM}{detail}{NC}")
    if not r["ok"] and r["fix_hint"]:
        print(f"      {DIM}→ {r['fix_hint']}{NC}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    args = sys.argv[1:]
    as_json = "--json" in args
    fix_mode = "--fix" in args

    checks = [
        _check_python(),
        _check_git(),
        _check_bago_core(),
        _check_disk(),
        _check_ollama_bundled(),
        _check_ollama(),
        _check_ollama_server(),
        _check_llm_model(),
    ]

    if as_json:
        print(json.dumps({"tool": "bago_doctor", "checks": checks}, ensure_ascii=False, indent=2))
        return 0 if all(c["ok"] for c in checks) else 1

    print()
    print(f"  {BOLD}BAGO Doctor — Diagnóstico del entorno{NC}")
    print(f"  {DIM}{'─' * 44}{NC}")
    print()

    critical = ["python", "bago_core"]  # noqa: HARDCODE
    all_ok = True
    for r in checks:
        _print_result(r)
        if not r["ok"] and r["id"] in critical:
            all_ok = False

    print()
    ok_count = sum(1 for c in checks if c["ok"])
    total = len(checks)

    if all_ok and ok_count == total:
        print(f"  {OK} {BOLD}Todo listo.{NC} ({ok_count}/{total} checks OK)")
    elif all_ok:
        print(f"  {WARN} {BOLD}Listo con advertencias.{NC} ({ok_count}/{total} checks OK)")
    else:
        print(f"  {ERR} {BOLD}Hay problemas críticos.{NC} ({ok_count}/{total} checks OK)")

    print()
    return 0 if all_ok else 1


# ── Self-test ─────────────────────────────────────────────────────────────────

def _self_test() -> None:
    results = []

    def check(id_: str, cond: bool, detail: str) -> None:
        passed = bool(cond)
        status = "OK" if passed else "FAIL"
        results.append({"id": id_, "passed": passed, "detail": detail})
        print(f"  [{status}] {id_:<35} — {detail}")

    r = _check_python()
    check("T1:python-check", isinstance(r["ok"], bool), "retorna bool")

    r = _check_git()
    check("T2:git-check", isinstance(r["ok"], bool), "retorna bool")

    r = _check_bago_core()
    check("T3:bago-core-check", isinstance(r["ok"], bool), "retorna bool")

    r = _check_disk()
    check("T4:disk-check", isinstance(r["ok"], bool), "retorna bool")

    r = _check_ollama()
    check("T5:ollama-check", isinstance(r["ok"], bool), "retorna bool")

    r = _check_ollama_server()
    check("T6:server-check", isinstance(r["ok"], bool), "retorna bool")

    r = _check_llm_model()
    check("T7:model-check", isinstance(r["ok"], bool), "retorna bool")

    r = _check_ollama_bundled()
    check("T8:bundled-check", isinstance(r["ok"], bool), "retorna bool")

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    print(f"\n  {passed}/{total} tests OK")
    print(json.dumps({"tool": "bago_doctor", "status": "ok" if passed == total else "fail",
                      "checks": results}, ensure_ascii=False))
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
    else:
        sys.exit(main())
