from __future__ import annotations

"""Novel phrase split for `/train`.

This script deliberately evaluates phrases that were not copied from the
classifier's keyword tables. The goal is not to fake learning, but to
measure whether the current deterministic classifier keeps behaving on
paraphrases, negations, and ambiguous inputs.
"""

from dataclasses import dataclass
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bago_core.codegen.task_classifier import classify_code_request


@dataclass(frozen=True)
class Sample:
    split: str
    text: str
    expected_kind: str


SAMPLES: tuple[Sample, ...] = (
    Sample("TRAIN", "Necesito revisar el archivo docs/guia.md antes de tocar nada", "inspect"),
    Sample("TRAIN", "Quiero crear un fichero nuevo para registrar la sesión", "create_file"),
    Sample("TRAIN", "Hay un traceback en src/app.py con TypeError", "fix_error"),
    Sample("VAL", "haz cleanup local del módulo docs/guia.md", "refactor_local"),
    Sample("VAL", "crea un test nuevo para el flujo de contexto", "add_test"),
    Sample("VAL", "Genera una app base desde cero", "generate_project"),
    Sample("TEST", "No cambies nada: solo dime qué ves en README.md", "inspect"),
    Sample("TEST", "modifica src/demo.py para añadir validación", "modify_file"),
    Sample("TEST", "Esto parece inseguro: powershell -c Remove-Item -Recurse -Force C:\\temp", "unsafe_or_unsupported"),
)


def _score(sample: Sample) -> tuple[bool, str]:
    result = classify_code_request(sample.text, workspace_root=ROOT)
    ok = result.kind == sample.expected_kind
    status = "PASS" if ok else f"FAIL expected={sample.expected_kind} got={result.kind}"
    return ok, f"[{sample.split}] {sample.text} -> {status} ({result.confidence:.2f})"


def main() -> int:
    totals = {"TRAIN": [0, 0], "VAL": [0, 0], "TEST": [0, 0]}
    for sample in SAMPLES:
        ok, line = _score(sample)
        print(line)
        totals[sample.split][1] += 1
        totals[sample.split][0] += int(ok)

    print("SPLIT: TRAIN")
    print("SPLIT: VAL")
    print("SPLIT: TEST")
    for split in ("TRAIN", "VAL", "TEST"):
        ok, total = totals[split]
        print(f"{split}: {ok}/{total}")

    if all(ok == total for ok, total in totals.values()):
        print("Split test aprobado")
        return 0

    print("Split test con observaciones")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
