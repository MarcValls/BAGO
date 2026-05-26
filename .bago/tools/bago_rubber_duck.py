#!/usr/bin/env python3
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

"""bago_rubber_duck.py — Auto rubber duck debugging para BAGO."""

import subprocess
import sys
import time
from pathlib import Path

from _cwd import get_user_cwd

from _duck_analyzer import active_model, analyze
from _duck_collector import (
    DIM,
    FINDINGS_DIR,
    MAX_CODE_CHARS,
    RED,
    TOOLS_DIR,
    WATCH_INTERVAL,
    YELLOW,
    extract_smart_code,
    find_last_modified_py,
    gather_memory_traces,
    redact,
    should_watch,
)

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


def watch(watch_dir: Path) -> None:
    print(f"\n{YELLOW('  ● Rubber Duck watch mode')} — {DIM(str(watch_dir))}")
    print(DIM(f"  Polling cada {WATCH_INTERVAL}s — Ctrl+C para detener\n"))

    mtimes: dict[Path, float] = {}
    for path in watch_dir.glob("**/*.py"):
        if should_watch(path):
            try:
                mtimes[path] = path.stat().st_mtime
            except FileNotFoundError:
                pass

    try:
        while True:
            time.sleep(WATCH_INTERVAL)
            for path in list(watch_dir.glob("**/*.py")):
                if not should_watch(path):
                    continue
                try:
                    mtime = path.stat().st_mtime
                except FileNotFoundError:
                    continue
                prev = mtimes.get(path)
                if prev is None:
                    mtimes[path] = mtime
                    continue
                if mtime != prev:
                    mtimes[path] = mtime
                    time.sleep(1)
                    try:
                        stable_mtime = path.stat().st_mtime
                    except FileNotFoundError:
                        continue
                    if stable_mtime == mtime:
                        _ts = time.strftime("%H:%M:%S")
                        print(f"\n{YELLOW(f'  ● [{_ts}] Cambio detectado: {path.name}')}")
                        analyze(path)
    except KeyboardInterrupt:
        print(f"\n{DIM('  [RD] Watch mode detenido.')}")


def auto_analyze(file_path: Path) -> None:
    try:
        rd_script = Path(__file__)
        if not rd_script.exists():
            return
        FINDINGS_DIR.mkdir(parents=True, exist_ok=True)
        log_path = FINDINGS_DIR / f"rd_auto_{file_path.stem}_{int(time.time())}.log"
        kwargs: dict = {"stdout": log_path.open("w", encoding="utf-8"), "stderr": subprocess.STDOUT}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
        subprocess.Popen([sys.executable, str(rd_script), str(file_path)], **kwargs)
        print(DIM(f"  [toolsmith] Rubber duck análisis iniciado → {log_path.name}"))
    except Exception:
        pass


def _self_test() -> int:
    print("Tests bago_rubber_duck.py...")
    fails: list[str] = []

    def ok(name: str) -> None:
        print(f"  OK: {name}")

    def fail(name: str, message: str) -> None:
        fails.append(name)
        print(f"  FAIL: {name}: {message}")

    redacted = redact("token=abc123secretxyz password=hunter2 normal text")
    if "[REDACTED]" in redacted and "normal text" in redacted:
        ok("redact_secrets")
    else:
        fail("redact_secrets", f"got: {redacted}")

    code, mode = extract_smart_code("# test\ndef foo(): pass")
    if mode == "full" and "foo" in code:
        ok("extract_full")
    else:
        fail("extract_full", f"mode={mode}, code={code[:40]}")

    big = ("import os\ndef xxxxx(): pass\n") * 600
    code, mode = extract_smart_code(big)
    if mode == "structural" and len(code) <= MAX_CODE_CHARS + 200:
        ok("extract_structural")
    else:
        fail("extract_structural", f"mode={mode} len={len(code)}")

    source = "\n".join(f"line_{i} = {i}" for i in range(100))
    code, mode = extract_smart_code(source, lines=(10, 20))
    if mode == "fragment" and "line_9" in code and "line_19" in code:
        ok("extract_fragment")
    else:
        fail("extract_fragment", f"mode={mode}, got: {code[:60]}")

    traces = gather_memory_traces("bago_rubber_duck")
    if isinstance(traces, str) and len(traces) > 0:
        ok("memory_traces_smoke")
    else:
        fail("memory_traces_smoke", "returned empty or non-str")

    watch_py = should_watch(Path("my_tool.py"))
    skip_test = should_watch(Path("test_tool.py"))
    skip_tmp = should_watch(Path("file.tmp"))
    if watch_py and not skip_test and not skip_tmp:
        ok("should_watch_filter")
    else:
        fail("should_watch_filter", f"watch={watch_py} test={skip_test} tmp={skip_tmp}")

    model = active_model()
    if isinstance(model, str) and len(model) > 2:
        ok(f"active_model ({model})")
    else:
        fail("active_model", f"got: {model!r}")

    print(f"\n  {len(fails)} fallos / {7 - len(fails)}/7 pasaron")
    return 0 if not fails else 1


def main(argv: list[str] | None = None) -> int:
    args = list((argv or sys.argv)[1:])
    if not args or args[0] in {"-h", "--help"}:
        print(USAGE)
        return 0
    if args[0] == "--test":
        return _self_test()
    if args[0] == "--watch":
        watch_dir = Path(args[1]) if len(args) > 1 and not args[1].startswith("--") else TOOLS_DIR
        if not watch_dir.exists():
            print(RED(f"  [RD] Directorio no encontrado: {watch_dir}"))
            return 1
        watch(watch_dir)
        return 0
    if args[0] == "--last":
        last = find_last_modified_py(TOOLS_DIR)
        if not last:
            print(YELLOW("  [RD] No se encontraron archivos .py en tools/"))
            return 1
        result = analyze(last)
        return 0 if result.get("verdict") in ("OK", "REVISAR", "NO_LLM") else 1

    file_path = Path(args[0])
    if not file_path.is_absolute():
        user_cwd = get_user_cwd()
        for candidate in [TOOLS_DIR / file_path, user_cwd / file_path, file_path]:
            if candidate.exists():
                file_path = candidate.resolve()
                break

    lines: tuple[int, int] | None = None
    i = 1
    while i < len(args):
        current = args[i]
        if current == "--lines" and i + 1 < len(args):
            value = args[i + 1]
            i += 2
        elif current.startswith("--lines="):
            value = current[8:]
            i += 1
        else:
            i += 1
            continue
        try:
            start, end = value.split(":")
            lines = (int(start), int(end))
        except (ValueError, TypeError):
            print(YELLOW(f"  [RD] --lines formato incorrecto: '{value}' (esperado N:M)"))
            return 1
        break

    result = analyze(file_path, lines=lines)
    if result.get("error"):
        return 1
    return 0 if result.get("verdict") in ("OK", "REVISAR", "NO_LLM") else 1


if __name__ == "__main__":
    raise SystemExit(main())
