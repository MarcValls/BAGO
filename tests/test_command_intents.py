#!/usr/bin/env python3
"""
test_command_intents.py — BAGO 4.1.5
Evidencia de entrenamiento: verifica que cada frase del dataset
command_intents.json se resuelve al comando correcto.

Uso:
    python tests\test_command_intents.py            # todos los comandos
    python tests\test_command_intents.py /autopilot  # solo un comando
    python tests\test_command_intents.py --fail-only # solo los que fallan
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# ── rutas ──────────────────────────────────────────────────────────────────
BAGO_ROOT = Path(__file__).resolve().parent
CORE_PATH = BAGO_ROOT / ".bago" / "core"
DATA_PATH = CORE_PATH / "command_intents.json"

sys.path.insert(0, str(CORE_PATH))
sys.path.insert(0, str(BAGO_ROOT / ".bago" / "chat"))
sys.path.insert(0, str(BAGO_ROOT / ".bago" / "providers"))

from intent_engine import classify_command_intent, reload_command_index  # noqa: E402

# ── colores ANSI ────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
DIM    = "\033[2m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

OK   = f"{GREEN}✓{RESET}"
FAIL = f"{RED}✗{RESET}"
SKIP = f"{YELLOW}·{RESET}"

SEP = f"{DIM}{'─' * 68}{RESET}"


def _load_data() -> dict:
    if not DATA_PATH.exists():
        print(f"{RED}ERROR:{RESET} No se encontró {DATA_PATH}")
        sys.exit(1)
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def _test_phrase(phrase: str, expected_cmd: str) -> tuple[bool, str | None]:
    """Llama al engine y devuelve (passed, got)."""
    got = classify_command_intent(phrase)
    return (got == expected_cmd), got


def _run(filter_cmd: str | None = None, fail_only: bool = False) -> int:
    """Ejecuta todos los tests. Retorna número de fallos."""
    reload_command_index()
    data = _load_data()
    commands = data.get("commands", {})

    total = 0
    passed = 0
    failed = 0
    skipped_cmds = 0

    t_start = time.perf_counter()

    for cmd, info in commands.items():
        if filter_cmd and cmd != filter_cmd:
            skipped_cmds += 1
            continue

        phrases = info.get("phrases", [])
        desc    = info.get("description", "")
        wizard  = info.get("wizard", False)
        wiz_tag = f" {CYAN}[wizard]{RESET}" if wizard else ""

        cmd_passed = 0
        cmd_failed = 0
        failures: list[tuple[str, str | None]] = []

        for phrase in phrases:
            total += 1
            ok, got = _test_phrase(phrase, cmd)
            if ok:
                passed += 1
                cmd_passed += 1
            else:
                failed += 1
                cmd_failed += 1
                failures.append((phrase, got))

        # Cabecera del comando
        rate = cmd_passed / len(phrases) * 100 if phrases else 0
        rate_color = GREEN if rate == 100 else (YELLOW if rate >= 70 else RED)
        header = (
            f"{BOLD}{cmd}{RESET}{wiz_tag}  "
            f"{rate_color}{rate:.0f}%{RESET}  "
            f"{DIM}({cmd_passed}/{len(phrases)}){RESET}"
        )
        if not fail_only or cmd_failed:
            print(f"\n{SEP}")
            print(f"  {header}")
            print(f"  {DIM}{desc}{RESET}")

        # Frases que fallan (siempre se muestran)
        if failures and not fail_only:
            for phrase, got in failures:
                got_str = f"'{got}'" if got else "None"
                print(f"    {FAIL} {DIM}'{phrase}'{RESET}  →  got {RED}{got_str}{RESET}")
        elif failures and fail_only:
            print(f"\n{SEP}")
            print(f"  {header}")
            print(f"  {DIM}{desc}{RESET}")
            for phrase, got in failures:
                got_str = f"'{got}'" if got else "None"
                print(f"    {FAIL} {DIM}'{phrase}'{RESET}  →  got {RED}{got_str}{RESET}")

        # Muestra algunas frases que pasan (solo si no es fail-only)
        if not fail_only and cmd_passed:
            shown = [p for p in phrases if p not in [f for f, _ in failures]][:3]
            for phrase in shown:
                print(f"    {OK} {DIM}'{phrase}'{RESET}")
            remaining = cmd_passed - len(shown)
            if remaining > 0:
                print(f"    {SKIP} {DIM}… y {remaining} más pasan{RESET}")

    elapsed = time.perf_counter() - t_start

    # ── Resumen final ──────────────────────────────────────────────────────
    print(f"\n{SEP}")
    pct = passed / total * 100 if total else 0
    color = GREEN if pct == 100 else (YELLOW if pct >= 80 else RED)
    print(f"\n  {BOLD}RESULTADO{RESET}  "
          f"{color}{pct:.1f}%{RESET}  "
          f"{passed}/{total} frases  "
          f"{DIM}({elapsed*1000:.0f} ms){RESET}")

    if failed:
        print(f"  {RED}{failed} fallos{RESET} — revisa las frases marcadas con {FAIL}")
    else:
        print(f"  {GREEN}Todas las frases se resuelven correctamente.{RESET}")

    if skipped_cmds:
        print(f"  {DIM}{skipped_cmds} comandos omitidos por filtro.{RESET}")

    print()
    return failed


# ── Tabla de ejemplos reales (timeout demo) ────────────────────────────────
TIMEOUT_DEMO_CASES: list[tuple[str, str]] = [
    # (frase de usuario, comando esperado)
    ("bago autonomo y ejecuta el plan", "/autopilot"),
    ("EJECUTA EL PLAN", "/autopilot"),
    ("toma el control", "/autopilot"),
    ("ya tu solo", "/autopilot"),
    ("quiero gpt", "/switch"),
    ("modelo mas potente", "/switch"),
    ("por donde empezamos a atacar", "/plan"),
    ("BAGO APRENDE DE NOSOTROS", "/evolve"),
    ("TENGO UNA API KEY", "/credentials set"),
    ("mete la api key", "/credentials set"),
    ("checkpoint", "/save"),
    ("AYUDA", "/help"),
    ("COMO ESTAMOS", "/status"),
    ("nos vemos", "/quit"),
    ("abre el menu", "/"),
]


def _run_demo() -> int:
    """Ejecuta solo los casos de demostración más representativos."""
    reload_command_index()
    print(f"\n{BOLD}DEMO — Frases realistas del usuario → comando BAGO{RESET}")
    print(SEP)

    failed = 0
    for phrase, expected in TIMEOUT_DEMO_CASES:
        ok, got = _test_phrase(phrase, expected)
        icon = OK if ok else FAIL
        got_str = f"{GREEN}{got}{RESET}" if ok else f"{RED}{got or 'None'}{RESET}"
        print(f"  {icon} {CYAN}\"{phrase}\"{RESET}")
        print(f"       → {got_str}  {DIM}(esperado: {expected}){RESET}")
        if not ok:
            failed += 1

    print(SEP)
    total = len(TIMEOUT_DEMO_CASES)
    color = GREEN if not failed else RED
    print(f"\n  {color}{total - failed}/{total} correctos{RESET}\n")
    return failed


# ── Tabla de puntos de timeout por wizard ──────────────────────────────────
TIMEOUT_POINTS: list[dict] = [
    {
        "wizard": "_credential_wizard",
        "command": "/credentials set",
        "timeout_s": 60,
        "input_prompt": "provider/key = ",
        "timeout_action": "Timeout: ningún valor introducido. Wizard cerrado.",
    },
    {
        "wizard": "_config_wizard",
        "command": "/config set",
        "timeout_s": 60,
        "input_prompt": "key = ",
        "timeout_action": "Timeout: ningún valor introducido. Wizard cerrado.",
    },
    {
        "wizard": "_switch_wizard / startup",
        "command": "/switch + startup interactivo",
        "timeout_s": 30,
        "input_prompt": "Elige: ",
        "timeout_action": "Timeout: continúa con el provider actual.",
    },
    {
        "wizard": "_interactive_startup",
        "command": "Inicio de sesión",
        "timeout_s": 15,
        "input_prompt": "Presiona Enter para continuar...",
        "timeout_action": "Timeout: continúa automáticamente.",
    },
]


def _print_timeout_table() -> None:
    print(f"\n{BOLD}PUNTOS DE TIMEOUT EN WIZARDS{RESET}")
    print(SEP)
    for pt in TIMEOUT_POINTS:
        print(f"  {CYAN}{pt['wizard']}{RESET}")
        print(f"    Comando   : {pt['command']}")
        print(f"    Timeout   : {BOLD}{pt['timeout_s']}s{RESET}")
        print(f"    Prompt    : \"{pt['input_prompt']}\"")
        print(f"    Si expira : {YELLOW}{pt['timeout_action']}{RESET}")
        print()


# ── Entry point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    args = sys.argv[1:]

    if "--demo" in args:
        sys.exit(_run_demo())

    if "--timeouts" in args:
        _print_timeout_table()
        sys.exit(0)

    fail_only = "--fail-only" in args
    filter_cmd = next((a for a in args if a.startswith("/") and a != "--fail-only"), None)

    _run_demo()
    _print_timeout_table()
    n_fail = _run(filter_cmd=filter_cmd, fail_only=fail_only)
    sys.exit(0 if n_fail == 0 else 1)
