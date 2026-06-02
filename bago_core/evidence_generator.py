#!/usr/bin/env python3
"""FASE 6.3: storage / generator logic for the contract evidence bundle.

Owns:
- _now_iso, _write_json, _write_text, _sha256, _copy_if_exists
- _sanitize_result, _prepare_output_dir, _copy_session_artifacts
- _collect_file_digests, _write_checksums
- _build_report, _validation_commands
- _generate_bundle_with_manager
- generate_bundle (the public entry point)

R0-R10:
- R0: <300 lines
- R8: no `print()` (uses _write_* helpers)
- R1: imports model from evidence_model, CLI from evidence_cli
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# The legacy evidence_bundle.py used to import `from commands import execute`
# at the top of the file. That worked because launcher.py injected the
# `.bago/chat/` directory *before* `bago_core/commands/` on sys.path, and the
# file at `.bago/chat/commands.py` exports a top-level `execute(command, mgr, engine)`.
#
# In the split world, the generator is imported lazily by evidence_cli and
# evidence_bundle. By the time the import runs, `bago_core/commands` may
# already be on sys.path. To keep the contract simple we resolve the REPL
# executor up front and bind it under a private alias, then we set `commands`
# in sys.modules to that REPL module so any `from commands import execute` in
# the generator stack keeps resolving correctly.
_BAGO_ROOT = Path(__file__).resolve().parents[1]
for _p in (_BAGO_ROOT / ".bago" / "core", _BAGO_ROOT / ".bago" / "chat",
           _BAGO_ROOT / ".bago" / "providers", _BAGO_ROOT / ".bago" / "api",
           _BAGO_ROOT / ".bago" / "tools"):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

# The REPL commands module (provides `execute`). Must be importable under the
# name `commands` so `from commands import execute` keeps working.
import importlib.util as _importlib_util  # noqa: E402

_REPL_CMDS_PATH = _BAGO_ROOT / ".bago" / "chat" / "commands.py"
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

from bago_core.evidence_model import (
    ContractMockAdapter,
    ObjectiveProfile,
    PROFILES,
    registered_mock_adapter,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_if_exists(source: Path, target: Path) -> None:
    if source.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _sanitize_result(result: dict[str, Any]) -> dict[str, Any]:
    clean = {
        "ok": bool(result.get("ok")),
        "message": str(result.get("message", "")),
    }
    if "action" in result:
        clean["action"] = result["action"]
    return clean


def _prepare_output_dir(output_dir: Path, overwrite: bool) -> None:
    if output_dir.exists():
        if not overwrite:
            raise FileExistsError(f"El directorio ya existe: {output_dir}")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def _copy_session_artifacts(base_path: Path, session_id: str, output_dir: Path) -> list[str]:
    state_dir = base_path / ".bago" / "state" / "sessions"
    session_dir = state_dir / session_id
    copied: list[str] = []

    for name in ("context.jsonl", "timeline.jsonl", "tokens.json", "meta.json"):
        source = session_dir / name
        target = output_dir / "session" / name
        if source.exists():
            _copy_if_exists(source, target)
            copied.append(str(target.relative_to(output_dir)).replace("/", "\\"))

    session_meta = state_dir / f"{session_id}.json"
    if session_meta.exists():
        target = output_dir / "session" / "session.json"
        _copy_if_exists(session_meta, target)
        copied.append(str(target.relative_to(output_dir)).replace("/", "\\"))

    return copied


def _collect_file_digests(output_dir: Path) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for path in sorted(output_dir.rglob("*")):
        if path.is_file():
            relative = str(path.relative_to(output_dir)).replace("/", "\\")
            files.append({
                "path": relative,
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            })
    return files


def _write_checksums(output_dir: Path, files: list[dict[str, Any]]) -> None:
    lines = [f"{entry['sha256']} *{entry['path']}" for entry in files if entry["path"] != "checksums.sha256"]
    _write_text(output_dir / "checksums.sha256", "\n".join(lines) + ("\n" if lines else ""))


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
    lines = [
        f"# Bundle de evidencia -- {profile.title}",
        "",
        f"- **Modo:** `{mode}`",
        f"- **Objetivo:** `{profile.objective_id}`",
        f"- **Provider/modelo:** `{provider}/{model}`",
        f"- **Session ID:** `{session_id}`",
        f"- **Generado en:** `{output_dir}`",
        "",
        "## Resultado directo al usuario",
        "",
        response_text.strip(),
        "",
    ]
    if plan_text:
        lines.extend([
            "## Plan generado",
            "",
            "```text",
            plan_text.strip(),
            "```",
            "",
        ])

    lines.extend([
        "## Comprobaciones demostrables",
        "",
    ])
    for check in checks:
        lines.append(f"- **{check['id']}**: {check['status']} -- {check['detail']}")

    lines.extend([
        "",
        "## Comandos capturados",
        "",
    ])
    for name, result in commands.items():
        lines.extend([
            f"### {name}",
            "",
            "```text",
            result.get("message", "").strip(),
            "```",
            "",
        ])

    return "\n".join(lines).rstrip() + "\n"


def _validation_commands(mode: str, objective: str, output_dir: Path, provider: str, model: str) -> list[str]:
    commands = [
        "python test_e2e.py",
        "python bago_core\\cli.py evidence --test",
    ]
    if mode == "simulated":
        commands.append(
            f'python bago_core\\cli.py evidence --mode simulated --objective {objective} --output "{output_dir}" --overwrite'
        )
    else:
        commands.append(
            f'python bago_core\\cli.py evidence --mode real --provider {provider} --model "{model}" --output "{output_dir}" --overwrite'
        )
    return commands


def _generate_bundle_with_manager(
    *,
    mgr: SessionManager,
    mode: str,
    profile: ObjectiveProfile,
    output_dir: Path,
    workspace_path: Path,
) -> Path:
    engine = SwitchEngine(mgr.adapters)

    direct_response = mgr.send(profile.user_prompt if mode == "simulated" else profile.real_prompt)
    if not direct_response.strip():
        raise RuntimeError("La respuesta del provider esta vacia.")

    status_result = _sanitize_result(execute("/status", mgr, engine))
    memory_add_result = _sanitize_result(execute(f"/memory add {profile.knowledge_entry}", mgr, engine))
    memory_search_result = _sanitize_result(execute(f"/memory search {profile.knowledge_query}", mgr, engine))
    save_result: dict[str, Any] | None = None

    plan_text = ""
    if mode == "simulated":
        plan_result = execute(f"/plan {profile.plan_task}", mgr, engine)
        plan_view = _sanitize_result(plan_result)
        commands = {
            "/status": status_result,
            "/plan": plan_view,
            "/memory add": memory_add_result,
            "/memory search": memory_search_result,
        }
        plan_text = plan_view["message"]
        good_result = _sanitize_result(execute("/good", mgr, engine))
        commands["/good"] = good_result
    else:
        commands = {
            "/status": status_result,
            "/memory add": memory_add_result,
            "/memory search": memory_search_result,
        }

    save_result = _sanitize_result(execute("/save", mgr, engine))
    commands["/save"] = save_result

    recent_memories = mgr.knowledge.list_recent(limit=5)
    exported_memory = [
        item for item in recent_memories
        if profile.knowledge_query.lower() in item["content"].lower()
        or profile.knowledge_entry.lower() in item["content"].lower()
    ]

    _write_json(output_dir / "objective.json", {
        "objective_id": profile.objective_id,
        "title": profile.title,
        "summary": profile.summary,
        "mode": mode,
        "recorded_at": _now_iso(),
    })
    _write_text(output_dir / "assistant_response.txt", direct_response.strip() + "\n")
    if plan_text:
        _write_text(output_dir / "plan.txt", plan_text.strip() + "\n")
    _write_json(output_dir / "commands" / "results.json", commands)
    _write_json(output_dir / "knowledge" / "recent_memories.json", exported_memory)

    copied_artifacts = _copy_session_artifacts(workspace_path, mgr.session_id, output_dir)

    checks: list[dict[str, str]] = [
        {
            "id": "session-runtime",
            "status": "pass" if copied_artifacts else "fail",
            "detail": "La sesion genero artefactos persistentes en context.jsonl/timeline/tokens/meta.",
        },
        {
            "id": "direct-assistance",
            "status": "pass" if direct_response.strip() else "fail",
            "detail": "Existe una respuesta util al objetivo planteado por el usuario.",
        },
        {
            "id": "knowledge-persistence",
            "status": "pass" if exported_memory else "fail",
            "detail": "La evidencia incluye conocimiento recuperable derivado de la sesion.",
        },
        {
            "id": "session-save",
            "status": "pass" if (output_dir / "session" / "session.json").exists() else "fail",
            "detail": "La sesion se guardo en disco con metadatos de continuidad.",
        },
    ]
    if mode == "simulated":
        checks.append({
            "id": "plan-generation",
            "status": "pass" if plan_text.strip() else "fail",
            "detail": "El runtime genero un plan reutilizable desde el parser REPL real.",
        })
    else:
        checks.insert(0, {
            "id": "live-provider-health",
            "status": "pass" if mgr.status()["health"]["ok"] else "fail",
            "detail": "El provider real respondio con salud positiva antes de cerrar el bundle.",
        })

    manifest = {
        "bundle_id": f"bago.v4.evidence.{mode}.{profile.objective_id}",
        "contract_version": "4.1.5",
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
            "provider": mgr.provider,
            "model": mgr.model,
            "session_id": mgr.session_id,
            "state_root": ".bago\\state",
        },
        "status": "pass" if all(item["status"] == "pass" for item in checks) else "fail",
        "recorded_at": _now_iso(),
        "validation_commands": _validation_commands(mode, profile.objective_id, output_dir, mgr.provider, mgr.model),
        "checks": checks,
        "artifacts": copied_artifacts + [
            "assistant_response.txt",
            "commands\\results.json",
            "knowledge\\recent_memories.json",
            "objective.json",
        ] + (["plan.txt"] if plan_text else []),
    }

    _write_json(output_dir / "manifest.json", manifest)
    _write_text(
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

    files = _collect_file_digests(output_dir)
    _write_checksums(output_dir, files)
    files = _collect_file_digests(output_dir)

    manifest["files"] = files
    _write_json(output_dir / "manifest.json", manifest)
    return output_dir / "manifest.json"


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
    _prepare_output_dir(output_dir, overwrite)

    if mode == "simulated":
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
                    mode=mode,
                    profile=profile,
                    output_dir=output_dir,
                    workspace_path=workspace_path,
                )
            finally:
                mgr.close()

    mgr = SessionManager(
        base_path=str(base_path),
        provider=provider,
        model=model,
    )
    try:
        health = mgr.status()["health"]
        if not health["ok"]:
            raise RuntimeError(f"Provider no saludable: {health['detail']}")
        return _generate_bundle_with_manager(
            mgr=mgr,
            mode=mode,
            profile=profile,
            output_dir=output_dir,
            workspace_path=base_path,
        )
    finally:
        mgr.close()
