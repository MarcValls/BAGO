from __future__ import annotations

"""Exact regression set for `/train`.

This keeps the old behavior honest: phrases already used by the classifier
must still map to the same deterministic intents.
"""

from dataclasses import dataclass
from pathlib import Path
import argparse
import sys


ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bago_core.codegen.task_classifier import classify_code_request


@dataclass(frozen=True)
class Sample:
    intent: str
    text: str
    expected_kind: str


SAMPLES: tuple[Sample, ...] = (
    Sample("inspect", "explica el archivo bago_core/codegen/task_classifier.py", "explain"),
    Sample("modify", "modifica src/demo.py para añadir validación", "modify_file"),
    Sample("create", "crea tests/test_forge_classifier.py", "create_file"),
    Sample("add_test", "añade un test para el clasificador determinista", "add_test"),
    Sample("fix", "traceback en bago_core/codegen/task_classifier.py con SyntaxError expected ':'", "fix_error"),
    Sample("refactor", "refactoriza el módulo sin cambiar la API pública", "refactor_local"),
    Sample("generate", "genera un proyecto nuevo desde cero", "generate_project"),
    Sample("unsafe", "powershell -c Remove-Item -Recurse -Force C:\\temp", "unsafe_or_unsupported"),
    Sample("chat", "hola, ¿qué tal?", "unsafe_or_unsupported"),
)


def _run(fail_only: bool = False, command_filter: str = "") -> int:
    total = 0
    passed = 0
    for sample in SAMPLES:
        if command_filter and command_filter not in sample.intent and command_filter not in sample.text:
            continue
        result = classify_code_request(sample.text, workspace_root=ROOT)
        total += 1
        ok = result.kind == sample.expected_kind
        passed += int(ok)
        if not fail_only or not ok:
            status = "PASS" if ok else f"FAIL expected={sample.expected_kind} got={result.kind}"
            print(f"{sample.intent}: {sample.text} -> {status}")
    print(f"Exact regression: {passed}/{total}")
    return 0 if passed == total else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fail-only", action="store_true")
    parser.add_argument("command", nargs="?", default="")
    args = parser.parse_args(argv)
    return _run(fail_only=args.fail_only, command_filter=args.command.lstrip("/"))


if __name__ == "__main__":
    raise SystemExit(main())
