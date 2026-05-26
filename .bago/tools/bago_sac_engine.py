#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bago_sac_engine.py — Motor de Superficie Activa por Condición (R-PROD-06).

Implementa el principio "Pit of Success": cuando el entorno ya cumple las
precondiciones de una herramienta, BAGO lo detecta y sugiere el comando exacto.

Garantías:
- stdlib-only, cero dependencias externas
- < 100ms (timeout defensivo en git, lectura defensiva de JSON)
- No bloquea: siempre devuelve aunque todo falle
- No cambia exit codes: solo imprime en stderr (solo si isatty)
- Anti-fatiga: locks en .bago/state/sac_locks/ con TTL configurable
- Anti-ciclo: respeta BAGO_SAC_DEPTH (máx. 1 sugerencia por cadena)
- BAGO_NO_SAC=1 silencia todo

Uso desde otros módulos:
    from bago_sac_engine import sac_suggest

    # Al final de tu script, DESPUÉS de calcular exit_code:
    sac_suggest("bago commit", exit_code=exit_code)

Condiciones registradas por trigger_point:
    "bago start"    → .py modificados sin auditar
    "bago commit"   → .py staged sin audit reciente
    "bago pre-push" → health score < 70
    "bago done"     → sprint ≥ 5 tareas done sin cosecha
    "bago cosecha"  → sesión sin evidencia de tests
    "bago health"   → health score < 60
    "bago heal"     → post-reparación
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

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

# ── Configuración ─────────────────────────────────────────────────────────────

LOCK_TTL_SECONDS = 4 * 3600  # 4 horas
MAX_SUGGESTIONS_PER_RUN = 1   # anti-ciclo: máximo 1 sugerencia por invocación
_BAGO_ROOT = Path(__file__).resolve().parents[1]   # .bago/
_PROJECT_ROOT = _BAGO_ROOT.parent                  # raíz del repo
_LOCK_DIR = _BAGO_ROOT / "state" / "sac_locks"
_STATE_FILE = _BAGO_ROOT / "state" / "global_state.json"
_SHOWN_THIS_RUN: list[str] = []  # anti-ciclo dentro de la misma invocación


class Suggestion(NamedTuple):
    trigger: str         # "bago commit"
    condition_id: str    # "staged_py_without_ast_audit"
    tool: str            # "bago audit ast"
    cmd: str             # comando exacto a ejecutar
    reason: str          # descripción breve
    min_exit_code: int   # solo sugerir si exit_code <= este valor (0=solo éxito, 99=siempre)
    max_exit_code: int   # solo sugerir si exit_code >= este valor


# ── Catálogo de sugerencias ────────────────────────────────────────────────────

_CATALOG: list[Suggestion] = [
    Suggestion(
        trigger="bago start",
        condition_id="start_py_modified",
        tool="bago audit ast",
        cmd="bago audit ast .",
        reason="hay archivos Python modificados sin analizar",
        min_exit_code=0, max_exit_code=99,
    ),
    Suggestion(
        trigger="bago commit",
        condition_id="commit_py_staged_no_audit",
        tool="bago audit ast",
        cmd="bago audit ast .",
        reason="hay archivos .py staged sin análisis AST reciente",
        min_exit_code=0, max_exit_code=0,  # solo sugerir si commit pasó
    ),
    Suggestion(
        trigger="bago pre-push",
        condition_id="push_health_low",
        tool="bago heal",
        cmd="bago heal",
        reason="health score < 70 antes de publicar",
        min_exit_code=0, max_exit_code=99,
    ),
    Suggestion(
        trigger="bago done",
        condition_id="done_sprint_no_cosecha",
        tool="bago cosecha",
        cmd="bago cosecha",
        reason="tienes ≥ 5 tareas cerradas sin haber ejecutado cosecha",
        min_exit_code=0, max_exit_code=99,
    ),
    Suggestion(
        trigger="bago cosecha",
        condition_id="cosecha_no_test_evidence",
        tool="bago audit commit",
        cmd="bago audit commit",
        reason="sin evidencia de tests registrada en esta sesión",
        min_exit_code=0, max_exit_code=99,
    ),
    Suggestion(
        trigger="bago health",
        condition_id="health_score_critical",
        tool="bago audit full",
        cmd="bago audit full",
        reason="health score < 60",
        min_exit_code=0, max_exit_code=99,
    ),
    Suggestion(
        trigger="bago heal",
        condition_id="post_heal_verify",
        tool="bago audit ast",
        cmd="bago audit ast .",
        reason="verificar que las reparaciones no introdujeron asimetrías",
        min_exit_code=0, max_exit_code=0,
    ),
]


# ── Condición detectors ────────────────────────────────────────────────────────

def _git(args: list[str], timeout_ms: int = 200) -> str:
    """Ejecuta git y retorna stdout. Devuelve '' en cualquier error."""
    try:
        r = subprocess.run(
            ["git"] + args,
            capture_output=True, text=True,
            cwd=str(_PROJECT_ROOT),
            timeout=timeout_ms / 1000,
        )
        return r.stdout.strip()
    except Exception:
        return ""


def _read_state() -> dict:
    """Lee global_state.json defensivamente. Devuelve {} si falla."""
    try:
        if _STATE_FILE.exists():
            return json.loads(_STATE_FILE.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        pass
    return {}


def _condition_met(s: Suggestion) -> bool:
    """Evalúa si la condición de una sugerencia está activa."""
    cid = s.condition_id

    if cid == "start_py_modified":
        diff = _git(["diff", "--name-only", "HEAD", "--", "*.py"])
        return bool(diff)

    if cid == "commit_py_staged_no_audit":
        staged = _git(["diff", "--cached", "--name-only", "--", "*.py"])
        return bool(staged)

    if cid == "push_health_low":
        state = _read_state()
        score = state.get("health_score", state.get("health", {}).get("score", 100))
        try:
            return int(score) < 70
        except (TypeError, ValueError):
            return False

    if cid == "done_sprint_no_cosecha":
        state = _read_state()
        sprint = state.get("sprint_status", {})
        done_count = sprint.get("tasks_done_count", 0)
        last_cosecha = sprint.get("last_cosecha_at")
        try:
            return int(done_count) >= 5 and not last_cosecha
        except (TypeError, ValueError):
            return False

    if cid == "cosecha_no_test_evidence":
        state = _read_state()
        evidence = state.get("test_evidence", [])
        return len(evidence) == 0

    if cid == "health_score_critical":
        state = _read_state()
        score = state.get("health_score", state.get("health", {}).get("score", 100))
        try:
            return int(score) < 60
        except (TypeError, ValueError):
            return False

    if cid == "post_heal_verify":
        # Siempre sugerir después de heal (oportunidad natural de verificar)
        return True

    return False


# ── Lock (anti-fatiga) ─────────────────────────────────────────────────────────

def _lock_key(s: Suggestion) -> str:
    """SHA-256 estable para identificar unicidad de sugerencia."""
    key = {
        "repo": str(_PROJECT_ROOT),
        "trigger": s.trigger,
        "condition_id": s.condition_id,
        "tool": s.tool,
        "cmd": s.cmd,
    }
    return hashlib.sha256(
        json.dumps(key, sort_keys=True).encode("utf-8")
    ).hexdigest()[:32]


def _is_locked(s: Suggestion) -> bool:
    """True si la sugerencia ya se mostró dentro del TTL."""
    _LOCK_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = _LOCK_DIR / f"{_lock_key(s)}.json"
    if not lock_path.exists():
        return False
    try:
        data = json.loads(lock_path.read_text(encoding="utf-8"))
        expires_at = datetime.fromisoformat(data["expires_at"])
        if datetime.now(timezone.utc) < expires_at:
            return True
        lock_path.unlink(missing_ok=True)
    except Exception:
        pass
    return False


def _set_lock(s: Suggestion) -> None:
    """Registra que la sugerencia fue mostrada."""
    _LOCK_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = _LOCK_DIR / f"{_lock_key(s)}.json"
    now = datetime.now(timezone.utc)
    data = {
        "trigger": s.trigger,
        "condition_id": s.condition_id,
        "tool": s.tool,
        "cmd": s.cmd,
        "shown_at": now.isoformat(),
        "expires_at": now.replace(
            hour=(now.hour + LOCK_TTL_SECONDS // 3600) % 24
        ).isoformat(),
    }
    try:
        # Escritura atómica: tmp → rename
        tmp = lock_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(lock_path)
    except Exception:
        pass


# ── Output ─────────────────────────────────────────────────────────────────────

def _print_suggestion(s: Suggestion) -> None:
    """Imprime la sugerencia en stderr (solo si stderr es TTY)."""
    # Si stderr no es TTY (pipe/redirección), no imprimir
    if not sys.stderr.isatty():
        return
    # Si stdout redirigido a pipe también podría ser usada por máquinas, ser conservador
    lines = [
        "",
        f"  ┌─ 💡 SAC · {s.trigger} ─────────────────────────────────────",
        f"  │  {s.reason}.",
        f"  │  → {s.cmd}",
        f"  │  (omitir: BAGO_NO_SAC=1 {s.trigger.replace(' ', ' ')})",
        f"  └{'─' * 56}",
        "",
    ]
    for line in lines:
        print(line, file=sys.stderr)


# ── API pública ────────────────────────────────────────────────────────────────

def sac_suggest(trigger_point: str, exit_code: int = 0) -> None:
    """
    Evalúa y muestra sugerencias SAC para el trigger_point dado.

    Llama SIEMPRE al final de tu script, pasando el exit_code real:

        if __name__ == "__main__":
            code = main()
            sac_suggest("bago commit", exit_code=code)
            sys.exit(code)

    Garantías:
    - Nunca lanza excepciones
    - Nunca modifica exit codes
    - Máximo una sugerencia por invocación (anti-ciclo)
    - Respeta BAGO_NO_SAC=1 y BAGO_SAC_DEPTH
    """
    try:
        _sac_suggest_inner(trigger_point, exit_code)
    except Exception:
        pass  # SAC nunca debe romper el script principal


def _sac_suggest_inner(trigger_point: str, exit_code: int) -> None:
    # Guardas globales
    if os.environ.get("BAGO_NO_SAC", "0") == "1":
        return
    depth = int(os.environ.get("BAGO_SAC_DEPTH", "0"))
    if depth >= 1:
        return  # anti-ciclo: no sugerir dentro de una cadena SAC

    if len(_SHOWN_THIS_RUN) >= MAX_SUGGESTIONS_PER_RUN:
        return

    candidates = [s for s in _CATALOG if s.trigger == trigger_point]

    for s in candidates:
        # Filtrar por exit_code relevante
        if not (s.min_exit_code <= exit_code <= s.max_exit_code):
            continue
        # Anti-fatiga
        if _is_locked(s):
            continue
        # Condición real
        if not _condition_met(s):
            continue
        # Mostrar
        _print_suggestion(s)
        _set_lock(s)
        _SHOWN_THIS_RUN.append(s.condition_id)
        return  # máximo una sugerencia por llamada


def clear_locks(trigger_point: str | None = None) -> int:
    """Elimina locks SAC (para testing o reset manual). Retorna número eliminados."""
    _LOCK_DIR.mkdir(parents=True, exist_ok=True)
    removed = 0
    for lock_file in _LOCK_DIR.glob("*.json"):
        try:
            if trigger_point:
                data = json.loads(lock_file.read_text(encoding="utf-8"))
                if data.get("trigger") != trigger_point:
                    continue
            lock_file.unlink()
            removed += 1
        except Exception:
            pass
    return removed


# ── Self-test ──────────────────────────────────────────────────────────────────

def _self_test() -> None:
    import tempfile, unittest

    class TestSACEngine(unittest.TestCase):

        def test_lock_key_stable(self):
            s = _CATALOG[0]
            k1 = _lock_key(s)
            k2 = _lock_key(s)
            self.assertEqual(k1, k2)
            self.assertEqual(len(k1), 32)

        def test_lock_key_different_for_different_conditions(self):
            keys = {_lock_key(s) for s in _CATALOG}
            self.assertEqual(len(keys), len(_CATALOG), "Todas las keys deben ser únicas")

        def test_no_sac_env_var(self):
            os.environ["BAGO_NO_SAC"] = "1"
            try:
                sac_suggest("bago commit", exit_code=0)  # No debe hacer nada
            finally:
                os.environ.pop("BAGO_NO_SAC", None)

        def test_depth_guard(self):
            os.environ["BAGO_SAC_DEPTH"] = "1"
            try:
                sac_suggest("bago commit", exit_code=0)  # No debe sugerir
            finally:
                os.environ.pop("BAGO_SAC_DEPTH", None)

        def test_exit_code_filter(self):
            # "bago commit" solo sugiere si exit_code==0
            commit_sug = next(s for s in _CATALOG if s.trigger == "bago commit")
            self.assertEqual(commit_sug.min_exit_code, 0)
            self.assertEqual(commit_sug.max_exit_code, 0)

        def test_read_state_defensive(self):
            # No debe lanzar aunque el archivo no exista
            state = _read_state()
            self.assertIsInstance(state, dict)

        def test_catalog_coverage(self):
            triggers = {s.trigger for s in _CATALOG}
            expected = {"bago start", "bago commit", "bago pre-push",
                        "bago done", "bago cosecha", "bago health", "bago heal"}
            self.assertEqual(triggers, expected)

    suite = unittest.TestLoader().loadTestsFromTestCase(TestSACEngine)
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
    elif "--clear-locks" in sys.argv:
        n = clear_locks()
        print(f"  SAC: {n} lock(s) eliminado(s)")
    elif "--status" in sys.argv:
        _LOCK_DIR.mkdir(parents=True, exist_ok=True)
        locks = list(_LOCK_DIR.glob("*.json"))
        print(f"  SAC locks activos: {len(locks)}")
        now = datetime.now(timezone.utc)
        for lf in locks:
            try:
                d = json.loads(lf.read_text(encoding="utf-8"))
                exp = datetime.fromisoformat(d["expires_at"])
                remaining = max(0, int((exp - now).total_seconds() // 60))
                print(f"    [{d['trigger']}] → {d['cmd']}  (expira en {remaining}m)")
            except Exception:
                print(f"    {lf.name} (error al leer)")
    else:
        print(__doc__)
