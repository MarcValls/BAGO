#!/usr/bin/env python3
"""Generate the machine-owned truth projection embedded in README.md.

Sources:
- release_version.txt
- package.json engines.node
- backend/docs/contracts/execution_gateway_unification_plan.v1.md

Only the marked README block is generated. The rest of README.md remains
human-authored product/release documentation.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
from pathlib import Path


BEGIN = "<!-- BEGIN GENERATED: README_TRUTH -->"
END = "<!-- END GENERATED: README_TRUTH -->"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _node_minimum(root: Path) -> str:
    package = json.loads(_read(root / "package.json"))
    engine = str(package.get("engines", {}).get("node", "")).strip()
    match = re.fullmatch(r">=\s*([0-9]+(?:\.[0-9]+){1,2})", engine)
    if not match:
        raise ValueError(f"Unsupported package.json engines.node format: {engine!r}")
    return match.group(1)


def _plan_state_and_table(root: Path) -> tuple[str, list[str], list[str]]:
    path = root / "backend/docs/contracts/execution_gateway_unification_plan.v1.md"
    text = _read(path)
    state_match = re.search(r"^Estado:\s*(.+)$", text, flags=re.MULTILINE)
    if not state_match:
        raise ValueError(f"Missing Estado line in {path}")
    state = state_match.group(1).strip("* ")

    section_match = re.search(
        r"^## Estado lineal actual\s*$\n(?P<body>.*?)(?=^##\s+)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    if not section_match:
        raise ValueError(f"Missing Estado lineal actual section in {path}")
    body = section_match.group("body")

    table_lines = [
        line.rstrip()
        for line in body.splitlines()
        if line.startswith("|")
    ]
    if len(table_lines) < 3:
        raise ValueError("Execution-gateway status table is missing or incomplete")

    global_match = re.search(
        r"Estado global:\s*(?P<global>.*)$",
        body,
        flags=re.DOTALL,
    )
    if not global_match:
        raise ValueError("Execution-gateway global status block is missing")
    global_lines = re.findall(
        r"^\s*`([^`]+)`\s*$",
        global_match.group("global"),
        flags=re.MULTILINE,
    )
    if not global_lines:
        raise ValueError("Execution-gateway global status values are missing")

    return state, table_lines, global_lines


def render(root: Path) -> str:
    version = _read(root / "release_version.txt").strip()
    if not version:
        raise ValueError("release_version.txt is empty")
    node_min = _node_minimum(root)
    plan_state, table_lines, global_lines = _plan_state_and_table(root)

    rows = "\n".join(table_lines)
    globals_md = "\n".join(f"- `{value}`" for value in global_lines)

    return f"""{BEGIN}
# BAGO v{version} — control plane de IA local y gobernado

[![Version](https://img.shields.io/badge/version-{version}-blue)]()
[![CI](https://github.com/MarcValls/BAGO/actions/workflows/canonical-ci.yml/badge.svg)](https://github.com/MarcValls/BAGO/actions/workflows/canonical-ci.yml)
[![Python](https://img.shields.io/badge/python-3.14%2B-blue)]()
[![Node](https://img.shields.io/badge/node-{node_min}%2B-green)]()
[![Execution boundary](https://img.shields.io/badge/execution%20boundary-migration%20open-orange)]()
[![License](https://img.shields.io/badge/license-Proprietary-red)]()

**BAGO** es un plano de control de IA local, orientado a sesión, contexto, proveedores, capacidades, permisos, evidencia y ejecución gobernada. La sesión y el backend mantienen la verdad operacional; los LLM y proveedores son motores intercambiables que pueden proponer trabajo, pero no deben convertirse por sí solos en autoridad de ejecución.

Versión canónica del repositorio: **v{version}**, resuelta desde `release_version.txt`. `main` puede contener trabajo posterior a la última release pública; publicación y distribución se documentan por separado en la sección de releases.

---

## Estado actual de `main`

Estado del plan lineal: `{plan_state}`.

Cadena de ejecución gobernada materializada:

```text
intent / task
  -> ExecutionRequest
  -> AuthorizationChallenge
  -> UserAuthorizationProof
  -> AuthorizationDecision
  -> Permit
  -> ExecutionGateway
  -> EffectAdapter
  -> material effect
  -> Receipt
```

Para ejecución programada:

```text
direct user decision
  -> schedule.delegate
  -> parent Permit
  -> ExecutionGateway
  -> DelegationGrant
  -> scheduler trigger
  -> child ExecutionRequest
  -> child Permit
  -> ExecutionGateway
  -> EffectAdapter
  -> effect
```

{rows}

Estado global de seguridad de ejecución:

{globals_md}

BAGO tiene una frontera cerrada para las rutas ya migradas. Mientras `UNIQUE_EXECUTION_BOUNDARY = NOT_YET`, no debe afirmarse que `ExecutionGateway` gobierna todos los efectos del sistema.

{END}"""


def _replace_projection(readme: str, projection: str) -> str:
    if BEGIN not in readme or END not in readme:
        raise ValueError(
            f"README.md must contain exactly one {BEGIN!r} / {END!r} block"
        )
    if readme.count(BEGIN) != 1 or readme.count(END) != 1:
        raise ValueError("README.md contains duplicated generated truth markers")
    start = readme.index(BEGIN)
    end = readme.index(END) + len(END)
    return readme[:start] + projection + readme[end:]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    path = root / "README.md"

    try:
        current = _read(path)
        expected_projection = render(root)
        expected = _replace_projection(current, expected_projection)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}")
        return 2

    if args.check:
        if current != expected:
            print(
                "error: README generated truth projection drifted. "
                "Run: python scripts/generate_readme_projection.py"
            )
            diff = difflib.unified_diff(
                current.splitlines(),
                expected.splitlines(),
                fromfile="README.md",
                tofile="README.md (generated)",
                lineterm="",
            )
            for line in diff:
                print(line)
            return 2
        print("README generated truth projection PASS")
        return 0

    path.write_text(expected, encoding="utf-8")
    print("README generated truth projection updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
