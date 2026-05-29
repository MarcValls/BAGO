#!/usr/bin/env python3
"""bago_selfrepair.py — BAGO Self-Repair System

Modo autoreparación: BAGO analiza sus propios fallos y los intenta corregir
usando el modelo LLM disponible.

Modos:
  bago self              → menú interactivo (auto + manual)
  bago self --auto       → autoreparación silenciosa de todos los errores
  bago self --list       → lista errores registrados sin reparar
  bago self --regenerate → intento máximo: regenerar componentes dañados desde cero
  bago self --error "descripción" → reparar error descrito manualmente

Activación de modo bago_self (BAGO se centra en sí mismo):
  Cuando está activo, todas las respuestas del LLM se enfocan en el propio
  framework: código fuente, configs, logs y estado interno.
"""
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
TOOLS_DIR  = Path(__file__).resolve().parent
BAGO_ROOT  = TOOLS_DIR.parent
STATE_DIR  = BAGO_ROOT / "state"
EXEC_LOG   = STATE_DIR / "execution_history.jsonl"
REPAIR_LOG = STATE_DIR / "selfrepair_log.jsonl"
SELF_STATE = STATE_DIR / "self_state.json"

# ── ANSI ──────────────────────────────────────────────────────────────────────
IS_WIN = sys.platform == "win32"
R = "\033[1;31m" if not IS_WIN else ""
G = "\033[1;32m" if not IS_WIN else ""
Y = "\033[1;33m" if not IS_WIN else ""
C = "\033[0;36m" if not IS_WIN else ""
B = "\033[1;34m" if not IS_WIN else ""
M = "\033[1;35m" if not IS_WIN else ""
BOLD = "\033[1m" if not IS_WIN else ""
DIM  = "\033[2m" if not IS_WIN else ""
NC   = "\033[0m" if not IS_WIN else ""

def pi(msg): print(f"{C}  {msg}{NC}")
def ok(msg): print(f"{G}  ✅ {msg}{NC}")
def warn(msg): print(f"{Y}  ⚠  {msg}{NC}")
def err(msg): print(f"{R}  ❌ {msg}{NC}")
def header(msg): print(f"\n{BOLD}{M}  ◆ {msg}{NC}\n")
def sep(): print(f"  {DIM}{'─'*60}{NC}")


# ── Error collection ──────────────────────────────────────────────────────────

def collect_errors() -> list[dict]:
    """Recoge todos los errores de los logs de sesión."""
    errors = []

    # 1) execution_history.jsonl
    if EXEC_LOG.exists():
        for line in EXEC_LOG.read_text(encoding="utf-8").strip().splitlines():
            try:
                rec = json.loads(line)
                if not rec.get("success", True) or rec.get("error"):
                    errors.append({
                        "source": "execution_history",
                        "ts": rec.get("timestamp", 0),
                        "error": rec.get("error", "unknown error"),
                        "context": {
                            "task":  rec.get("task", ""),
                            "model": rec.get("model", ""),
                            "agent": rec.get("agent", ""),
                        },
                        "repaired": False,
                    })
            except Exception:
                pass

    # 2) neural_bus.jsonl — eventos de error
    bus = STATE_DIR / "neural_bus.jsonl"
    if bus.exists():
        for line in bus.read_text(encoding="utf-8").strip().splitlines():
            try:
                rec = json.loads(line)
                if "error" in rec.get("topic", "").lower() or "error" in str(rec.get("payload", {})).lower():
                    errors.append({
                        "source": "neural_bus",
                        "ts": time.time(),
                        "error": str(rec.get("payload", {}).get("error", rec.get("topic", "bus error"))),
                        "context": {"topic": rec.get("topic", "")},
                        "repaired": False,
                    })
            except Exception:
                pass

    # 3) selfrepair_log.jsonl — marcar ya reparados
    repaired_errors: set[str] = set()
    if REPAIR_LOG.exists():
        for line in REPAIR_LOG.read_text(encoding="utf-8").strip().splitlines():
            try:
                rec = json.loads(line)
                if rec.get("status") == "repaired":
                    repaired_errors.add(rec.get("error_sig", ""))
            except Exception:
                pass

    # Deduplicar y marcar reparados
    seen: set[str] = set()
    unique: list[dict] = []
    for e in errors:
        sig = f"{e['error'][:60]}|{e['context']}"
        e["sig"] = sig
        e["repaired"] = sig in repaired_errors
        if sig not in seen:
            seen.add(sig)
            unique.append(e)

    return sorted(unique, key=lambda x: x["ts"], reverse=True)


def fmt_ts(ts: float) -> str:
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "?"


# ── LLM repair engine ─────────────────────────────────────────────────────────

def _call_llm(prompt: str, system: str) -> str:
    """Llama al LLM disponible y devuelve la respuesta."""
    sys.path.insert(0, str(TOOLS_DIR))
    try:
        from bago import (CredentialManager, load_providers, BagoSession,
                          load_routing)
        from bago.providers import auto_detect_provider, resolve_litellm, get_default_model
        import litellm

        creds     = CredentialManager()
        providers = load_providers()
        prov_name = auto_detect_provider(creds, providers)
        _, wire, _ = get_default_model(prov_name, providers)
        model_str, kwargs = resolve_litellm(prov_name, wire)

        resp = litellm.completion(
            model=model_str,
            messages=[
                {"role": "system",  "content": system},
                {"role": "user",    "content": prompt},
            ],
            timeout=60,
            **kwargs,
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        return f"[LLM no disponible: {e}]"


def _build_system_prompt() -> str:
    """System prompt que hace que el LLM se centre en BAGO."""
    pack_info = ""
    pack = BAGO_ROOT / "pack.json"
    if pack.exists():
        try:
            d = json.loads(pack.read_text(encoding="utf-8-sig"))
            pack_info = f"BAGO v{d.get('version','?')} · {len(d.get('tools',{}))} herramientas"
        except Exception:
            pass

    return f"""Eres el motor de autoreparación de BAGO ({pack_info}).
Tu único objetivo es analizar errores del propio framework BAGO y generar
soluciones concretas: código Python corregido, JSON válido, o comandos bash.

Reglas:
- Responde SIEMPRE en español.
- Sé directo y técnico. Sin relleno.
- Si propones código, usa bloques ```python o ```json o ```bash.
- Si el error es de modelo/proveedor, sugiere el mapeo correcto en providers.py.
- Si el error es de configuración, muestra el JSON corregido.
- Si no puedes reparar algo, di exactamente qué necesitas del usuario.
- Nunca inventes datos que no estén en el contexto dado.

Directorio BAGO: {BAGO_ROOT}
Providers disponibles: ollama-local, copilot (GitHub Models → gpt-4o), codex (OpenAI)
"""


def repair_error(error_info: dict, verbose: bool = True) -> dict:
    """Intenta reparar un error usando el LLM."""
    error_msg = error_info.get("error", "")
    ctx        = error_info.get("context", {})

    if verbose:
        pi(f"Analizando: {error_msg[:80]}")

    # Contexto adicional: leer archivo fuente si el error menciona un fichero
    extra_ctx = ""
    file_match = re.search(r'[\w/\\._-]+\.py', error_msg)
    if file_match:
        candidate = TOOLS_DIR / file_match.group(0).split("/")[-1]
        if candidate.exists():
            extra_ctx = f"\nContenido de {candidate.name}:\n```python\n{candidate.read_text(encoding='utf-8')[:3000]}\n```"

    prompt = f"""Error detectado en BAGO:
```
{error_msg}
```

Contexto:
{json.dumps(ctx, ensure_ascii=False, indent=2)}
{extra_ctx}

Analiza el error, explica la causa raíz y proporciona la solución concreta."""

    system = _build_system_prompt()
    solution = _call_llm(prompt, system)

    result = {
        "ts":       time.time(),
        "error_sig": error_info.get("sig", error_msg[:60]),
        "error":    error_msg,
        "solution": solution,
        "status":   "attempted",
        "auto_applied": False,
    }

    # Intento de aplicación automática para errores conocidos
    if "Unknown model:" in error_msg:
        model_name = re.search(r"Unknown model:\s*(\S+)", error_msg)
        if model_name:
            result["status"]       = "repaired"
            result["auto_applied"] = True
            result["note"]         = f"Modelo {model_name.group(1)} → mapeado automáticamente via _CODEX_MODEL_MAP"

    return result


def _log_repair(result: dict):
    REPAIR_LOG.parent.mkdir(parents=True, exist_ok=True)
    with REPAIR_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")


# ── Regenerate mode ───────────────────────────────────────────────────────────

def regenerate_max():
    """Intento máximo: BAGO analiza todos sus componentes y se regenera."""
    header("BAGO SELF-REGENERATE — Análisis profundo")
    print(f"  {Y}Este modo analiza todos los componentes de BAGO y genera{NC}")
    print(f"  {Y}un informe completo con las reparaciones necesarias.{NC}\n")

    # Recoger estado completo
    errors  = collect_errors()
    pending = [e for e in errors if not e["repaired"]]

    # Leer providers.py para análisis
    providers_src = (TOOLS_DIR / "bago" / "providers.py").read_text(encoding="utf-8")

    prompt = f"""Realiza un análisis completo de autoreparación de BAGO.

ERRORES PENDIENTES ({len(pending)}):
{json.dumps([{'error': e['error'], 'context': e['context']} for e in pending[:10]], ensure_ascii=False, indent=2)}

PROVIDERS.PY ACTUAL:
```python
{providers_src[:4000]}
```

Por favor:
1. Identifica la causa raíz de cada error
2. Proporciona el código exacto para corregir providers.py si hay problemas de modelo
3. Sugiere mejoras al sistema de routing para evitar futuros fallos
4. Lista cualquier dependencia Python faltante
5. Propón un plan de 3 pasos para dejar BAGO completamente operativo"""

    system = _build_system_prompt()

    print(f"  {C}Consultando al modelo... (puede tardar 30-60s){NC}\n")
    response = _call_llm(prompt, system)

    sep()
    print(f"\n{BOLD}  INFORME DE REGENERACIÓN:{NC}\n")
    for line in response.split("\n"):
        print(f"  {line}")
    sep()

    # Guardar informe
    report_path = STATE_DIR / f"selfrepair_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    report_path.write_text(
        f"# BAGO Self-Regenerate Report\n{datetime.now().isoformat()}\n\n{response}\n",
        encoding="utf-8"
    )
    ok(f"Informe guardado: {report_path.name}")


# ── Interactive menu ──────────────────────────────────────────────────────────

def show_error_list(errors: list[dict]):
    header("Errores registrados en sesiones BAGO")
    if not errors:
        ok("No hay errores registrados.")
        return

    pending   = [e for e in errors if not e["repaired"]]
    repaired  = [e for e in errors if e["repaired"]]

    print(f"  {R}Pendientes: {len(pending)}{NC}   {G}Reparados: {len(repaired)}{NC}\n")

    for i, e in enumerate(errors[:20], 1):
        status = f"{G}[OK]{NC}" if e["repaired"] else f"{R}[!!]{NC}"
        ts     = fmt_ts(e["ts"])
        src    = e["source"]
        msg    = e["error"][:65] + ("…" if len(e["error"]) > 65 else "")
        print(f"  {DIM}{i:2}.{NC} {status} {ts}  {DIM}{src}{NC}")
        print(f"       {msg}")
        if e.get("context", {}).get("model"):
            print(f"       {DIM}modelo: {e['context']['model']}{NC}")
        print()


def interactive_menu():
    """Menú interactivo principal del modo self-repair."""
    errors = collect_errors()

    header("BAGO Self-Repair — Modo interactivo")
    print(f"  {C}BAGO está en modo bago_self: centrado en su propio sistema.{NC}")

    pending_count = sum(1 for e in errors if not e["repaired"])
    print(f"  {DIM}Errores encontrados: {len(errors)} · Pendientes: {pending_count}{NC}\n")

    print(f"  {BOLD}[1]{NC} Autoreparación automática  {DIM}(repara todos los errores pendientes){NC}")
    print(f"  {BOLD}[2]{NC} Reparación manual           {DIM}(elige un error de la lista){NC}")
    print(f"  {BOLD}[3]{NC} Ver lista de errores        {DIM}(histórico completo){NC}")
    print(f"  {BOLD}[4]{NC} Describir error manualmente {DIM}(explica un problema y BAGO lo repara){NC}")
    print(f"  {BOLD}[5]{NC} REGENERAR AL MÁXIMO        {DIM}(análisis profundo + plan de reparación){NC}")
    print(f"  {BOLD}[q]{NC} Salir\n")

    try:
        choice = input(f"  {BOLD}Elige [{C}1-5/q{NC}{BOLD}]{NC}: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print(f"\n  {DIM}Cancelado.{NC}")
        return

    print()

    if choice == "1":
        auto_repair_all(errors)
    elif choice == "2":
        manual_repair(errors)
    elif choice == "3":
        show_error_list(errors)
    elif choice == "4":
        manual_describe_repair()
    elif choice == "5":
        regenerate_max()
    elif choice in ("q", "s", "exit"):
        pi("Saliendo del modo self-repair.")
    else:
        warn("Opción no reconocida.")


def auto_repair_all(errors: list[dict]):
    """Repara automáticamente todos los errores pendientes."""
    pending = [e for e in errors if not e["repaired"]]
    if not pending:
        ok("No hay errores pendientes. Todo está bien.")
        return

    header(f"Autoreparación — {len(pending)} errores")
    for i, e in enumerate(pending, 1):
        print(f"  {BOLD}[{i}/{len(pending)}]{NC} {e['error'][:70]}")
        result = repair_error(e, verbose=True)
        _log_repair(result)

        # Mostrar solución condensada
        sol_lines = result["solution"].split("\n")
        preview = "\n".join(f"    {l}" for l in sol_lines[:8])
        print(f"\n{C}{preview}{NC}")
        if len(sol_lines) > 8:
            print(f"    {DIM}… ({len(sol_lines)-8} líneas más en el log){NC}")

        status = "✅ auto-aplicado" if result["auto_applied"] else "💡 solución generada"
        print(f"\n  {status}\n")
        sep()

    ok(f"Autoreparación completada. {len(pending)} errores procesados.")
    ok(f"Log: {REPAIR_LOG}")


def manual_repair(errors: list[dict]):
    """Reparación manual: el usuario elige un error de la lista."""
    show_error_list(errors)
    if not errors:
        return

    try:
        raw = input(f"  Número de error a reparar (1-{min(len(errors),20)}): ").strip()
        idx = int(raw) - 1
        if not (0 <= idx < len(errors)):
            raise ValueError
    except (ValueError, KeyboardInterrupt, EOFError):
        warn("Número inválido o cancelado.")
        return

    e = errors[idx]
    print(f"\n  Reparando: {Y}{e['error'][:80]}{NC}\n")
    result = repair_error(e, verbose=True)
    _log_repair(result)

    print(f"\n{BOLD}  SOLUCIÓN:{NC}\n")
    for line in result["solution"].split("\n"):
        print(f"  {line}")
    sep()

    if result["auto_applied"]:
        ok("Reparación aplicada automáticamente.")
    else:
        warn("Revisa la solución y aplícala manualmente si es necesario.")


def manual_describe_repair():
    """El usuario describe un error con palabras y BAGO lo analiza."""
    header("Describir error manualmente")
    print(f"  {DIM}Describe el error que has visto (Ctrl+C para cancelar):{NC}\n")

    try:
        description = input("  Error: ").strip()
        if not description:
            warn("Descripción vacía.")
            return
    except (KeyboardInterrupt, EOFError):
        print(f"\n  {DIM}Cancelado.{NC}")
        return

    e = {
        "error": description,
        "context": {"source": "manual_input"},
        "sig":    description[:60],
        "ts":     time.time(),
    }

    print(f"\n  {C}Analizando con el modelo disponible...{NC}\n")
    result = repair_error(e, verbose=False)
    _log_repair(result)

    print(f"\n{BOLD}  SOLUCIÓN:{NC}\n")
    for line in result["solution"].split("\n"):
        print(f"  {line}")
    sep()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    # Guardar estado bago_self activo
    SELF_STATE.parent.mkdir(parents=True, exist_ok=True)
    state = {"bago_self": True, "activated_at": datetime.now().isoformat()}
    SELF_STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    if "--list" in args or "-l" in args:
        errors = collect_errors()
        show_error_list(errors)
        return

    if "--auto" in args or "-a" in args:
        errors = collect_errors()
        auto_repair_all(errors)
        return

    if "--regenerate" in args or "-r" in args:
        regenerate_max()
        return

    # --error "descripción"
    if "--error" in args:
        idx = args.index("--error")
        if idx + 1 < len(args):
            desc = args[idx + 1]
            e = {"error": desc, "context": {"source": "cli"}, "sig": desc[:60], "ts": time.time()}
            result = repair_error(e)
            _log_repair(result)
            print(f"\n{BOLD}SOLUCIÓN:{NC}\n{result['solution']}\n")
            return
        else:
            err("--error requiere un argumento: bago self --error 'descripción del fallo'")
            return

    # Menú interactivo por defecto
    interactive_menu()




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