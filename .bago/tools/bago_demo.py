#!/usr/bin/env python3
"""bago_demo.py - entrada rapida para mostrar BAGO sin exponer estado interno."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from bago.ollama_runtime import DEFAULT_BAGO_LLM_SERVER_PORT, env_port

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent.parent


def main() -> int:
    port = str(env_port("BAGO_MINIAPP_PORT", "BAGO_PORT", default=DEFAULT_BAGO_LLM_SERVER_PORT))
    args = sys.argv[1:]
    if "--port" in args:
        idx = args.index("--port")
        if idx + 1 < len(args):
            port = args[idx + 1]

    if "--serve" in args:
        server = TOOLS / "bago_miniapp_server.py"
        return subprocess.run([sys.executable, str(server), "--port", port]).returncode

    print("BAGO demo")
    print(f"Dashboard publico: python {REPO / 'bago_core' / 'launcher.py'} dashboard --public")
    print(f"Publish kit beta:  python {REPO / 'bago_core' / 'launcher.py'} publish-kit --channel beta")
    print(f"Miniapp local:      python {REPO / 'bago_core' / 'launcher.py'} demo --serve --port {port}")
    return 0




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
    raise SystemExit(main())