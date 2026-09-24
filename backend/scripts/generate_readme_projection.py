#!/usr/bin/env python3
"""Generate the machine-derived README truth block and projection contract.

Stable explanatory prose stays hand-maintained. Volatile product facts are
projected from canonical repository sources. CI uses --check so canonical
changes cannot silently leave README.md stale.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
OUTPUT = ROOT / "backend" / "contracts" / "readme_projection.v1.json"

START = "<!-- BAGO:README_TRUTH:START -->"
END = "<!-- BAGO:README_TRUTH:END -->"

VERSION = ROOT / "release_version.txt"
PACKAGE = ROOT / "package.json"
FRONTEND_PACKAGE = ROOT / "frontend" / "package.json"
CANONICAL_CI = ROOT / ".github" / "workflows" / "canonical-ci.yml"
PROVIDERS = ROOT / "backend" / ".bago" / "core" / "session_utils.py"
EFFECTS = ROOT / "backend" / ".bago" / "contracts" / "bago.effect-registry.v1.json"

AUTH_CONTRACT = ROOT / "backend" / "docs" / "contracts" / "user_authorization_provenance.v1.md"
GATEWAY_CONTRACT = ROOT / "backend" / "docs" / "contracts" / "execution_gateway.v2.md"
SCHEDULER_CONTRACT = ROOT / "backend" / "docs" / "contracts" / "scheduler_delegation.v1.md"
UNIFICATION_PLAN = ROOT / "backend" / "docs" / "contracts" / "execution_gateway_unification_plan.v1.md"


class ProjectionError(RuntimeError):
    pass


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ProjectionError(f"cannot read {path.relative_to(ROOT)}: {exc}") from exc


def _json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(_read(path))
    except json.JSONDecodeError as exc:
        raise ProjectionError(f"invalid JSON in {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ProjectionError(f"{path.relative_to(ROOT)} must contain a JSON object")
    return payload


def _canonical_version() -> str:
    version = _read(VERSION).strip()
    if not version:
        raise ProjectionError("release_version.txt is empty")
    return version


def _engine(package: dict[str, Any], key: str) -> str:
    engines = package.get("engines")
    if not isinstance(engines, dict):
        raise ProjectionError("package engines are missing")
    value = engines.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ProjectionError(f"engine {key!r} is missing")
    return value.strip()


def _python_ci_version() -> str:
    match = re.search(r'(?m)^\s*PYTHON_VERSION:\s*[\'"]?([^\'"\s]+)', _read(CANONICAL_CI))
    if not match:
        raise ProjectionError("PYTHON_VERSION not found in canonical-ci.yml")
    return match.group(1).strip()


def _provider_ids() -> list[str]:
    try:
        tree = ast.parse(_read(PROVIDERS), filename=str(PROVIDERS))
    except SyntaxError as exc:
        raise ProjectionError(f"cannot parse provider registry: {exc}") from exc

    for node in tree.body:
        target = None
        value = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            target = node.target
            value = node.value
        if not isinstance(target, ast.Name) or target.id != "ADAPTER_REGISTRY":
            continue
        if not isinstance(value, ast.Dict):
            raise ProjectionError("ADAPTER_REGISTRY is not a literal dict")
        providers: list[str] = []
        for key in value.keys:
            if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
                raise ProjectionError("ADAPTER_REGISTRY contains a non-literal provider key")
            providers.append(key.value)
        if not providers:
            raise ProjectionError("ADAPTER_REGISTRY is empty")
        return providers
    raise ProjectionError("ADAPTER_REGISTRY not found")


def _contract_status(path: Path) -> str:
    for raw in _read(path).splitlines():
        line = raw.strip()
        if line.startswith("Estado:"):
            return line.split(":", 1)[1].strip().replace("**", "").strip()
    raise ProjectionError(f"Estado not found in {path.relative_to(ROOT)}")


def _state_token(text: str, name: str) -> str:
    match = re.search(rf"{re.escape(name)}\s*=\s*([A-Z0-9_]+)", text)
    if not match:
        raise ProjectionError(f"{name} not found in canonical contracts")
    return match.group(1).strip()


def _next_gateway_phase() -> str:
    match = re.search(r"(?m)^##\s+P5\s+\u2014\s+(.+?)\s*$", _read(UNIFICATION_PLAN))
    if not match:
        raise ProjectionError("P5 heading not found in execution gateway unification plan")
    return f"P5 \u2014 {match.group(1).strip()}"


def build_projection() -> dict[str, Any]:
    root_pkg = _json(PACKAGE)
    front_pkg = _json(FRONTEND_PACKAGE)
    effects = _json(EFFECTS)
    effect_rows = effects.get("effects")
    if not isinstance(effect_rows, list) or not effect_rows:
        raise ProjectionError("effect registry has no effects")

    scheduler_text = _read(SCHEDULER_CONTRACT)
    schedule_effect = next(
        (
            row
            for row in effect_rows
            if isinstance(row, dict) and row.get("id") == "schedule.delegate"
        ),
        None,
    )
    if not isinstance(schedule_effect, dict):
        raise ProjectionError("schedule.delegate missing from effect registry")

    return {
        "contract": "bago.readme-projection.v1",
        "generated_from": [
            "release_version.txt",
            "package.json",
            "frontend/package.json",
            ".github/workflows/canonical-ci.yml",
            "backend/.bago/core/session_utils.py:ADAPTER_REGISTRY",
            "backend/.bago/contracts/bago.effect-registry.v1.json",
            "backend/docs/contracts/user_authorization_provenance.v1.md",
            "backend/docs/contracts/execution_gateway.v2.md",
            "backend/docs/contracts/scheduler_delegation.v1.md",
            "backend/docs/contracts/execution_gateway_unification_plan.v1.md",
        ],
        "product": {
            "version": _canonical_version(),
            "node_engine": _engine(root_pkg, "node"),
            "npm_engine": _engine(front_pkg, "npm"),
            "python_ci": _python_ci_version(),
        },
        "providers": _provider_ids(),
        "governance": {
            "effect_registry_status": str(effects.get("status") or "").strip(),
            "effect_registry_version": str(effects.get("version") or "").strip(),
            "effect_count": len(effect_rows),
            "authorization_boundary_status": _contract_status(AUTH_CONTRACT),
            "execution_gateway_status": _contract_status(GATEWAY_CONTRACT),
            "scheduler_delegation_status": _contract_status(SCHEDULER_CONTRACT),
            "unique_execution_boundary": _state_token(
                scheduler_text, "UNIQUE_EXECUTION_BOUNDARY"
            ),
            "strong_human_identity_verified": _state_token(
                scheduler_text, "STRONG_HUMAN_IDENTITY_VERIFIED"
            ),
            "schedule_delegate": {
                "risk_level": str(schedule_effect.get("risk_level") or ""),
                "authorization_mode": str(schedule_effect.get("authorization_mode") or ""),
                "delegable": bool(schedule_effect.get("delegable")),
            },
            "next_gateway_phase": _next_gateway_phase(),
        },
    }


def _badge_value(value: str) -> str:
    return value.replace("-", "--").replace(">=", "").replace(" ", "%20").replace("+", "%2B")


def render_block(projection: dict[str, Any]) -> str:
    product = projection["product"]
    governance = projection["governance"]
    provider_text = " \u00b7 ".join(f"`{item}`" for item in projection["providers"])

    lines = [
        START,
        "<!-- Generated by backend/scripts/generate_readme_projection.py. Do not edit this block manually. -->",
        "",
        f"[![Version](https://img.shields.io/badge/version-{_badge_value(product['version'])}-blue)]()",
        "[![CI](https://github.com/MarcValls/BAGO/actions/workflows/canonical-ci.yml/badge.svg)](https://github.com/MarcValls/BAGO/actions/workflows/canonical-ci.yml)",
        f"[![Python CI](https://img.shields.io/badge/python_CI-{_badge_value(product['python_ci'])}-blue)]()",
        f"[![Node](https://img.shields.io/badge/node-{_badge_value(product['node_engine'])}-green)]()",
        "[![README truth](https://img.shields.io/badge/README-generated%20%2B%20drift--checked-blueviolet)]()",
        "[![License](https://img.shields.io/badge/license-Proprietary-red)]()",
        "",
        "### Estado canonico generado",
        "",
        "| Dato | Estado | Fuente canonica |",
        "|---|---|---|",
        f"| Version de producto | `{product['version']}` | `release_version.txt` |",
        f"| Python en Canonical CI | `{product['python_ci']}` | `.github/workflows/canonical-ci.yml` |",
        f"| Node.js | `{product['node_engine']}` | `package.json` |",
        f"| npm | `{product['npm_engine']}` | `frontend/package.json` |",
        f"| Effect Registry | `{governance['effect_registry_status']}` \u00b7 v`{governance['effect_registry_version']}` \u00b7 {governance['effect_count']} efectos | `bago.effect-registry.v1.json` |",
        f"| Authorization Boundary | `{governance['authorization_boundary_status']}` | `user_authorization_provenance.v1.md` |",
        f"| ExecutionGateway | `{governance['execution_gateway_status']}` | `execution_gateway.v2.md` |",
        f"| Scheduler + DelegationGrant | `{governance['scheduler_delegation_status']}` | `scheduler_delegation.v1.md` |",
        f"| Frontera unica de ejecucion | `{governance['unique_execution_boundary']}` | contratos P1-P4 |",
        f"| Strong Human Identity Proof | `{governance['strong_human_identity_verified']}` | P13 pendiente |",
        f"| Siguiente fase de unificacion | `{governance['next_gateway_phase']}` | `execution_gateway_unification_plan.v1.md` |",
        "",
        f"**Proveedores registrados:** {provider_text}",
        "",
        (
            "**E6 `schedule.delegate`:** "
            f"riesgo `{governance['schedule_delegate']['risk_level']}`, "
            f"autorizacion `{governance['schedule_delegate']['authorization_mode']}`, "
            f"delegable=`{str(governance['schedule_delegate']['delegable']).lower()}`."
        ),
        "",
        "> Este bloque es una proyeccion de fuentes canonicas. Si cualquiera de ellas cambia y el README no se regenera, CI falla.",
        END,
    ]
    return "\n".join(lines)


def _replace_block(readme: str, block: str) -> str:
    if readme.count(START) != 1 or readme.count(END) != 1:
        raise ProjectionError("README truth markers must exist exactly once")
    start = readme.index(START)
    end = readme.index(END, start) + len(END)
    return readme[:start] + block + readme[end:]


def _expected_json(projection: dict[str, Any]) -> str:
    return json.dumps(projection, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def check(projection: dict[str, Any]) -> int:
    errors: list[str] = []
    if not OUTPUT.exists() or _read(OUTPUT) != _expected_json(projection):
        errors.append(f"{OUTPUT.relative_to(ROOT)} drifted")

    current_readme = _read(README)
    if current_readme != _replace_block(current_readme, render_block(projection)):
        errors.append("README.md generated truth block drifted")

    if errors:
        for item in errors:
            print(f"[readme-projection] {item}", file=sys.stderr)
        print(
            "[readme-projection] run: python backend/scripts/generate_readme_projection.py",
            file=sys.stderr,
        )
        return 1
    print("[readme-projection] PASS")
    return 0


def write(projection: dict[str, Any]) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(_expected_json(projection), encoding="utf-8")
    current = _read(README)
    README.write_text(_replace_block(current, render_block(projection)), encoding="utf-8")
    print(f"[readme-projection] wrote {OUTPUT.relative_to(ROOT)} and README.md")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        projection = build_projection()
        if args.check:
            return check(projection)
        write(projection)
        return 0
    except ProjectionError as exc:
        print(f"[readme-projection] error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
