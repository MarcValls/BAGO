#!/usr/bin/env python3
"""FASE 6.3 + FASE 9.2: orchestrator for the contract evidence bundle.

This module owns the *orchestration* of an evidence bundle: it runs the
REPL commands, builds the manifest payload, and writes the final files.
All filesystem IO is delegated to :mod:`bago_core.evidence_io` and all
payload formatting is delegated to :mod:`bago_core.evidence_report`.

Owns:
- `_sanitize_result`
- `_run_status_and_memory`, `_run_simulated_repl`
- `_run_repl_commands`, `_collect_evidence`
- `_build_baseline_checks`, `_build_manifest_checks`
- `_write_bundle_artifacts`, `_run_session_phase`
- `_build_checks_and_manifest`, `_run_simulated_bundle`, `_run_live_bundle`
- `_write_report`, `_refresh_checksums_and_files`, `_finalize_manifest`
- `_generate_bundle_with_manager` (thin orchestrator)
- `generate_bundle` (public entry point)

R0-R10:
- R0: <400 lines (target 300).
- R1: imports IO from `evidence_io`, formatting from `evidence_report`,
  model from `evidence_model`, CLI from `evidence_cli`.
- R8: no `print()`.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any

from bago_core.evidence_io import (
    collect_file_digests,
    copy_session_artifacts,
    now_iso,
    prepare_output_dir,
    write_checksums,
    write_json,
    write_text,
)
from bago_core.evidence_model import (
    ContractMockAdapter,
    ObjectiveProfile,
    PROFILES,
    registered_mock_adapter,
)
from bago_core.evidence_report import (
    _build_manifest_dict,
    _build_report,
    _direct_assistance_check,
    _knowledge_persistence_check,
    _live_mode_check,
    _session_runtime_check,
    _session_save_check,
    _simulated_mode_check,
    _validation_commands,
)
from bago_core.resolver import add_piece_paths, resolve_piece_path

# The legacy evidence bundle imported `from commands import execute` at the
# top of the file. The resolver keeps that import shape working without
# depending on a particular on-disk package layout.
#
# In the split world, the generator is imported lazily by evidence_cli and
# evidence_bundle. By the time the import runs, `bago_core/commands` may
# already be on sys.path. To keep the contract simple we resolve the REPL
# executor up front and bind it under a private alias, then we set `commands`
# in sys.modules so any `from commands import execute` in the generator stack
# keeps resolving correctly.
_BAGO_ROOT = Path(__file__).resolve().parents[1]
add_piece_paths("core.package", "chat.package", "providers.package", "api.package", "tools.package")

# The REPL commands module (provides `execute`). Must be importable under the
# name `commands` so `from commands import execute` keeps working.
import importlib.util as _importlib_util  # noqa: E402

_REPL_CMDS_PATH = resolve_piece_path("chat.commands")
_spec = _importlib_util.spec_from_file_location("bago_repl_commands", _REPL_CMDS_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"cannot load REPL commands from {_REPL_CMDS_PATH}")
_repl_cmds = _importlib_util.module_from_spec(_spec)
sys.modules.setdefault("commands", _repl_cmds)
_spec.loader.exec_module(_repl_cmds)

# Re-bind to the canonical aliases used by the rest of this module.
execute = _repl_cmds.execute  # type: ignore[attr-defined]
from session_manager import SessionManager  # noqa: E402
from switch_engine import SwitchEngine  # noqa: E402


def _sanitize_result(result: dict[str, Any]) -> dict[str, Any]:
    clean = {
        "ok": bool(result.get("ok")),
        "message": str(result.get("message", "")),
    }
    if "action" in result:
        clean["action"] = result["action"]
    return clean


# --- REPL evidence collection (R4) -----------------------------------------


def _run_status_and_memory(
    *,
    mgr: SessionManager,
    engine: SwitchEngine,
    profile: ObjectiveProfile,
) -> dict[str, dict[str, Any]]:
    """Run /status, /memory add, /memory search (R4)."""
    return {
        "/status": _sanitize_result(execute("/status", mgr, engine)),
        "/memory add": _sanitize_result(
            execute(f"/memory add {profile.knowledge_entry}", mgr, engine)
        ),
        "/memory search": _sanitize_result(
            execute(f"/memory search {profile.knowledge_query}", mgr, engine)
        ),
    }


def _run_simulated_repl(
    *,
    mgr: SessionManager,
    engine: SwitchEngine,
    profile: ObjectiveProfile,
) -> tuple[dict[str, dict[str, Any]], str]:
    """Run /plan + /good in simulated mode (R4)."""
    plan_result = execute(f"/plan {profile.plan_task}", mgr, engine)
    plan_view = _sanitize_result(plan_result)
    commands = {
        "/plan": plan_view,
        "/good": _sanitize_result(execute("/good", mgr, engine)),
    }
    return commands, plan_view["message"]


def _run_repl_commands(
    *,
    mgr: SessionManager,
    engine: SwitchEngine,
    profile: ObjectiveProfile,
    mode: str,
) -> tuple[dict[str, dict[str, Any]], str]:
    """Run the standard REPL evidence commands and collect their results."""
    commands = _run_status_and_memory(
        mgr=mgr, engine=engine, profile=profile,
    )
    plan_text = ""
    if mode == "simulated":
        sim_cmds, plan_text = _run_simulated_repl(
            mgr=mgr, engine=engine, profile=profile,
        )
        commands.update(sim_cmds)
    commands["/save"] = _sanitize_result(execute("/save", mgr, engine))
    return commands, plan_text


def _collect_evidence(
    *,
    mgr: SessionManager,
    profile: ObjectiveProfile,
) -> list[dict[str, Any]]:
    """Pick recent memories matching the objective's knowledge queries."""
    recent_memories = mgr.knowledge.list_recent(limit=5)
    return [
        item for item in recent_memories
        if profile.knowledge_query.lower() in item["content"].lower()
        or profile.knowledge_entry.lower() in item["content"].lower()
    ]


# --- Check + manifest composition (R4) ------------------------------------


def _build_baseline_checks(
    *,
    direct_response: str,
    copied_artifacts: list[str],
    exported_memory: list[dict[str, Any]],
    output_dir: Path,
) -> list[dict[str, str]]:
    """The four always-present contract checks (R4)."""
    return [
        _session_runtime_check(copied_artifacts),
        _direct_assistance_check(direct_response),
        _knowledge_persistence_check(exported_memory),
        _session_save_check(output_dir),
    ]


def _build_manifest_checks(
    *,
    mode: str,
    profile: ObjectiveProfile,
    direct_response: str,
    copied_artifacts: list[str],
    exported_memory: list[dict[str, Any]],
    output_dir: Path,
    mgr: SessionManager,
) -> list[dict[str, str]]:
    """Build the contract checks for the evidence manifest (R4)."""
    checks = _build_baseline_checks(
        direct_response=direct_response,
        copied_artifacts=copied_artifacts,
        exported_memory=exported_memory,
        output_dir=output_dir,
    )
    if mode == "simulated":
        checks.append(_simulated_mode_check(profile))
    else:
        health_ok = bool(mgr.status()["health"]["ok"])
        checks.insert(0, _live_mode_check(health_ok))
    return checks


def _build_manifest(
    *,
    mode: str,
    profile: ObjectiveProfile,
    mgr: SessionManager,
    output_dir: Path,
    checks: list[dict[str, str]],
    copied_artifacts: list[str],
    plan_text: str,
) -> dict[str, Any]:
    """Compose the manifest.json payload (R4, R8)."""
    return _build_manifest_dict(
        mode=mode,
        profile=profile,
        provider=mgr.provider,
        model=mgr.model,
        session_id=mgr.session_id,
        output_dir=output_dir,
        checks=checks,
        copied_artifacts=copied_artifacts,
        plan_text=plan_text,
        validation_commands=_validation_commands(
            mode, profile.objective_id, output_dir, mgr.provider, mgr.model
        ),
    )


# --- IO delegation helpers (R4) -------------------------------------------


def _write_bundle_artifacts(
    *,
    output_dir: Path,
    profile: ObjectiveProfile,
    mode: str,
    direct_response: str,
    plan_text: str,
    commands: dict[str, dict[str, Any]],
    exported_memory: list[dict[str, Any]],
) -> None:
    """Materialize the bundle's evidence files on disk (R4)."""
    write_json(output_dir / "objective.json", {
        "objective_id": profile.objective_id,
        "title": profile.title,
        "summary": profile.summary,
        "mode": mode,
        "recorded_at": now_iso(),
    })
    write_text(
        output_dir / "assistant_response.txt",
        direct_response.strip() + "\n",
    )
    if plan_text:
        write_text(output_dir / "plan.txt", plan_text.strip() + "\n")
    write_json(output_dir / "commands" / "results.json", commands)
    write_json(
        output_dir / "knowledge" / "recent_memories.json",
        exported_memory,
    )


def _write_report(
    *,
    output_dir: Path,
    mode: str,
    profile: ObjectiveProfile,
    mgr: SessionManager,
    checks: list[dict[str, str]],
    commands: dict[str, dict[str, Any]],
    direct_response: str,
    plan_text: str,
) -> None:
    """Materialize the human-readable report.md (R4, R8)."""
    write_text(
        output_dir / "report.md",
        _build_report(
            mode=mode,
            profile=profile,
            provider=mgr.provider,
            model=mgr.model,
            session_id=mgr.session_id,
            checks=checks,
            commands=commands,
            response_text=direct_response,
            plan_text=plan_text,
            output_dir=output_dir,
        ),
    )


def _finalize_manifest(
    *,
    output_dir: Path,
    manifest: dict[str, Any],
    mode: str,
    profile: ObjectiveProfile,
    mgr: SessionManager,
    checks: list[dict[str, str]],
    commands: dict[str, dict[str, Any]],
    direct_response: str,
    plan_text: str,
) -> dict[str, Any]:
    """Write the manifest, report, and checksums without circular hashes."""
    _write_report(
        output_dir=output_dir,
        mode=mode,
        profile=profile,
        mgr=mgr,
        checks=checks,
        commands=commands,
        direct_response=direct_response,
        plan_text=plan_text,
    )
    manifest["files"] = collect_file_digests(
        output_dir,
        exclude={"manifest.json", "checksums.sha256"},
    )
    write_json(output_dir / "manifest.json", manifest)
    checksum_files = collect_file_digests(
        output_dir,
        exclude={"checksums.sha256"},
    )
    write_checksums(output_dir, checksum_files)
    return manifest


# --- Phase helpers (R4) ---------------------------------------------------


def _run_session_phase(
    *,
    mgr: SessionManager,
    profile: ObjectiveProfile,
    mode: str,
    workspace_path: Path,
    output_dir: Path,
) -> tuple[
    str,
    dict[str, dict[str, Any]],
    str,
    list[dict[str, Any]],
    list[str],
]:
    """Run the evidence collection phase of a bundle (R4)."""
    engine = SwitchEngine(mgr.adapters)
    direct_response = mgr.send(
        profile.user_prompt if mode == "simulated" else profile.real_prompt
    )
    if not direct_response.strip():
        raise RuntimeError("La respuesta del provider esta vacia.")

    commands, plan_text = _run_repl_commands(
        mgr=mgr, engine=engine, profile=profile, mode=mode,
    )
    exported_memory = _collect_evidence(mgr=mgr, profile=profile)
    copied_artifacts = copy_session_artifacts(
        workspace_path, mgr.session_id, output_dir,
    )
    return direct_response, commands, plan_text, exported_memory, copied_artifacts


def _build_checks_and_manifest(
    *,
    mode: str,
    profile: ObjectiveProfile,
    mgr: SessionManager,
    output_dir: Path,
    direct_response: str,
    copied_artifacts: list[str],
    exported_memory: list[dict[str, Any]],
    plan_text: str,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Compose the contract checks and the manifest payload (R4)."""
    checks = _build_manifest_checks(
        mode=mode,
        profile=profile,
        direct_response=direct_response,
        copied_artifacts=copied_artifacts,
        exported_memory=exported_memory,
        output_dir=output_dir,
        mgr=mgr,
    )
    manifest = _build_manifest(
        mode=mode,
        profile=profile,
        mgr=mgr,
        output_dir=output_dir,
        checks=checks,
        copied_artifacts=copied_artifacts,
        plan_text=plan_text,
    )
    return checks, manifest


# --- Public entry points --------------------------------------------------


def _generate_bundle_with_manager(
    *,
    mgr: SessionManager,
    mode: str,
    profile: ObjectiveProfile,
    output_dir: Path,
    workspace_path: Path,
) -> Path:
    """Build a complete evidence bundle on disk and return its manifest path.

    The function is intentionally thin: each phase is delegated to a
    R4 helper (`_run_session_phase`, `_write_bundle_artifacts`,
    `_build_checks_and_manifest`, `_finalize_manifest`).
    """
    direct_response, commands, plan_text, exported_memory, copied_artifacts = (
        _run_session_phase(
            mgr=mgr,
            profile=profile,
            mode=mode,
            workspace_path=workspace_path,
            output_dir=output_dir,
        )
    )
    _write_bundle_artifacts(
        output_dir=output_dir,
        profile=profile,
        mode=mode,
        direct_response=direct_response,
        plan_text=plan_text,
        commands=commands,
        exported_memory=exported_memory,
    )
    checks, manifest = _build_checks_and_manifest(
        mode=mode,
        profile=profile,
        mgr=mgr,
        output_dir=output_dir,
        direct_response=direct_response,
        copied_artifacts=copied_artifacts,
        exported_memory=exported_memory,
        plan_text=plan_text,
    )
    _finalize_manifest(
        output_dir=output_dir,
        manifest=manifest,
        mode=mode,
        profile=profile,
        mgr=mgr,
        checks=checks,
        commands=commands,
        direct_response=direct_response,
        plan_text=plan_text,
    )
    return output_dir / "manifest.json"


def _run_simulated_bundle(
    *,
    profile: ObjectiveProfile,
    output_dir: Path,
) -> Path:
    """Build a bundle in simulated mode (R4, R8)."""
    with tempfile.TemporaryDirectory() as temp_dir, registered_mock_adapter():
        workspace_path = Path(temp_dir)
        mgr = SessionManager(
            base_path=str(workspace_path),
            provider="mock-contract",
            model=ContractMockAdapter.MODEL_ID,
        )
        try:
            return _generate_bundle_with_manager(
                mgr=mgr,
                mode="simulated",
                profile=profile,
                output_dir=output_dir,
                workspace_path=workspace_path,
            )
        finally:
            mgr.close()


def _run_live_bundle(
    *,
    profile: ObjectiveProfile,
    output_dir: Path,
    provider: str,
    model: str,
    base_path: Path,
) -> Path:
    """Build a bundle against a real provider (R4, R8)."""
    mgr = SessionManager(
        base_path=str(base_path),
        provider=provider,
        model=model,
    )
    try:
        health = mgr.status()["health"]
        if not health["ok"]:
            raise RuntimeError(
                f"Provider no saludable: {health['detail']}"
            )
        return _generate_bundle_with_manager(
            mgr=mgr,
            mode="real",
            profile=profile,
            output_dir=output_dir,
            workspace_path=base_path,
        )
    finally:
        mgr.close()


def generate_bundle(
    *,
    mode: str,
    objective: str,
    output_dir: Path,
    provider: str,
    model: str,
    base_path: Path,
    overwrite: bool,
) -> Path:
    """Public entry point: build a complete evidence bundle on disk.

    Returns the path to the manifest.json that was written.
    """
    profile = PROFILES[objective]
    prepare_output_dir(output_dir, overwrite)

    if mode == "simulated":
        return _run_simulated_bundle(
            profile=profile, output_dir=output_dir,
        )
    return _run_live_bundle(
        profile=profile,
        output_dir=output_dir,
        provider=provider,
        model=model,
        base_path=base_path,
    )
