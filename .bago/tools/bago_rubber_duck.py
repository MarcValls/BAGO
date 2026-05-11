#!/usr/bin/env python3
"""
bago_rubber_duck.py — Auto rubber duck debugging para BAGO.

Cuando se crea o modifica un módulo, recopila trazas de memoria relacionadas
y pide al LLM que "repita" qué quiere hacer el código para detectar pasos
faltantes, saltos de lógica y fallos similares.

Subcomandos:
  bago rubber-duck <file.py>             → analiza un archivo completo
  bago rubber-duck <file.py> --lines N:M → analiza un fragmento (líneas N a M)
  bago rubber-duck --last                → último .py modificado en tools/
  bago rubber-duck --watch [dir]         → modo watch (polling, foreground)
  bago rubber-duck --test                → self-tests

Variables de entorno:
  BAGO_RD_INTERVAL=N     segundos entre polls en watch mode (default 3)
  BAGO_RD_MAX_CHARS=N    máximo chars de código enviados al LLM (default 6000)
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ── Paths ─────────────────────────────────────────────────────────────────────
TOOLS_DIR    = Path(__file__).parent
BAGO_ROOT    = TOOLS_DIR.parent
STATE_DIR    = BAGO_ROOT / "state"
CONTEXT_LOG  = STATE_DIR / "advisor_context.jsonl"
GLOBAL_ST    = STATE_DIR / "global_state.json"
FINDINGS_DIR = STATE_DIR / "findings"
LLM_CFG      = STATE_DIR / "llm_config.json"
OLLAMA_URL   = "http://127.0.0.1:11434"
DEFAULT_MODEL = "phi3:mini"

# ── Config ────────────────────────────────────────────────────────────────────
WATCH_INTERVAL     = int(os.getenv("BAGO_RD_INTERVAL", "3"))
MAX_CODE_CHARS     = int(os.getenv("BAGO_RD_MAX_CHARS", "6000"))
MAX_MEMORY_ENTRIES = 8
MAX_HISTORY_CHARS  = 1500
MAX_HISTORY_LOG    = 10

# ── Colors ────────────────────────────────────────────────────────────────────
_NO_COLOR = not sys.stdout.isatty() or bool(os.getenv("NO_COLOR"))


def _c(code: str, text: str) -> str:
    return text if _NO_COLOR else f"\033[{code}m{text}\033[0m"


CYAN    = lambda t: _c("96", t)
YELLOW  = lambda t: _c("93", t)
GREEN   = lambda t: _c("92", t)
RED     = lambda t: _c("91", t)
DIM     = lambda t: _c("2", t)
BOLD    = lambda t: _c("1", t)
MAGENTA = lambda t: _c("95", t)

# ── Secret redaction (mirrors bago_advisor.py) ────────────────────────────────
_SECRET_PATTERNS = [
    r'(?i)(password|passwd|secret|token|key|api[_-]?key|auth|credential|private)\s*[=:]\s*["\']?[\w\-./+]{8,}["\']?',
    r'[A-Za-z0-9+/]{40,}={0,2}',
    r'[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}',
]
_SECRET_RE = re.compile("|".join(_SECRET_PATTERNS), re.IGNORECASE)


def _redact(text: str) -> str:
    return _SECRET_RE.sub("[REDACTED]", text)


# ── LLM helpers ───────────────────────────────────────────────────────────────

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
        with socket.create_connection(("127.0.0.1", 11434), timeout=1):
            return True
    except OSError:
        return False


def _stream_ollama(messages: list[dict], model: str):
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


def _call_llm(messages: list[dict]) -> str:
    model = _active_model()
    if not _ollama_alive():
        print(RED("  [RD] Ollama no responde. Arranca con: bago llm start"))
        return ""
    full = []
    print()
    try:
        for chunk in _stream_ollama(messages, model):
            print(chunk, end="", flush=True)
            full.append(chunk)
    except urllib.error.URLError as e:
        print(RED(f"\n  [RD-E] Error de conexión: {e}"))
    except Exception as e:
        print(RED(f"\n  [RD-E] {e}"))
    print("\n")
    return "".join(full)


# ── AST-based smart code extractor ───────────────────────────────────────────

def _extract_module_docstring(tree: ast.Module) -> str:
    return ast.get_docstring(tree) or ""


def _extract_smart_code(source: str, lines: tuple[int, int] | None = None) -> tuple[str, str]:
    """
    Smart code extraction within MAX_CODE_CHARS budget.

    If lines specified: return that fragment (redacted).
    If full source fits: return as-is.
    If too large: build structural summary via AST (imports + signatures + docstrings).
    Returns (code_for_llm, extraction_mode).
    """
    if lines:
        start, end = lines
        src_lines = source.splitlines()
        fragment = "\n".join(src_lines[max(0, start - 1):end])
        if len(fragment) <= MAX_CODE_CHARS:
            return fragment, "fragment"
        source = fragment  # fall through to structural

    if len(source) <= MAX_CODE_CHARS:
        return source, "full"

    # Build structural summary via AST
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source[:MAX_CODE_CHARS] + "\n# [TRUNCADO — SyntaxError en parse]", "truncated"

    parts: list[str] = []
    src_lines = source.splitlines()

    # Module docstring
    doc = ast.get_docstring(tree)
    if doc:
        parts.append(f'"""\n{doc[:400]}\n"""')

    # Imports (first 30 lines usually)
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            try:
                parts.append(ast.unparse(node))
            except Exception:
                pass

    # Top-level assignments (constants / config vars)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if node.lineno <= len(src_lines):
                line = src_lines[node.lineno - 1].strip()
                if line and not line.startswith("#") and len(line) < 120:
                    parts.append(line)

    # Function and class signatures + docstrings (no bodies)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            try:
                arg_str = ", ".join(ast.unparse(a) for a in node.args.args)
                pfx = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
                parts.append(f"{pfx} {node.name}({arg_str}): ...")
            except Exception:
                parts.append(f"def {node.name}(...): ...")
            fn_doc = ast.get_docstring(node)
            if fn_doc:
                parts.append(f'    """{fn_doc[:200]}"""')

        elif isinstance(node, ast.ClassDef):
            parts.append(f"class {node.name}:")
            cls_doc = ast.get_docstring(node)
            if cls_doc:
                parts.append(f'    """{cls_doc[:200]}"""')
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    try:
                        arg_str = ", ".join(ast.unparse(a) for a in item.args.args)
                        pfx = "async def" if isinstance(item, ast.AsyncFunctionDef) else "def"
                        parts.append(f"    {pfx} {item.name}({arg_str}): ...")
                    except Exception:
                        parts.append(f"    def {item.name}(...): ...")
                    m_doc = ast.get_docstring(item)
                    if m_doc:
                        parts.append(f'        """{m_doc[:100]}"""')

    structural = "\n".join(parts)
    return structural[:MAX_CODE_CHARS], "structural"


# ── Memory trace gathering ─────────────────────────────────────────────────────

def _gather_memory_traces(module_name: str) -> str:
    """
    Gather relevant memory traces for a module using a fallback hierarchy:
    1. advisor_context.jsonl entries that mention module name
    2. sprint/flow from global_state.json
    3. git log for the file
    4. Last 3 general entries as fallback (marked as low-relevance)
    """
    traces: list[str] = []
    used_fallback = False

    # 1. advisor_context.jsonl — filtered by module name
    if CONTEXT_LOG.exists():
        try:
            all_entries = []
            for line in CONTEXT_LOG.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    try:
                        all_entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

            related = [e for e in all_entries if module_name.lower() in str(e).lower()]
            if related:
                traces.append("=== Historial LLM relacionado al módulo ===")
                for e in related[-MAX_MEMORY_ENTRIES:]:
                    ts = e.get("ts", "?")[11:16]
                    cmd = e.get("cmd", "?")
                    summary = e.get("summary", "")[:120]
                    traces.append(f"  [{ts}] {cmd}: {summary}")
            elif all_entries:
                # Fallback: last 3 general entries
                traces.append("=== Contexto general reciente (no específico del módulo) ===")
                for e in all_entries[-3:]:
                    ts = e.get("ts", "?")[11:16]
                    cmd = e.get("cmd", "?")
                    summary = e.get("summary", "")[:80]
                    traces.append(f"  [{ts}] {cmd}: {summary}")
                used_fallback = True
        except Exception:
            pass

    # 2. Sprint/flow context from global_state.json
    try:
        gs = json.loads(GLOBAL_ST.read_text(encoding="utf-8"))
        sprint = gs.get("sprint_status", {})
        flow = sprint.get("active_workflow", "")
        active_task = sprint.get("active_task", "")
        if flow or active_task:
            traces.append("=== Sprint activo ===")
            if flow:
                traces.append(f"  Flujo: {flow}")
            if active_task:
                traces.append(f"  Tarea: {str(active_task)[:120]}")
    except Exception:
        pass

    # 3. Git log for the file
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "--follow", "-5", "--", f"*{module_name}*"],
            capture_output=True, text=True, timeout=5,
            encoding="utf-8", errors="replace",
        )
        if result.returncode == 0 and result.stdout.strip():
            traces.append("=== Git log (últimos commits relevantes) ===")
            for line in result.stdout.strip().splitlines()[:5]:
                traces.append(f"  {line}")
    except Exception:
        pass

    if not traces:
        return "(sin trazas de memoria disponibles)"

    result_str = "\n".join(traces)
    if used_fallback:
        result_str = "[contexto_general_no_relacionado]\n" + result_str
    return _redact(result_str[:MAX_HISTORY_CHARS])


# ── Test discovery ────────────────────────────────────────────────────────────

def _find_related_tests(file_path: Path) -> list[Path]:
    """Find related test files using broad patterns."""
    name = file_path.stem
    repo_root = BAGO_ROOT.parent

    patterns = [
        f"**/test_{name}.py",
        f"**/{name}_test.py",
        f"**/*{name}*test*.py",
        f"**/*test*{name}*.py",
    ]
    found: set[Path] = set()
    for pat in patterns:
        try:
            for p in repo_root.glob(pat):
                if "test" in p.stem.lower() or "test" in str(p.parent).lower():
                    found.add(p)
        except Exception:
            pass
    return sorted(found)[:3]


# ── Core analysis ─────────────────────────────────────────────────────────────

def analyze(file_path: Path, lines: tuple[int, int] | None = None) -> dict:
    """
    Perform rubber duck analysis on a Python file (or fragment).
    Prints analysis to terminal and persists finding JSON.
    Returns a dict with analysis metadata.
    """
    if not file_path.exists():
        print(RED(f"  [RD] Archivo no encontrado: {file_path}"))
        return {"error": "file_not_found", "path": str(file_path)}

    try:
        source = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        print(RED(f"  [RD] Error leyendo archivo: {e}"))
        return {"error": str(e), "path": str(file_path)}

    # Module docstring
    module_doc = ""
    try:
        tree = ast.parse(source)
        module_doc = _extract_module_docstring(tree)
    except SyntaxError:
        pass

    # Smart code extraction
    code_for_llm, extraction_mode = _extract_smart_code(source, lines)
    code_for_llm = _redact(code_for_llm)

    # Memory traces
    module_name = file_path.stem
    memory_traces = _gather_memory_traces(module_name)

    # Related tests
    related_tests = _find_related_tests(file_path)

    # Print header
    loc = len(source.splitlines())
    fragment_note = f" (líneas {lines[0]}-{lines[1]})" if lines else ""
    print(f"\n{BOLD(CYAN('╔══ RUBBER DUCK DEBUG ══════════════════════════════════╗'))}")
    print(f"{BOLD('  Módulo :')} {MAGENTA(module_name)}")
    print(f"{BOLD('  Archivo:')} {DIM(str(file_path))}")
    print(f"{BOLD('  LOC    :')} {loc}{fragment_note}  [{extraction_mode}]")
    if related_tests:
        print(f"{BOLD('  Tests  :')} {DIM(', '.join(t.name for t in related_tests))}")
    print(f"{BOLD(CYAN('╚══════════════════════════════════════════════════════╝'))}")

    if not _ollama_alive():
        print(YELLOW("  [RD] Ollama no disponible — análisis estático únicamente."))
        finding = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "module": module_name,
            "file": str(file_path),
            "loc": loc,
            "extraction": extraction_mode,
            "lines": list(lines) if lines else None,
            "verdict": "NO_LLM",
            "model": None,
            "analysis": None,
            "memory_traces": memory_traces[:500],
        }
        _save_finding(module_name, finding)
        return finding

    # Build rubber duck prompt
    docstring_section = (
        f"\nIntención declarada (docstring):\n{module_doc[:500]}\n"
        if module_doc else ""
    )
    memory_section = (
        f"\nTrazas de memoria relacionadas:\n{memory_traces}\n"
        if memory_traces and memory_traces != "(sin trazas de memoria disponibles)"
        else ""
    )
    test_info = (
        "\nTests relacionados encontrados:\n" + "\n".join(f"  - {t}" for t in related_tests)
        if related_tests else ""
    )

    prompt = (
        f"Eres un rubber duck debugger especializado en código Python del framework BAGO.\n"
        f"Tu análisis tiene 4 secciones OBLIGATORIAS:\n\n"
        f"**1. REPITE** (en tus propias palabras, paso a paso):\n"
        f"Describe qué hace este código como si se lo explicaras a alguien que no lo conoce.\n"
        f"Usa viñetas numeradas. Sé concreto sobre el flujo de ejecución.\n\n"
        f"**2. DETECTA** (pasos faltantes / saltos de lógica):\n"
        f"¿Qué casos edge no están cubiertos? ¿Hay suposiciones implícitas que podrían fallar?\n"
        f"Marca cada hallazgo con: ⚠ POSIBLE FALLO: <descripción>\n\n"
        f"**3. COMPARA** (implementación vs intención):\n"
        f"¿Coincide lo que hace el código con lo que declara el docstring/comentarios?\n"
        f"Si hay discrepancia: ❌ INCONSISTENCIA: <descripción>\n\n"
        f"**4. ALERTA** (patterns problemáticos):\n"
        f"Race conditions, encoding issues, error handling incompleto, dependencias frágiles.\n"
        f"Marca con: 🔴 ALERTA: <descripción>\n\n"
        f"Módulo: {module_name}{fragment_note}"
        f"{docstring_section}{memory_section}{test_info}\n\n"
        f"Código:\n```python\n{code_for_llm}\n```\n\n"
        f"Analiza el código. Si está correcto, dilo explícitamente en cada sección.\n"
        f"Termina con: → Veredicto: OK | REVISAR | CRÍTICO"
    )

    messages = [
        {
            "role": "system",
            "content": (
                "Eres un experto debugger Python. Analizas código con precisión técnica. "
                "Respondes en español. Eres conciso pero completo. "
                "Identificas problemas reales, no de estilo."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    print(CYAN("\n  ● Rubber Duck analizando..."))
    response = _call_llm(messages)

    # Parse verdict from response
    verdict = "REVISAR"
    if "Veredicto: OK" in response or "→ Veredicto: OK" in response:
        verdict = "OK"
    elif "Veredicto: CRÍTICO" in response or "CRÍTICO" in response:
        verdict = "CRÍTICO"

    # Display verdict
    verdict_display = {
        "OK":      GREEN("✅ OK — sin problemas detectados"),
        "REVISAR": YELLOW("⚠️  REVISAR — revisar hallazgos"),
        "CRÍTICO": RED("🚨 CRÍTICO — problemas importantes"),
    }.get(verdict, YELLOW(f"⚠️  {verdict}"))
    print(f"  {verdict_display}\n")

    # Persist finding
    finding = {
        "ts":            time.strftime("%Y-%m-%dT%H:%M:%S"),
        "module":        module_name,
        "file":          str(file_path),
        "loc":           loc,
        "extraction":    extraction_mode,
        "lines":         list(lines) if lines else None,
        "verdict":       verdict,
        "model":         _active_model(),
        "analysis":      response,
        "memory_traces": memory_traces[:500],
    }
    _save_finding(module_name, finding)
    _log_to_advisor(module_name, verdict, response)

    return finding


def _save_finding(module_name: str, finding: dict) -> Path | None:
    """Persist finding to .bago/state/findings/rd_<module>_<ts>.json."""
    try:
        FINDINGS_DIR.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        out = FINDINGS_DIR / f"rd_{module_name}_{ts}.json"
        out.write_text(json.dumps(finding, ensure_ascii=False, indent=2), encoding="utf-8")
        print(DIM(f"  [RD] Finding guardado: {out.name}"))
        return out
    except Exception:
        return None


def _log_to_advisor(module_name: str, verdict: str, response: str) -> None:
    """Log a summary pointer in advisor_context.jsonl."""
    entry = {
        "ts":      time.strftime("%Y-%m-%dT%H:%M:%S"),
        "cmd":     f"rubber-duck {module_name}",
        "rc":      0 if verdict == "OK" else 1,
        "summary": f"[{verdict}] {response[:80]}",
    }
    try:
        with CONTEXT_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        lines = CONTEXT_LOG.read_text(encoding="utf-8").splitlines()
        if len(lines) > MAX_HISTORY_LOG:
            CONTEXT_LOG.write_text("\n".join(lines[-MAX_HISTORY_LOG:]) + "\n", encoding="utf-8")
    except Exception:
        pass


# ── Watch mode ────────────────────────────────────────────────────────────────

def _should_watch(p: Path) -> bool:
    """Return True if this file should be watched for changes."""
    name = p.name
    if name.startswith(".~") or name.endswith((".tmp", ".swp")):
        return False
    if "__pycache__" in str(p):
        return False
    if name.startswith("test_") or name.endswith("_test.py"):
        return False
    return True


def watch(watch_dir: Path) -> None:
    """
    Poll watch_dir for .py file changes and auto-analyze on modification.
    Foreground process — exits on Ctrl+C or SIGTERM.
    """
    print(f"\n{CYAN('  ● Rubber Duck watch mode')} — {DIM(str(watch_dir))}")
    print(DIM(f"  Polling cada {WATCH_INTERVAL}s — Ctrl+C para detener\n"))

    # Seed mtimes
    mtimes: dict[Path, float] = {}
    for p in watch_dir.glob("**/*.py"):
        if _should_watch(p):
            try:
                mtimes[p] = p.stat().st_mtime
            except FileNotFoundError:
                pass

    try:
        while True:
            time.sleep(WATCH_INTERVAL)
            for p in list(watch_dir.glob("**/*.py")):
                if not _should_watch(p):
                    continue
                try:
                    mtime = p.stat().st_mtime
                except FileNotFoundError:
                    continue

                prev = mtimes.get(p)
                if prev is None:
                    # New file — seed mtime, analyze on next change
                    mtimes[p] = mtime
                    continue
                if mtime != prev:
                    mtimes[p] = mtime
                    # Wait one extra cycle to confirm file is stable
                    time.sleep(1)
                    try:
                        stable_mtime = p.stat().st_mtime
                    except FileNotFoundError:
                        continue
                    if stable_mtime == mtime:
                        ts_str = time.strftime("%H:%M:%S")
                        print(f"\n{YELLOW(f'  ● [{ts_str}] Cambio detectado: {p.name}')}")
                        analyze(p)
    except KeyboardInterrupt:
        print(f"\n{DIM('  [RD] Watch mode detenido.')}")


def _find_last_modified_py(search_dir: Path) -> Path | None:
    """Find the most recently modified .py in search_dir (not tests)."""
    candidates = [p for p in search_dir.glob("*.py") if _should_watch(p)]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


# ── Auto-trigger helper (called from toolsmith) ───────────────────────────────

def auto_analyze(file_path: Path) -> None:
    """
    Launch rubber duck analysis in a background subprocess after tool creation.
    Output is redirected to a log file in findings/ — does not block.
    """
    try:
        rd_script = Path(__file__)
        if not rd_script.exists():
            return
        FINDINGS_DIR.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        log_path = FINDINGS_DIR / f"rd_auto_{file_path.stem}_{ts}.log"

        kwargs: dict = {
            "stdout": log_path.open("w", encoding="utf-8"),
            "stderr": subprocess.STDOUT,
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]

        subprocess.Popen(
            [sys.executable, str(rd_script), str(file_path)],
            **kwargs,
        )
        print(DIM(f"  [toolsmith] Rubber duck análisis iniciado → {log_path.name}"))
    except Exception:
        pass  # auto-trigger is best-effort


# ── Self-tests ────────────────────────────────────────────────────────────────

def _self_test() -> int:
    print("Tests bago_rubber_duck.py...")
    fails: list[str] = []

    def ok(n: str) -> None:
        print(f"  OK: {n}")

    def fail(n: str, m: str) -> None:
        fails.append(n)
        print(f"  FAIL: {n}: {m}")

    # T1: secret redaction
    sample = "token=abc123secretxyz password=hunter2 normal text"
    redacted = _redact(sample)
    if "[REDACTED]" in redacted and "normal text" in redacted:
        ok("redact_secrets")
    else:
        fail("redact_secrets", f"got: {redacted}")

    # T2: extract_full — short code fits budget
    short = "# test\ndef foo(): pass"
    code, mode = _extract_smart_code(short)
    if mode == "full" and "foo" in code:
        ok("extract_full")
    else:
        fail("extract_full", f"mode={mode}, code={code[:40]}")

    # T3: extract_structural — large code triggers AST summary
    big = ("import os\ndef " + "x" * 5 + "(): pass\n") * 600
    code, mode = _extract_smart_code(big)
    if mode == "structural" and len(code) <= MAX_CODE_CHARS + 200:
        ok("extract_structural")
    else:
        fail("extract_structural", f"mode={mode} len={len(code)}")

    # T4: extract_fragment — lines slice
    source = "\n".join(f"line_{i} = {i}" for i in range(100))
    code, mode = _extract_smart_code(source, lines=(10, 20))
    if mode == "fragment" and "line_9" in code and "line_19" in code:
        ok("extract_fragment")
    else:
        fail("extract_fragment", f"mode={mode}, got: {code[:60]}")

    # T5: memory traces smoke test
    traces = _gather_memory_traces("bago_rubber_duck")
    if isinstance(traces, str) and len(traces) > 0:
        ok("memory_traces_smoke")
    else:
        fail("memory_traces_smoke", "returned empty or non-str")

    # T6: should_watch filter
    watch_py = _should_watch(Path("my_tool.py"))
    skip_test = _should_watch(Path("test_tool.py"))
    skip_tmp  = _should_watch(Path("file.tmp"))
    if watch_py and not skip_test and not skip_tmp:
        ok("should_watch_filter")
    else:
        fail("should_watch_filter", f"watch={watch_py} test={skip_test} tmp={skip_tmp}")

    # T7: active_model fallback
    m = _active_model()
    if isinstance(m, str) and len(m) > 2:
        ok(f"active_model ({m})")
    else:
        fail("active_model", f"got: {m!r}")

    print(f"\n  {len(fails)} fallos / {7 - len(fails)}/7 pasaron")
    return 0 if not fails else 1


# ── CLI ───────────────────────────────────────────────────────────────────────

USAGE = """
  bago rubber-duck <file.py>             → analiza un archivo completo
  bago rubber-duck <file.py> --lines N:M → analiza un fragmento (líneas N a M)
  bago rubber-duck --last                → último .py modificado en tools/
  bago rubber-duck --watch [dir]         → modo watch (polling, foreground)
  bago rubber-duck --test                → self-tests

  Variables de entorno:
    BAGO_RD_INTERVAL=N     segundos entre polls en watch mode (default 3)
    BAGO_RD_MAX_CHARS=N    máximo chars de código al LLM (default 6000)

  Ejemplos:
    bago rubber-duck bago_advisor.py
    bago rubber-duck toolsmith.py --lines 319:346
    bago rubber-duck --last
    bago rubber-duck --watch .bago/tools
"""


def main(argv: list[str] | None = None) -> int:
    args = list((argv or sys.argv)[1:])

    if not args or args[0] in {"-h", "--help"}:
        print(USAGE)
        return 0

    if args[0] == "--test":
        return _self_test()

    if args[0] == "--watch":
        watch_dir = (
            Path(args[1])
            if len(args) > 1 and not args[1].startswith("--")
            else TOOLS_DIR
        )
        if not watch_dir.exists():
            print(RED(f"  [RD] Directorio no encontrado: {watch_dir}"))
            return 1
        watch(watch_dir)
        return 0

    if args[0] == "--last":
        last = _find_last_modified_py(TOOLS_DIR)
        if not last:
            print(YELLOW("  [RD] No se encontraron archivos .py en tools/"))
            return 1
        result = analyze(last)
        return 0 if result.get("verdict") in ("OK", "REVISAR", "NO_LLM") else 1

    # Positional file argument
    file_arg = args[0]
    file_path = Path(file_arg)

    if not file_path.is_absolute():
        for candidate in [TOOLS_DIR / file_path, Path.cwd() / file_path, file_path]:
            if candidate.exists():
                file_path = candidate.resolve()
                break

    # Parse --lines N:M
    lines: tuple[int, int] | None = None
    i = 1
    while i < len(args):
        a = args[i]
        if a == "--lines" and i + 1 < len(args):
            val = args[i + 1]
            i += 2
        elif a.startswith("--lines="):
            val = a[8:]
            i += 1
        else:
            i += 1
            continue
        try:
            n, m = val.split(":")
            lines = (int(n), int(m))
        except (ValueError, TypeError):
            print(YELLOW(f"  [RD] --lines formato incorrecto: '{val}' (esperado N:M)"))
            return 1
        break

    result = analyze(file_path, lines=lines)
    if result.get("error"):
        return 1
    return 0 if result.get("verdict") in ("OK", "REVISAR", "NO_LLM") else 1


if __name__ == "__main__":
    raise SystemExit(main())
