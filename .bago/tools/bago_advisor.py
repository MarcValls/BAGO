#!/usr/bin/env python3
"""bago_advisor.py — Advisor LLM adaptativo y orientativo para BAGO.

Un modelo pequeño (phi3:mini, qwen2.5-coder:7b) que conoce el estado real
del framework y orienta al usuario en cada paso de su trabajo.

Subcomandos:
  bago advisor ask "<pregunta>"      → pregunta libre en contexto BAGO
  bago advisor next                  → ¿qué debo hacer ahora?
  bago advisor explain <cmd>         → explica un comando + cuándo usarlo
  bago advisor run <cmd> [args...]   → ejecuta + analiza output con LLM
  bago advisor context               → muestra snapshot de contexto activo
  bago advisor --test                → self-tests

Características:
  • Prompt adaptativo: lee estado real (flow, task, health, historial)
  • Historial rolling 10 interacciones en advisor_context.jsonl
  • Streaming real de tokens (phi3:mini funciona en 2–4 GB RAM)
  • Redacción automática de secretos antes de enviar al LLM
  • Orientación siempre: cada respuesta termina con → Próximo paso
  • Detección de dominio: music/código/seguridad/general
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import threading
import urllib.request
import urllib.error
import uuid
from pathlib import Path
from typing import Iterator

from bago.ollama_runtime import DEFAULT_OLLAMA_PORT, default_ollama_base_url, env_port

# ── Fix UTF-8 en Windows ──────────────────────────────────────────────────────
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── Rutas ─────────────────────────────────────────────────────────────────────
TOOLS_DIR   = Path(__file__).resolve().parent
BAGO_ROOT   = TOOLS_DIR.parent
PROJECT_DIR = BAGO_ROOT.parent
STATE_DIR   = BAGO_ROOT / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)

CONTEXT_LOG  = STATE_DIR / "advisor_context.jsonl"
GLOBAL_STATE = STATE_DIR / "global_state.json"
LLM_CFG      = STATE_DIR / "llm_config.json"
BAGO_SCRIPT  = PROJECT_DIR / "bago"

# ── Colores ───────────────────────────────────────────────────────────────────
_USE_COLOR = sys.stdout.isatty()
def _c(code: str, t: str) -> str:
    return f"\033[{code}m{t}\033[0m" if _USE_COLOR else t

OK   = lambda t: _c("1;32", t)   # noqa: E731
WARN = lambda t: _c("1;33", t)   # noqa: E731
ERR  = lambda t: _c("1;31", t)   # noqa: E731
BOLD = lambda t: _c("1", t)      # noqa: E731
DIM  = lambda t: _c("2", t)      # noqa: E731
CYAN = lambda t: _c("1;36", t)   # noqa: E731
MAG  = lambda t: _c("1;35", t)   # noqa: E731

# ── Ollama ─────────────────────────────────────────────────────────────────────
OLLAMA_URL   = default_ollama_base_url()
DEFAULT_MODEL = "qwen2.5-coder:7b"

_SECRET_PATTERNS = [
    # API keys / tokens
    r'(api[_\-]?key|token|secret|password|passwd|pwd)\s*[=:]\s*\S+',
    r'bearer\s+[A-Za-z0-9\-._~+/]{20,}',
    # Private IPs / internal URLs with credentials
    r'https?://[^:@\s]+:[^@\s]+@\S+',
    # Long hex/base64 that look like keys (40+ chars)
    r'[A-Za-z0-9+/]{40,}={0,2}',
    # JWT-like (3 base64 segments with dots)
    r'[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}',
]
_SECRET_RE = re.compile("|".join(_SECRET_PATTERNS), re.IGNORECASE)

_RUN_DENYLIST = {
    "neural", "shell", "workflow", "daemon", "watch", "server",
    "listen", "live", "stream", "repl", "interactive", "node",
}

MAX_OUTPUT_BYTES  = 8 * 1024   # 8 KB
MAX_CONTEXT_CHARS = 2_000      # chars injected into system prompt
MAX_HISTORY       = 10         # interactions persisted


# ─────────────────────────────────────────────────────────────────────────────
# Ollama client (inline, no Neural Bus required)
# ─────────────────────────────────────────────────────────────────────────────

def _active_model() -> str:
    try:
        cfg = json.loads(LLM_CFG.read_text(encoding="utf-8"))
        mid = cfg.get("active_model", "")
        _map = {
            "phi3-mini":      "phi3:mini",
            "qwen25-coder":   "qwen2.5-coder:7b",
            "llama32-3b":     "llama3.2:3b",
            "deepseek-coder": "deepseek-coder:6.7b",
        }
        return _map.get(mid, mid) if mid else DEFAULT_MODEL
    except Exception:
        return DEFAULT_MODEL


def _ollama_alive() -> bool:
    import socket
    try:
        with socket.create_connection(("127.0.0.1", DEFAULT_OLLAMA_PORT), timeout=1):
            return True
    except OSError:
        return False


def _stream_ollama(messages: list[dict], model: str) -> Iterator[str]:
    """Yield text tokens from Ollama /api/chat (streaming NDJSON)."""
    payload = json.dumps({
        "model":    model,
        "messages": messages,
        "stream":   True,
    }).encode()

    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            for raw in resp:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    chunk = obj.get("message", {}).get("content", "")
                    if chunk:
                        yield chunk
                except json.JSONDecodeError:
                    continue
    except urllib.error.HTTPError as exc:
        print(ERR(f"  [ADVISOR-E] Ollama respondió con error HTTP {exc.code}: {exc.reason}"))
    except urllib.error.URLError as exc:
        print(ERR(f"  [ADVISOR-E] No se pudo conectar con Ollama: {exc.reason}"))
    except socket.timeout:
        print(ERR("  [ADVISOR-E] Timeout al esperar respuesta de Ollama."))


def _call_llm(messages: list[dict], model: str | None = None) -> str:
    """Stream LLM and print to terminal. Returns full text."""
    model = model or _active_model()
    if not _ollama_alive():
        print(ERR("  [ADVISOR-E] Ollama no responde. Arranca con: bago llm start"))
        return ""

    full = []
    print()
    try:
        for chunk in _stream_ollama(messages, model):
            print(chunk, end="", flush=True)
            full.append(chunk)
    except urllib.error.URLError as e:
        print(ERR(f"\n  [ADVISOR-E] Error de conexión: {e}"))
    except Exception as e:
        print(ERR(f"\n  [ADVISOR-E] {e}"))
    print("\n")
    return "".join(full)


# ─────────────────────────────────────────────────────────────────────────────
# Context engine
# ─────────────────────────────────────────────────────────────────────────────

def _read_global_state() -> dict:
    try:
        return json.loads(GLOBAL_STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read_recent_history(n: int = 5) -> list[dict]:
    if not CONTEXT_LOG.exists():
        return []
    entries = []
    try:
        for line in CONTEXT_LOG.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    except Exception:
        pass
    return entries[-n:]


def _detect_domain(gs: dict, recent: list[dict]) -> str:
    """Detect active work domain from state + recent commands."""
    flow = str(gs.get("sprint_status", {}).get("active_workflow") or "").lower()
    last_cmds = " ".join(e.get("cmd", "") for e in recent[-3:]).lower()

    music_kw = {"ableton", "music", "techno", "midi", "audio", "musicxml"}
    security_kw = {"secret", "scan", "audit", "dep-audit", "hardcode"}
    code_kw = {"lint", "complexity", "refactor", "type", "review", "dead"}

    combined = f"{flow} {last_cmds}"
    if any(k in combined for k in music_kw):
        return "music"
    if any(k in combined for k in security_kw):
        return "security"
    if any(k in combined for k in code_kw):
        return "code"
    return "general"


def _build_context_snapshot() -> dict:
    gs = _read_global_state()
    recent = _read_recent_history(5)
    domain = _detect_domain(gs, recent)

    health = gs.get("health_score", {})
    health_score = health.get("score", "?")
    health_issues = health.get("ko", [])

    sprint = gs.get("sprint_status", {})
    flow = sprint.get("active_workflow") or "ninguno"

    return {
        "domain":       domain,
        "flow":         flow,
        "version":      gs.get("bago_version", "?"),
        "health_score": health_score,
        "health_issues": health_issues[:3],
        "recent":       recent,
        "mode":         gs.get("mode", "manual"),
    }


def _build_system_prompt(snap: dict) -> str:
    domain = snap["domain"]

    # Domain-specific voice
    if domain == "music":
        domain_hint = (
            "El usuario está trabajando en producción musical/Ableton. "
            "Usa terminología de música electrónica (BPM, tracks, samples, MIDI, arrangement). "
            "Herramientas relevantes: ableton-template, music, find-tool."
        )
    elif domain == "security":
        domain_hint = (
            "El usuario está revisando seguridad del código. "
            "Sé preciso sobre vectores de ataque, CVEs y remediación. "
            "Herramientas relevantes: secret-scan, dep-audit, hardcodes, spanish."
        )
    elif domain == "code":
        domain_hint = (
            "El usuario está trabajando en calidad de código. "
            "Sé técnico y concreto sobre refactoring, complejidad y tipos. "
            "Herramientas relevantes: lint, complexity, type-check, refactor, dead-code."
        )
    else:
        domain_hint = (
            "Contexto general de desarrollo con BAGO. "
            "Sugiere herramientas según el problema descrito."
        )

    # Health warning
    health_ctx = f"Salud del proyecto: {snap['health_score']}/100."
    if snap["health_issues"]:
        issues_str = "; ".join(snap["health_issues"][:2])
        health_ctx += f" Problemas activos: {issues_str}."

    # Recent history
    history_lines = []
    for e in snap["recent"][-3:]:
        cmd = e.get("cmd", "")
        summary = e.get("summary", "")[:80]
        rc = e.get("rc", "?")
        status = "✓" if rc == 0 else "✗"
        history_lines.append(f"  {status} bago {cmd}: {summary}")
    history_ctx = ""
    if history_lines:
        history_ctx = "\nComandos recientes:\n" + "\n".join(history_lines)

    return f"""Eres el advisor LLM del framework BAGO v{snap['version']} (Bootstrap Adaptive Guided Operations).
Asistes a desarrolladores en tiempo real usando herramientas del framework.

{domain_hint}

Estado actual:
  Flujo activo: {snap['flow']}
  {health_ctx}
  Modo: {snap['mode']}{history_ctx}

Herramientas BAGO disponibles (bago <cmd>):
  find-tool        → busca la herramienta adecuada para cualquier tarea
  ask / intent     → procesa lenguaje natural y ejecuta tools
  health           → puntuación de salud del proyecto (0-100)
  ideas            → qué hacer ahora (priorizado por contexto)
  review           → revisión de código: calidad, bugs, mejoras
  audit            → auditoría completa
  secret-scan      → detecta secretos hardcodeados
  hardcodes        → datos estáticos que deberían ser dinámicos
  spanish          → auditoría ortográfica en español
  complexity       → complejidad ciclomática y cognitiva
  lint             → estilo y calidad Python
  type-check       → type hints
  sprint           → gestión de sprints y tareas
  npath            → grafo de conocimiento del proyecto
  ableton-template → scaffold proyecto Ableton techno
  music            → pipeline MusicXML
  neural           → Neural Bus (mensajería agentes)
  llm              → motor LLM local (Ollama)
  why <cmd>        → explica un comando en detalle
  advisor          → este advisor (recursivo)

Reglas de respuesta:
  1. Responde en el idioma del usuario.
  2. Sé conciso y accionable — máximo 5 párrafos.
  3. Cita comandos con formato exacto: `bago <cmd>`.
  4. SIEMPRE termina tu respuesta con una línea vacía y luego:
     → Próximo paso: <acción concreta>
  5. Si el usuario describe un error, primero diagnosica, luego sugiere fix.
  6. No inventes comandos — usa solo los listados arriba."""


def _redact(text: str) -> str:
    """Redact secrets and sensitive patterns from text before sending to LLM."""
    return _SECRET_RE.sub("[REDACTED]", text)


def _log_interaction(cmd: str, rc: int | None, summary: str) -> None:
    entry = {
        "ts":      time.strftime("%Y-%m-%dT%H:%M:%S"),
        "cmd":     cmd,
        "rc":      rc,
        "summary": summary[:120],
    }
    try:
        with CONTEXT_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        # Trim to MAX_HISTORY lines
        lines = CONTEXT_LOG.read_text(encoding="utf-8").splitlines()
        if len(lines) > MAX_HISTORY:
            CONTEXT_LOG.write_text(
                "\n".join(lines[-MAX_HISTORY:]) + "\n", encoding="utf-8"
            )
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Subcommands
# ─────────────────────────────────────────────────────────────────────────────

def cmd_ask(question: str) -> int:
    """Free-form question in BAGO context."""
    if not question.strip():
        print(WARN("  Uso: bago advisor ask \"<pregunta>\""))
        return 1

    print(CYAN(f"  ● Advisor · pregunta: {question[:60]}{'…' if len(question)>60 else ''}"))
    snap = _build_context_snapshot()
    sysprompt = _build_system_prompt(snap)

    messages = [
        {"role": "system",  "content": sysprompt},
        {"role": "user",    "content": question},
    ]

    response = _call_llm(messages)
    if response:
        _log_interaction(f"advisor ask", 0, response[:80])
    return 0 if response else 1


def cmd_next() -> int:
    """Orientation: what should I do now?"""
    snap = _build_context_snapshot()
    sysprompt = _build_system_prompt(snap)

    # Build a rich "what is the state" query
    issues_str = "; ".join(snap["health_issues"]) if snap["health_issues"] else "ninguno"
    recent_str = "; ".join(
        f"bago {e['cmd']} ({'ok' if e.get('rc')==0 else 'error'})"
        for e in snap["recent"][-3:]
    ) if snap["recent"] else "ninguna actividad previa registrada"

    question = (
        f"Dime qué debo hacer ahora mismo. "
        f"Flujo activo: {snap['flow']}. "
        f"Salud: {snap['health_score']}/100. "
        f"Problemas: {issues_str}. "
        f"Comandos recientes: {recent_str}. "
        f"Dominio detectado: {snap['domain']}. "
        f"Dame un plan de acción concreto con los comandos exactos a ejecutar."
    )

    print(CYAN("  ● Advisor · calculando próximo paso..."))
    messages = [
        {"role": "system", "content": sysprompt},
        {"role": "user",   "content": question},
    ]

    response = _call_llm(messages)
    if response:
        _log_interaction("advisor next", 0, response[:80])
    return 0 if response else 1


def cmd_explain(cmd_name: str) -> int:
    """Explain a BAGO command with LLM enrichment."""
    if not cmd_name.strip():
        print(WARN("  Uso: bago advisor explain <cmd>"))
        return 1

    # First: try to get the registry description
    registry_info = ""
    try:
        sys.path.insert(0, str(TOOLS_DIR))
        from tool_registry import REGISTRY
        entry = REGISTRY.get(cmd_name) or REGISTRY.get(cmd_name.replace("-", "_"))
        if entry:
            registry_info = (
                f"Descripción técnica del registro: {entry.description}. "
                f"Módulo: {entry.module}. "
            )
    except Exception:
        pass

    snap = _build_context_snapshot()
    sysprompt = _build_system_prompt(snap)

    question = (
        f"Explica el comando `bago {cmd_name}` de forma práctica. "
        f"{registry_info}"
        f"Incluye: (1) qué hace exactamente, (2) cuándo usarlo, "
        f"(3) un ejemplo de uso, (4) con qué otros comandos se combina bien. "
        f"Termina con el próximo paso habitual después de usarlo."
    )

    print(CYAN(f"  ● Advisor · explicando `bago {cmd_name}`..."))
    messages = [
        {"role": "system", "content": sysprompt},
        {"role": "user",   "content": question},
    ]

    response = _call_llm(messages)
    if response:
        _log_interaction(f"advisor explain {cmd_name}", 0, response[:80])
    return 0 if response else 1


def cmd_run(cmd_args: list[str], dry_run: bool = False) -> int:
    """Execute a BAGO command and analyze its output with the LLM."""
    if not cmd_args:
        print(WARN("  Uso: bago advisor run <cmd> [args...]"))
        print(WARN("  Comandos no permitidos (interactivos/daemons): "
                   + ", ".join(sorted(_RUN_DENYLIST))))
        return 1

    cmd_name = cmd_args[0].lower()
    # Safety: denylist check
    for denied in _RUN_DENYLIST:
        if denied in cmd_name:
            print(ERR(f"  [ADVISOR-W] `bago {cmd_name}` es interactivo/daemon — "
                      "usa directamente: bago " + " ".join(cmd_args)))
            return 1

    if dry_run:
        print(DIM(f"  [DRY-RUN] bago {' '.join(cmd_args)}"))
        print(DIM("  → El output sería analizado por el LLM (max 8KB, timeout 30s)"))
        return 0

    print(CYAN(f"  ● Ejecutando: bago {' '.join(cmd_args)}"))
    t0 = time.time()

    try:
        launcher = [sys.executable, str(BAGO_SCRIPT)] if BAGO_SCRIPT.exists() else ["bago"]
        result = subprocess.run(
            launcher + list(cmd_args),
            capture_output=True,
            timeout=30,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(PROJECT_DIR),
        )
    except subprocess.TimeoutExpired:
        print(ERR(f"  [ADVISOR-E] Timeout (30s) ejecutando bago {cmd_args[0]}"))
        return 1
    except FileNotFoundError:
        print(ERR("  [ADVISOR-E] No se encontró el lanzador bago. Ejecuta desde el directorio del proyecto."))
        return 1

    elapsed = round(time.time() - t0, 1)
    raw_output = (result.stdout + result.stderr)[:MAX_OUTPUT_BYTES]
    redacted = _redact(raw_output)
    rc = result.returncode

    # Show command output first
    if redacted.strip():
        print(DIM("  ─── Output del comando ───────────────────────────"))
        print(redacted[:2000])  # Show max 2KB to terminal
        if len(raw_output) > 2000:
            print(DIM(f"  ... (+{len(raw_output)-2000} chars truncados)"))
        print()

    # Now analyze with LLM
    snap = _build_context_snapshot()
    sysprompt = _build_system_prompt(snap)

    status_word = "exitoso" if rc == 0 else f"con error (rc={rc})"
    question = (
        f"Acabo de ejecutar `bago {' '.join(cmd_args)}` — resultado {status_word} en {elapsed}s.\n\n"
        f"Output:\n```\n{redacted[:3000]}\n```\n\n"
        f"{'Analiza el output y dime qué significan los resultados.' if rc == 0 else 'El comando falló. Diagnostica el error y sugiere cómo corregirlo.'} "
        f"¿Qué debo hacer a continuación?"
    )

    print(CYAN("  ● Advisor · analizando output..."))
    messages = [
        {"role": "system", "content": sysprompt},
        {"role": "user",   "content": question},
    ]

    response = _call_llm(messages)
    summary = f"rc={rc} | " + response[:60] if response else f"rc={rc} | (sin respuesta LLM)"
    _log_interaction(f"advisor run {cmd_args[0]}", rc, summary)
    return 0 if response else 1


def cmd_context() -> int:
    """Show current advisor context snapshot."""
    snap = _build_context_snapshot()
    print(f"\n  {BOLD('Advisor Context Snapshot')}")
    print(f"  {'─'*50}")
    print(f"  Dominio detectado : {CYAN(snap['domain'])}")
    print(f"  Flujo activo      : {snap['flow']}")
    print(f"  Salud             : {snap['health_score']}/100")
    print(f"  Modo              : {snap['mode']}")
    print(f"  Modelo LLM        : {_active_model()}")
    print(f"  Ollama            : {OK('activo') if _ollama_alive() else ERR('inactivo')}")

    if snap["health_issues"]:
        print(f"\n  {WARN('Problemas activos:')}")
        for issue in snap["health_issues"]:
            print(f"    • {issue}")

    recent = snap["recent"]
    if recent:
        print(f"\n  {DIM('Historial reciente:')}")
        for e in recent:
            rc = e.get("rc", "?")
            icon = OK("✓") if rc == 0 else ERR("✗")
            print(f"    {icon} [{e.get('ts','?')[11:16]}] bago {e.get('cmd','')} — {e.get('summary','')[:50]}")
    else:
        print(f"\n  {DIM('Sin historial previo.')}")

    print()
    return 0


def cmd_rubber_duck(file_arg: str, extra_args: list[str]) -> int:
    """Delegate rubber duck analysis to bago_rubber_duck.py."""
    try:
        rd_module = TOOLS_DIR / "bago_rubber_duck.py"
        if not rd_module.exists():
            print(WARN("  bago_rubber_duck.py no encontrado en tools/"))
            return 1
        import importlib.util
        spec = importlib.util.spec_from_file_location("bago_rubber_duck", rd_module)
        if spec is None or spec.loader is None:
            raise ImportError("Cannot load bago_rubber_duck")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        # Build argv list for the sub-tool
        sub_argv = ["rubber-duck"]
        if file_arg:
            sub_argv.append(file_arg)
        sub_argv.extend(extra_args)
        return mod.main(sub_argv)
    except Exception as e:
        print(ERR(f"  [ADVISOR-E] Error cargando rubber duck: {e}"))
        return 1


# ─────────────────────────────────────────────────────────────────────────────
# Self-tests
# ─────────────────────────────────────────────────────────────────────────────

def _self_test() -> int:
    print("Tests bago_advisor.py...")
    fails: list[str] = []

    def ok(n: str) -> None:   print(f"  OK: {n}")
    def fail(n: str, m: str): fails.append(n); print(f"  FAIL: {n}: {m}")

    # T1: redact secrets
    sample = "token=abc123secret password=hunter2 normal text"
    redacted = _redact(sample)
    if "[REDACTED]" in redacted and "normal text" in redacted:
        ok("redact_secrets")
    else:
        fail("redact_secrets", f"got: {redacted}")

    # T2: context snapshot keys
    snap = _build_context_snapshot()
    req = {"domain", "flow", "health_score", "recent", "mode", "version"}
    missing = req - snap.keys()
    if not missing:
        ok("context_snapshot_keys")
    else:
        fail("context_snapshot_keys", f"missing: {missing}")

    # T3: domain detection — music
    class FakeEntry:
        cmd = "ableton-template"
    _log_interaction("ableton-template", 0, "Created project folder")
    snap2 = _build_context_snapshot()
    if snap2["domain"] in ("music", "general"):
        ok("domain_detection_music")
    else:
        fail("domain_detection_music", f"domain={snap2['domain']}")

    # T4: system prompt contains key sections
    prompt = _build_system_prompt(snap)
    for kw in ["bago", "Próximo paso", "find-tool", "health"]:
        if kw not in prompt:
            fail("system_prompt_completeness", f"missing keyword: {kw}")
            break
    else:
        ok("system_prompt_completeness")

    # T5: history log write/read
    CONTEXT_LOG.unlink(missing_ok=True)
    for i in range(3):
        _log_interaction(f"test-cmd-{i}", i % 2, f"summary {i}")
    hist = _read_recent_history(10)
    if len(hist) == 3 and hist[0]["cmd"] == "test-cmd-0":
        ok("history_log_rw")
    else:
        fail("history_log_rw", f"got {len(hist)} entries")

    # T6: MAX_HISTORY trim
    for i in range(15):
        _log_interaction(f"trim-cmd-{i}", 0, "x")
    lines = CONTEXT_LOG.read_text(encoding="utf-8").splitlines()
    if len(lines) <= MAX_HISTORY:
        ok("history_trim")
    else:
        fail("history_trim", f"got {len(lines)} lines (max {MAX_HISTORY})")

    # T7: denylist blocks interactive commands
    denied = any(d in "neural" for d in _RUN_DENYLIST)
    if denied:
        ok("denylist_neural")
    else:
        fail("denylist_neural", "neural not in denylist")

    # T8: active model fallback
    m = _active_model()
    if isinstance(m, str) and len(m) > 2:
        ok(f"active_model ({m})")
    else:
        fail("active_model", f"got: {m!r}")

    print(f"\n  {len(fails)} fallos / {8 - len(fails)}/8 pasaron")
    return 0 if not fails else 1


# ─────────────────────────────────────────────────────────────────────────────
# Main dispatcher
# ─────────────────────────────────────────────────────────────────────────────

USAGE = """
  bago advisor <subcomando>

  Subcomandos:
    ask "<pregunta>"       → pregunta libre al LLM en contexto BAGO
    next                   → ¿qué debo hacer ahora?
    explain <cmd>          → explica un comando con ejemplos y contexto
    run <cmd> [args...]    → ejecuta + analiza output (max 30s, 8KB)
    context                → muestra snapshot de contexto activo
    rubber-duck <file.py>  → rubber duck debugging: repite qué hace el código

  Opciones:
    --test                 → self-tests
    --dry-run              → simula sin ejecutar ni llamar al LLM
    -h, --help             → esta ayuda

  Ejemplos:
    bago advisor ask "cómo mejoro la calidad del código?"
    bago advisor next
    bago advisor explain health
    bago advisor run health
    bago advisor run secret-scan
    bago advisor context
    bago advisor rubber-duck bago_wizard.py
"""


def main(argv: list[str]) -> int:
    args = argv[1:]  # strip "advisor"

    if not args or args[0] in {"-h", "--help"}:
        print(USAGE)
        return 0

    if args[0] == "--test":
        return _self_test()

    dry_run = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]

    subcmd = args[0] if args else ""

    if subcmd == "ask":
        question = " ".join(args[1:]) if len(args) > 1 else ""
        return cmd_ask(question)

    if subcmd == "next":
        return cmd_next()

    if subcmd == "explain":
        cmd_name = args[1] if len(args) > 1 else ""
        return cmd_explain(cmd_name)

    if subcmd == "run":
        return cmd_run(args[1:], dry_run=dry_run)

    if subcmd == "context":
        return cmd_context()

    if subcmd in ("rubber-duck", "rubber_duck", "rd"):
        file_arg = args[1] if len(args) > 1 else ""
        return cmd_rubber_duck(file_arg, args[2:])

    # Unknown subcommand — treat as implicit 'ask'
    print(WARN(f"  Subcomando desconocido: '{subcmd}'. Interpretando como pregunta..."))
    return cmd_ask(" ".join(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
