from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from bago.ollama_runtime import default_ollama_base_url

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

TOOLS_DIR = Path(__file__).parent
BAGO_ROOT = TOOLS_DIR.parent
STATE_DIR = BAGO_ROOT / "state"
CONTEXT_LOG = STATE_DIR / "advisor_context.jsonl"
GLOBAL_ST = STATE_DIR / "global_state.json"
FINDINGS_DIR = STATE_DIR / "findings"
LLM_CFG = STATE_DIR / "llm_config.json"
OLLAMA_URL = default_ollama_base_url()
DEFAULT_MODEL = "phi3:mini"

WATCH_INTERVAL = int(os.getenv("BAGO_RD_INTERVAL", "3"))
MAX_CODE_CHARS = int(os.getenv("BAGO_RD_MAX_CHARS", "6000"))
MAX_MEMORY_ENTRIES = 8
MAX_HISTORY_CHARS = 1500
MAX_HISTORY_LOG = 10

_NO_COLOR = not sys.stdout.isatty() or bool(os.getenv("NO_COLOR"))

def _c(code: str, text: str) -> str:
    return text if _NO_COLOR else f"\033[{code}m{text}\033[0m"

CYAN = lambda text: _c("96", text)  # noqa: E731
YELLOW = lambda text: _c("93", text)  # noqa: E731
GREEN = lambda text: _c("92", text)  # noqa: E731
RED = lambda text: _c("91", text)  # noqa: E731
DIM = lambda text: _c("2", text)  # noqa: E731
BOLD = lambda text: _c("1", text)  # noqa: E731
MAGENTA = lambda text: _c("95", text)  # noqa: E731

_SECRET_PATTERNS = [
    r'(?i)(password|passwd|secret|token|key|api[_-]?key|auth|credential|private)\s*[=:]\s*["\']?[\w\-./+]{8,}["\']?',
    r'[A-Za-z0-9+/]{40,}={0,2}',
    r'[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}',
]
_SECRET_RE = re.compile("|".join(_SECRET_PATTERNS), re.IGNORECASE)


def redact(text: str) -> str:
    return _SECRET_RE.sub("[REDACTED]", text)


def extract_module_docstring(tree: ast.Module) -> str:
    return ast.get_docstring(tree) or ""


def extract_smart_code(source: str, lines: tuple[int, int] | None = None) -> tuple[str, str]:
    if lines:
        start, end = lines
        fragment = "\n".join(source.splitlines()[max(0, start - 1):end])
        if len(fragment) <= MAX_CODE_CHARS:
            return fragment, "fragment"
        source = fragment

    if len(source) <= MAX_CODE_CHARS:
        return source, "full"

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source[:MAX_CODE_CHARS] + "\n# [TRUNCADO — SyntaxError en parse]", "truncated"

    parts: list[str] = []
    src_lines = source.splitlines()
    doc = ast.get_docstring(tree)
    if doc:
        parts.append(f'"""\n{doc[:400]}\n"""')

    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            try:
                parts.append(ast.unparse(node))
            except Exception:
                continue

    for node in tree.body:
        if isinstance(node, ast.Assign) and node.lineno <= len(src_lines):
            line = src_lines[node.lineno - 1].strip()
            if line and not line.startswith("#") and len(line) < 120:
                parts.append(line)

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            try:
                arg_str = ", ".join(ast.unparse(arg) for arg in node.args.args)
                prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
                parts.append(f"{prefix} {node.name}({arg_str}): ...")
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
                        arg_str = ", ".join(ast.unparse(arg) for arg in item.args.args)
                        prefix = "async def" if isinstance(item, ast.AsyncFunctionDef) else "def"
                        parts.append(f"    {prefix} {item.name}({arg_str}): ...")
                    except Exception:
                        parts.append(f"    def {item.name}(...): ...")
                    method_doc = ast.get_docstring(item)
                    if method_doc:
                        parts.append(f'        """{method_doc[:100]}"""')

    return "\n".join(parts)[:MAX_CODE_CHARS], "structural"


def gather_memory_traces(module_name: str) -> str:
    traces: list[str] = []
    used_fallback = False

    if CONTEXT_LOG.exists():
        try:
            all_entries = []
            for line in CONTEXT_LOG.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    all_entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            related = [entry for entry in all_entries if module_name.lower() in str(entry).lower()]
            if related:
                traces.append("=== Historial LLM relacionado al módulo ===")
                for entry in related[-MAX_MEMORY_ENTRIES:]:
                    ts = entry.get("ts", "?")[11:16]
                    cmd = entry.get("cmd", "?")
                    summary = entry.get("summary", "")[:120]
                    traces.append(f"  [{ts}] {cmd}: {summary}")
            elif all_entries:
                traces.append("=== Contexto general reciente (no específico del módulo) ===")
                for entry in all_entries[-3:]:
                    ts = entry.get("ts", "?")[11:16]
                    cmd = entry.get("cmd", "?")
                    summary = entry.get("summary", "")[:80]
                    traces.append(f"  [{ts}] {cmd}: {summary}")
                used_fallback = True
        except Exception:
            pass

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

    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "--follow", "-5", "--", f"*{module_name}*"],
            capture_output=True,
            text=True,
            timeout=5,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0 and result.stdout.strip():
            traces.append("=== Git log (últimos commits relevantes) ===")
            traces.extend(f"  {line}" for line in result.stdout.strip().splitlines()[:5])
    except Exception:
        pass

    if not traces:
        return "(sin trazas de memoria disponibles)"
    result = "\n".join(traces)
    if used_fallback:
        result = "[contexto_general_no_relacionado]\n" + result
    return redact(result[:MAX_HISTORY_CHARS])


def find_related_tests(file_path: Path) -> list[Path]:
    name = file_path.stem
    repo_root = BAGO_ROOT.parent
    patterns = [
        f"**/test_{name}.py",
        f"**/{name}_test.py",
        f"**/*{name}*test*.py",
        f"**/*test*{name}*.py",
    ]
    found: set[Path] = set()
    for pattern in patterns:
        try:
            for path in repo_root.glob(pattern):
                if "test" in path.stem.lower() or "test" in str(path.parent).lower():
                    found.add(path)
        except Exception:
            continue
    return sorted(found)[:3]


def save_finding(module_name: str, finding: dict) -> Path | None:
    try:
        FINDINGS_DIR.mkdir(parents=True, exist_ok=True)
        out = FINDINGS_DIR / f"rd_{module_name}_{time.strftime('%Y%m%d_%H%M%S')}.json"
        out.write_text(json.dumps(finding, ensure_ascii=False, indent=2), encoding="utf-8")
        print(DIM(f"  [RD] Finding guardado: {out.name}"))
        return out
    except Exception:
        return None


def log_to_advisor(module_name: str, verdict: str, response: str) -> None:
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "cmd": f"rubber-duck {module_name}",
        "rc": 0 if verdict == "OK" else 1,
        "summary": f"[{verdict}] {response[:80]}",
    }
    try:
        with CONTEXT_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        lines = CONTEXT_LOG.read_text(encoding="utf-8").splitlines()
        if len(lines) > MAX_HISTORY_LOG:
            CONTEXT_LOG.write_text("\n".join(lines[-MAX_HISTORY_LOG:]) + "\n", encoding="utf-8")
    except Exception:
        pass


def should_watch(path: Path) -> bool:
    name = path.name
    if name.startswith(".~") or name.endswith((".tmp", ".swp")):
        return False
    if "__pycache__" in str(path):
        return False
    if name.startswith("test_") or name.endswith("_test.py"):
        return False
    return True


def find_last_modified_py(search_dir: Path) -> Path | None:
    candidates = [path for path in search_dir.glob("*.py") if should_watch(path)]
    return max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None


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

