#!/usr/bin/env python3
"""intent_router.py — Interpreta lenguaje natural y ejecuta tools BAGO.

Uso:
    python3 intent_router.py "mi código tiene passwords hardcodeados"
    python3 intent_router.py --resolve --json "mi código tiene passwords hardcodeados"
    python3 intent_router.py --rewrite "algo va mal con el framework"
    python3 intent_router.py --dry-run "secretos en el código"
    python3 intent_router.py --list-intents
    python3 intent_router.py --test
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import importlib.util
import json
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from intent_catalog import INTENTS, INTENT_VOICES

BAGO_ROOT = Path(__file__).parent.parent
TOOLS_DIR = Path(__file__).parent
PROJECT_ROOT = BAGO_ROOT.parent
BAGO_SCRIPT = PROJECT_ROOT / "bago"


try:
    _bp_spec = importlib.util.spec_from_file_location(
        "bago_presence", TOOLS_DIR / "bago_presence.py"
    )
    _bp_mod = importlib.util.module_from_spec(_bp_spec)  # type: ignore
    _bp_spec.loader.exec_module(_bp_mod)  # type: ignore
    bp = _bp_mod.bp
except Exception:
    class _NullBP:
        def __getattr__(self, _):
            return lambda *a, **k: None
    bp = _NullBP()  # type: ignore


@lru_cache(maxsize=1)
def _load_intents() -> list:
    try:
        from bago_config import load_config
        data = load_config("intents_catalog", fallback=None)
        if data and isinstance(data.get("intents"), list):
            merged = {intent.get("id"): intent for intent in INTENTS}
            for intent in data["intents"]:
                if isinstance(intent, dict) and intent.get("id"):
                    merged[intent["id"]] = intent
            return list(merged.values())
    except Exception:
        pass
    return INTENTS


def _cap_activate_voices(intent_id: str, task_desc: str, dry_run: bool = False) -> None:
    voices = INTENT_VOICES.get(intent_id, [])
    if not voices:
        return
    try:
        vc_path = Path(__file__).parent / "voice_conductor.py"
        if not vc_path.exists():
            return
        spec = importlib.util.spec_from_file_location("voice_conductor", str(vc_path))
        mod = importlib.util.module_from_spec(spec)  # type: ignore
        spec.loader.exec_module(mod)  # type: ignore
        cycle = mod.VoiceConductor()
        activated = cycle.activate_voices(task=task_desc, available_roles=voices)
        if activated and not dry_run:
            gate_state = cycle._state.get("gate", "PUERTA_CERRADA")
            bp.cap_voices(activated, gate=gate_state)
    except Exception:
        pass


def tokenize(text: str) -> list:
    return re.findall(r"\w+", text.lower())


def score_intent(query: str, intent: dict) -> int:
    query_lower = query.lower()
    tokens = tokenize(query_lower)
    score = 0
    for trigger in intent["triggers"]:
        if trigger in query_lower:
            score += 20
        elif len(trigger) >= 6 and any(tok.startswith(trigger[:5]) for tok in tokens if len(trigger) >= 5):
            score += 10
        elif len(trigger) >= 7 and any(trigger[:6] in tok for tok in tokens):
            score += 5
    return score


def identify_intents(query: str, top_n: int = 3) -> list:
    scored = []
    for intent in _load_intents():
        score = score_intent(query, intent)
        if score > 0:
            scored.append((score, intent))
    scored.sort(key=lambda item: -item[0])
    return scored[:top_n]


def _confidence_code(score: int) -> str:
    return "INT-I001" if score >= 20 else "INT-I002"


def _confidence_value(score: int) -> float:
    return round(min(0.99, max(0.05, score / 80)), 2)


def _canonical_rewrite(intent: dict) -> str:
    tools = " -> ".join(intent.get("tools", []))
    return f"{intent['name']}: {intent['description']} [{tools}]"


def resolve_intent(query: str, top_n: int = 3) -> dict:
    intents = identify_intents(query, top_n=top_n)
    if not intents:
        return {
            "matched": False,
            "code": "INT-W001",
            "original": query,
            "rewrite": "",
            "intent": None,
            "confidence": 0.0,
            "requires_confirmation": False,
            "risk": "unknown",
            "tools": [],
            "alternatives": [],
        }

    score, best = intents[0]
    alternatives = [
        {
            "intent": alt["id"],
            "name": alt["name"],
            "score": alt_score,
            "confidence": _confidence_value(alt_score),
            "tools": alt.get("tools", []),
        }
        for alt_score, alt in intents[1:]
    ]
    destructive = bool(best.get("destructive"))
    return {
        "matched": True,
        "code": _confidence_code(score),
        "original": query,
        "rewrite": _canonical_rewrite(best),
        "intent": best["id"],
        "name": best["name"],
        "description": best["description"],
        "score": score,
        "confidence": _confidence_value(score),
        "requires_confirmation": destructive,
        "risk": "mutating" if destructive else "read_only",
        "tools": best.get("tools", []),
        "alternatives": alternatives,
    }


def print_resolved_intent(plan: dict, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return
    if not plan.get("matched"):
        print(f"  [{plan['code']}] No identifiqué una intención clara.")
        print(f"  Original: {plan['original']}")
        return
    print(f"  [{plan['code']}] {plan['rewrite']}")
    print(f"  intención: {plan['intent']}  confianza: {plan['confidence']}")
    print(f"  tools: {' -> '.join(plan['tools'])}")
    if plan.get("requires_confirmation"):
        print("  requiere confirmación: sí")
    if plan.get("alternatives"):
        print("  alternativas:")
        for alt in plan["alternatives"]:
            print(f"    - {alt['intent']} ({alt['confidence']}): {' -> '.join(alt['tools'])}")


def run_tool(cmd: str, extra_args: list | None = None, dry_run: bool = False) -> tuple:
    if dry_run:
        return 0, f"[DRY-RUN] bago {cmd}"
    try:
        full_cmd = [str(BAGO_SCRIPT), cmd] + (extra_args or [])
        result = subprocess.run(
            full_cmd,
            capture_output=True, text=True,
            cwd=str(PROJECT_ROOT), timeout=60,
        )
        return result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return 1, f"[INT-E001] Timeout en: bago {cmd}"
    except Exception as exc:
        return 1, f"[INT-E001] Error ejecutando bago {cmd}: {exc}"


def execute_intent(intent: dict, dry_run: bool = False, confirm_destructive: bool = True) -> int:
    if intent.get("destructive") and confirm_destructive and not dry_run:
        print(f"\n  Esta acción es destructiva: {intent['description']}")
        print("  Ejecuta con --yes para confirmar, o --dry-run para previsualizar.")
        return 1

    errors = 0
    for tool_cmd in intent["tools"]:
        print(f"\n  bago {tool_cmd}")
        print("  " + "─" * 50)
        rc, output = run_tool(tool_cmd, dry_run=dry_run)
        if output.strip():
            for line in output.strip().splitlines():
                print(f"  {line}")
        if rc != 0 and not dry_run:
            print(f"\n  [INT-E001] bago {tool_cmd} salió con código {rc}")
            errors += 1
    return errors


def cmd_route(query: str, dry_run: bool = False, yes: bool = False, verbose: bool = False):
    intents = identify_intents(query)
    if not intents:
        print(f"\n  [INT-W001] No identifiqué una intención clara en: '{query}'")
        print("  Prueba: bago intent --list-intents")
        return 1

    score, best = intents[0]
    confidence = "INT-I001" if score >= 20 else "INT-I002"
    bp.act("MAESTRO", f"recibiendo: {query[:60]}")
    bp.act("ORQUESTADOR", f"[{confidence}] intención: {best['name']}")
    bp.think(best["description"])
    bp.think(f"tools: {' → '.join(best['tools'])}")

    if len(intents) > 1 and verbose:
        print("\n  Alternativas:")
        for score_alt, intent in intents[1:]:
            print(f"    • {intent['name']} (score={score_alt})")

    _cap_activate_voices(best.get("id", ""), query, dry_run=dry_run)
    execute_intent(best, dry_run=dry_run, confirm_destructive=not yes)
    return 0


def cmd_list_intents():
    intents = _load_intents()
    print(f"\n  BAGO — Intenciones reconocidas ({len(intents)})")
    print("  " + "─" * 56)
    for intent in intents:
        tools_str = " + ".join(intent["tools"])
        destructive = " !  " if intent.get("destructive") else "    "
        print(f"  {destructive}{intent['name']:30s}  [{tools_str}]")
        sample = ", ".join(intent["triggers"][:4])
        print(f"       Palabras clave: {sample}…")
        print()


def run_tests():
    from intent_router_tests import run_tests as _run_tests
    return _run_tests({
        "identify_intents": identify_intents,
        "score_intent": score_intent,
        "resolve_intent": resolve_intent,
        "load_intents": _load_intents,
    })


def main() -> int:
    args = sys.argv[1:]
    if not args or "--help" in args or "-h" in args:
        print(__doc__)
        return 0
    if "--test" in args:
        return run_tests()
    if "--list-intents" in args:
        cmd_list_intents()
        return 0

    dry_run = "--dry-run" in args
    yes = "--yes" in args
    verbose = "--verbose" in args or "-v" in args
    resolve_only = any(flag in args for flag in ("--resolve", "--rewrite", "--plan", "--json"))
    as_json = "--json" in args
    query_parts = [arg for arg in args if not arg.startswith("--")]
    if not query_parts:
        print("  Describe el problema: bago intent 'mi código tiene secretos'")
        return 1

    query = " ".join(query_parts)
    if resolve_only:
        plan = resolve_intent(query)
        print_resolved_intent(plan, as_json=as_json)
        return 0 if plan.get("matched") else 1
    return cmd_route(query, dry_run=dry_run, yes=yes, verbose=verbose)


if __name__ == "__main__":
    raise SystemExit(main())
