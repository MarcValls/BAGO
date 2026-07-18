#!/usr/bin/env python3
"""FASE 9.2: report + manifest payload builders (R0, R1, R8).

This module owns the *formatting* of the evidence bundle: it composes
the markdown report and the manifest.json payload. It has no side
effects: it never reads or writes files (R0). All filesystem IO is
delegated to :mod:`bago_core.evidence_io` by the orchestrator.

Owns:
- `_build_report_header`, `_format_checks_lines`, `_format_commands_lines`
- `_build_direct_response_section`, `_build_plan_section`
- `_build_report`
- `_validation_commands`
- `_build_manifest_dict`
- The four baseline checks: `_session_runtime_check`,
  `_direct_assistance_check`, `_knowledge_persistence_check`,
  `_session_save_check`
- `_simulated_mode_check`, `_live_mode_check`

R0-R10:
- R0: <250 lines (target 200).
- R1: depends only on stdlib + `evidence_io.now_iso` (for timestamps).
- R8: no `print()`, no `open()`, no `subprocess`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from bago_core.evidence_io import now_iso
from bago_core.evidence_model import ObjectiveProfile
from bago_core.versioning import read_release_version


def _build_report_header(
    *,
    profile: ObjectiveProfile,
    mode: str,
    provider: str,
    model: str,
    session_id: str,
    output_dir: Path,
) -> list[str]:
    """Markdown header for the evidence report (R4: small helper)."""
    relative_output = f"docs/evidence/{output_dir.name}"
    return [
        f"# Bundle de evidencia -- {profile.title}",
        "",
        f"- **Modo:** `{mode}`",
        f"- **Objetivo:** `{profile.objective_id}`",
        f"- **Provider/modelo:** `{provider}/{model}`",
        f"- **Session ID:** `{session_id}`",
        f"- **Generado en:** `{relative_output}`",
        "",
    ]


def _format_checks_lines(checks: list[dict[str, str]]) -> list[str]:
    lines = ["## Comprobaciones demostrables", ""]
    for check in checks:
        lines.append(
            f"- **{check['id']}**: {check['status']} -- {check['detail']}"
        )
    lines.append("")
    return lines


def _format_commands_lines(commands: dict[str, dict[str, Any]]) -> list[str]:
    lines = ["## Comandos capturados", ""]
    for name, result in commands.items():
        lines.extend([
            f"### {name}",
            "",
            "```text",
            result.get("message", "").strip(),
            "```",
            "",
        ])
    return lines


def _build_direct_response_section(response_text: str) -> list[str]:
    """First content section of the report (R4: small builder)."""
    return [
        "## Resultado directo al usuario",
        "",
        response_text.strip(),
        "",
    ]


def _build_plan_section(plan_text: str) -> list[str]:
    """Optional plan section, empty when no plan was generated (R4)."""
    if not plan_text:
        return []
    return [
        "## Plan generado",
        "",
        "```text",
        plan_text.strip(),
        "```",
        "",
    ]


def _build_report(
    *,
    mode: str,
    profile: ObjectiveProfile,
    provider: str,
    model: str,
    session_id: str,
    checks: list[dict[str, str]],
    commands: dict[str, dict[str, Any]],
    response_text: str,
    plan_text: str,
    output_dir: Path,
) -> str:
    """Compose the human-readable report.md (R4: small, side-effect free)."""
    lines = _build_report_header(
        profile=profile,
        mode=mode,
        provider=provider,
        model=model,
        session_id=session_id,
        output_dir=output_dir,
    )
    lines.extend(_build_direct_response_section(response_text))
    lines.extend(_build_plan_section(plan_text))
    lines.extend(_format_checks_lines(checks))
    lines.extend(_format_commands_lines(commands))
    return "\n".join(lines).rstrip() + "\n"


def _validation_commands(
    mode: str, objective: str, output_dir: Path, provider: str, model: str
) -> list[str]:
    relative_output = f"docs/evidence/{output_dir.name}"
    commands = [
        "python test_e2e.py",
        "python bago_core\\cli.py evidence --test",
    ]
    if mode == "simulated":
        commands.append(
            f'python bago_core\\cli.py evidence --mode simulated --objective {objective} --output "{relative_output}" --overwrite'
        )
    else:
        commands.append(
            f'python bago_core\\cli.py evidence --mode real --provider {provider} --model "{model}" --output "{relative_output}" --overwrite'
        )
    return commands


# --- Baseline contract checks (R4) ----------------------------------------


def _session_runtime_check(copied_artifacts: list[str]) -> dict[str, str]:
    return {
        "id": "session-runtime",
        "status": "pass" if copied_artifacts else "fail",
        "detail": (
            "La sesion genero artefactos persistentes en "
            "context.jsonl/timeline/tokens/meta."
        ),
    }


def _direct_assistance_check(direct_response: str) -> dict[str, str]:
    return {
        "id": "direct-assistance",
        "status": "pass" if direct_response.strip() else "fail",
        "detail": (
            "Existe una respuesta util al objetivo planteado por el "
            "usuario."
        ),
    }


def _knowledge_persistence_check(
    exported_memory: list[dict[str, Any]],
) -> dict[str, str]:
    return {
        "id": "knowledge-persistence",
        "status": "pass" if exported_memory else "fail",
        "detail": (
            "La evidencia incluye conocimiento recuperable derivado "
            "de la sesion."
        ),
    }


def _session_save_check(output_dir: Path) -> dict[str, str]:
    return {
        "id": "session-save",
        "status": "pass"
            if (output_dir / "session" / "session.json").exists()
            else "fail",
        "detail": (
            "La sesion se guardo en disco con metadatos de "
            "continuidad."
        ),
    }


# --- Mode-specific checks (R4) --------------------------------------------


def _simulated_mode_check(profile: ObjectiveProfile) -> dict[str, str]:
    return {
        "id": "plan-generation",
        "status": "pass" if profile.plan_task else "fail",
        "detail": (
            "El runtime definio un plan reutilizable desde el parser "
            "REPL real."
        ),
    }


def _live_mode_check(health_ok: bool) -> dict[str, str]:
    return {
        "id": "live-provider-health",
        "status": "pass" if health_ok else "fail",
        "detail": (
            "El provider real respondio con salud positiva antes de "
            "cerrar el bundle."
        ),
    }


# --- Manifest payload (R4) ------------------------------------------------


def _build_manifest_dict(
    *,
    mode: str,
    profile: ObjectiveProfile,
    provider: str,
    model: str,
    session_id: str,
    output_dir: Path,
    checks: list[dict[str, str]],
    copied_artifacts: list[str],
    plan_text: str,
    validation_commands: list[str],
) -> dict[str, Any]:
    """Inner builder for the manifest.json payload (R4)."""
    return {
        "bundle_id": (
            f"bago.v4.evidence.{mode}.{profile.objective_id}"
        ),
        "contract_version": read_release_version(Path(__file__).resolve().parents[1]),
        "related_to": [
            "docs\\contracts\\bago_v4_runtime_contract.json",
            "docs\\contracts\\bago_v4_repl_contract.md",
            "docs\\contracts\\bago_v4_evidence_contract.md",
            "docs\\contracts\\bago_v4_knowledge_contract.md",
            "docs\\contracts\\bago_v4_governance_contract.md",
            "docs\\contracts\\bago_v4_engineering_contract.md",
        ],
        "summary": profile.summary,
        "details": {
            "mode": mode,
            "provider": provider,
            "model": model,
            "session_id": session_id,
            "state_root": ".gabo\\state",
        },
        "status": "pass"
            if all(item["status"] == "pass" for item in checks)
            else "fail",
        "recorded_at": now_iso(),
        "validation_commands": validation_commands,
        "checks": checks,
        "artifacts": copied_artifacts + [
            "assistant_response.txt",
            "commands\\results.json",
            "knowledge\\recent_memories.json",
            "objective.json",
        ] + (["plan.txt"] if plan_text else []),
    }
