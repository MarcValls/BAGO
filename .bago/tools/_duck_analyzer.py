from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import ast
import json
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path

from bago.ollama_runtime import DEFAULT_OLLAMA_PORT

from _duck_collector import (
    BOLD,
    CYAN,
    DEFAULT_MODEL,
    DIM,
    GREEN,
    LLM_CFG,
    MAGENTA,
    OLLAMA_URL,
    RED,
    YELLOW,
    extract_module_docstring,
    extract_smart_code,
    find_related_tests,
    gather_memory_traces,
    log_to_advisor,
    redact,
    save_finding,
)


def active_model() -> str:
    try:
        cfg = json.loads(LLM_CFG.read_text(encoding="utf-8"))
        mid = cfg.get("active_model", "")
        aliases = {
            "phi3-mini": "phi3:mini",
            "qwen25-coder": "qwen2.5-coder:7b",
            "llama32-3b": "llama3.2:3b",
            "deepseek-coder": "deepseek-coder:6.7b",
        }
        return aliases.get(mid, mid) if mid else DEFAULT_MODEL
    except Exception:
        return DEFAULT_MODEL


def ollama_alive() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", DEFAULT_OLLAMA_PORT), timeout=1):
            return True
    except OSError:
        return False


def _stream_ollama(messages: list[dict], model: str):
    payload = json.dumps({"model": model, "messages": messages, "stream": True}).encode()
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
            except json.JSONDecodeError:
                continue
            chunk = obj.get("message", {}).get("content", "")
            if chunk:
                yield chunk


def call_llm(messages: list[dict]) -> str:
    model = active_model()
    if not ollama_alive():
        print(RED("  [RD] Ollama no responde. Arranca con: bago llm start"))
        return ""
    full: list[str] = []
    print()
    try:
        for chunk in _stream_ollama(messages, model):
            print(chunk, end="", flush=True)
            full.append(chunk)
    except urllib.error.URLError as exc:
        print(RED(f"\n  [RD-E] Error de conexión: {exc}"))
    except Exception as exc:
        print(RED(f"\n  [RD-E] {exc}"))
    print("\n")
    return "".join(full)


def analyze(file_path: Path, lines: tuple[int, int] | None = None) -> dict:
    if not file_path.exists():
        print(RED(f"  [RD] Archivo no encontrado: {file_path}"))
        return {"error": "file_not_found", "path": str(file_path)}

    try:
        source = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        print(RED(f"  [RD] Error leyendo archivo: {exc}"))
        return {"error": str(exc), "path": str(file_path)}

    module_doc = ""
    try:
        module_doc = extract_module_docstring(ast.parse(source))
    except SyntaxError:
        pass

    code_for_llm, extraction_mode = extract_smart_code(source, lines)
    code_for_llm = redact(code_for_llm)
    module_name = file_path.stem
    memory_traces = gather_memory_traces(module_name)
    related_tests = find_related_tests(file_path)
    loc = len(source.splitlines())
    fragment_note = f" (líneas {lines[0]}-{lines[1]})" if lines else ""

    print(f"\n{BOLD(CYAN('╔══ RUBBER DUCK DEBUG ══════════════════════════════════╗'))}")
    print(f"{BOLD('  Módulo :')} {MAGENTA(module_name)}")
    print(f"{BOLD('  Archivo:')} {DIM(str(file_path))}")
    print(f"{BOLD('  LOC    :')} {loc}{fragment_note}  [{extraction_mode}]")
    if related_tests:
        print(f"{BOLD('  Tests  :')} {DIM(', '.join(test.name for test in related_tests))}")
    print(f"{BOLD(CYAN('╚══════════════════════════════════════════════════════╝'))}")

    if not ollama_alive():
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
        save_finding(module_name, finding)
        return finding

    docstring_section = f"\nIntención declarada (docstring):\n{module_doc[:500]}\n" if module_doc else ""
    memory_section = (
        f"\nTrazas de memoria relacionadas:\n{memory_traces}\n"
        if memory_traces and memory_traces != "(sin trazas de memoria disponibles)"
        else ""
    )
    test_info = "\nTests relacionados encontrados:\n" + "\n".join(f"  - {test}" for test in related_tests) if related_tests else ""
    prompt = (
        "Eres un rubber duck debugger especializado en código Python del framework BAGO.\n"
        "Tu análisis tiene 4 secciones OBLIGATORIAS:\n\n"
        "**1. REPITE** (en tus propias palabras, paso a paso):\n"
        "Describe qué hace este código como si se lo explicaras a alguien que no lo conoce.\n"
        "Usa viñetas numeradas. Sé concreto sobre el flujo de ejecución.\n\n"
        "**2. DETECTA** (pasos faltantes / saltos de lógica):\n"
        "¿Qué casos edge no están cubiertos? ¿Hay suposiciones implícitas que podrían fallar?\n"
        "Marca cada hallazgo con: ⚠ POSIBLE FALLO: <descripción>\n\n"
        "**3. COMPARA** (implementación vs intención):\n"
        "¿Coincide lo que hace el código con lo que declara el docstring/comentarios?\n"
        "Si hay discrepancia: ❌ INCONSISTENCIA: <descripción>\n\n"
        "**4. ALERTA** (patterns problemáticos):\n"
        "Race conditions, encoding issues, error handling incompleto, dependencias frágiles.\n"
        "Marca con: 🔴 ALERTA: <descripción>\n\n"
        f"Módulo: {module_name}{fragment_note}"
        f"{docstring_section}{memory_section}{test_info}\n\n"
        f"Código:\n```python\n{code_for_llm}\n```\n\n"
        "Analiza el código. Si está correcto, dilo explícitamente en cada sección.\n"
        "Termina con: → Veredicto: OK | REVISAR | CRÍTICO"
    )
    messages = [
        {
            "role": "system",
            "content": "Eres un experto debugger Python. Analizas código con precisión técnica. Respondes en español. Eres conciso pero completo. Identificas problemas reales, no de estilo.",
        },
        {"role": "user", "content": prompt},
    ]

    print(CYAN("\n  ● Rubber Duck analizando..."))
    response = call_llm(messages)
    verdict = "OK" if "Veredicto: OK" in response or "→ Veredicto: OK" in response else "CRÍTICO" if "Veredicto: CRÍTICO" in response or "CRÍTICO" in response else "REVISAR"
    verdict_display = {
        "OK": GREEN("✅ OK — sin problemas detectados"),
        "REVISAR": YELLOW("⚠️  REVISAR — revisar hallazgos"),
        "CRÍTICO": RED("🚨 CRÍTICO — problemas importantes"),
    }.get(verdict, YELLOW(f"⚠️  {verdict}"))
    print(f"  {verdict_display}\n")

    finding = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "module": module_name,
        "file": str(file_path),
        "loc": loc,
        "extraction": extraction_mode,
        "lines": list(lines) if lines else None,
        "verdict": verdict,
        "model": active_model(),
        "analysis": response,
        "memory_traces": memory_traces[:500],
    }
    save_finding(module_name, finding)
    log_to_advisor(module_name, verdict, response)
    return finding
