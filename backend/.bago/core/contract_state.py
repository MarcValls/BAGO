#!/usr/bin/env python3
"""contract_state.py - canonical DTO builders for BAGO surfaces.

Keeps the backend as the single authority for workspace, welcome, menu,
and model-catalog state while preserving compatibility aliases for older
consumers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from workspace_binding import resolve_workspace_binding


CONTRACT_VERSION = "bago.contract.ui.v1"


def _norm_path(value: str | Path | None) -> str:
    if value is None:
        return ""
    try:
        return str(Path(value))
    except Exception:
        return str(value)


def _center_id(title: str) -> str:
    normalized = title.lower().strip()
    aliases = {
        "sesion y estado": "session",
        "proyectos y directorio": "workspace",
        "providers y modelos": "model",
        "herramientas y automatizacion": "tools",
        "agentes y memoria": "evidence",
        "configuracion y control": "system",
        "contexto": "context",
        "vista": "view",
        "avanzado": "advanced",
        "tarea": "task",
    }
    return aliases.get(normalized, normalized.replace(" ", "_"))


def _action_line(command: str, item: dict[str, Any]) -> dict[str, Any]:
    command_line = command.strip()
    return {
        "command_id": command_line.lstrip("/").replace(" ", "."),
        "nombre": command_line,
        "description": item.get("description", ""),
        "args": item.get("args_prompt", ""),
        "wizard": item.get("wizard", ""),
        "confirm": bool(item.get("confirm", False)),
        "allowed": True,
        "state": "permitted",
    }


def build_workspace_state(
    project_root: str | Path,
    *,
    session_id: str = "",
    workspace_id: str = "",
    context_revision: str = "",
    request_id: str = "",
    contract_version: str = CONTRACT_VERSION,
    session_workspace_id: str = "",
) -> dict[str, Any]:
    binding = resolve_workspace_binding(project_root)
    project = _norm_path(project_root)
    workspace_state_root = _norm_path(binding.workspace_state_root)
    scope_root = _norm_path(binding.workspace_scope_root)
    legacy_root = str(Path(project) / ".bago")
    legacy_exists = Path(legacy_root).exists()

    manifest_status = "valid" if binding.manifest_exists and binding.binding_confirmed else (
        "missing" if not binding.manifest_exists else "invalid"
    )
    workspace_state = "blocked"
    if not binding.project_exists:
        workspace_state = "blocked"
    elif binding.workspace_exists and binding.manifest_exists and binding.binding_confirmed:
        if session_workspace_id and session_workspace_id != binding.workspace_id:
            workspace_state = "detected_unlinked"
        elif workspace_id and workspace_id != binding.workspace_id:
            workspace_state = "detected_unlinked"
        else:
            workspace_state = "linked_confirmed"
    elif binding.workspace_exists and not binding.manifest_exists:
        workspace_state = "invalid"
        manifest_status = "missing"
    elif binding.workspace_exists and binding.manifest_exists and not binding.binding_confirmed:
        workspace_state = "invalid"
    elif legacy_exists and not binding.workspace_exists:
        workspace_state = "legacy_only"
    elif not binding.workspace_exists:
        workspace_state = "absent"

    allowed_actions_by_state = {
        "linked_confirmed": [
            "session.status",
            "session.save",
            "workspace.inspect",
            "workspace.verify",
            "context.inspect",
            "context.measure",
            "context.benchmark",
            "context.certify",
            "chat.send",
        ],
        "detected_unlinked": [
            "workspace.link",
            "workspace.inspect",
            "workspace.verify",
            "session.resume",
            "session.select",
        ],
        "invalid": [
            "workspace.inspect",
            "workspace.verify",
            "workspace.repair",
            "workspace.migrate",
        ],
        "absent": [
            "workspace.init",
            "workspace.detect",
            "workspace.inspect",
            "workspace.read_only",
        ],
        "legacy_only": [
            "workspace.inspect_legacy",
            "workspace.migrate_legacy",
            "workspace.create_gabo",
            "workspace.read_only",
        ],
        "blocked": [
            "system.doctor",
            "workspace.inspect",
        ],
    }
    blocked_by_state = {
        "linked_confirmed": [],
        "detected_unlinked": ["workspace.init", "workspace.create_gabo"],
        "invalid": ["chat.send", "workspace.init", "workspace.create_gabo"],
        "absent": ["chat.send", "workspace.link"],
        "legacy_only": ["chat.send", "workspace.init"],
        "blocked": ["chat.send", "workspace.link", "workspace.init"],
    }
    warnings = []
    if binding.workspace_exists and not binding.manifest_exists:
        warnings.append("manifest_missing")
    if binding.workspace_exists and binding.manifest_exists and not binding.binding_confirmed:
        warnings.append(binding.binding_reason)
    if legacy_exists:
        warnings.append("legacy_bago_detected")

    return {
        "contract_version": contract_version,
        "source_of_truth_version": "gabo-workspace-v2",
        "workspace_state": workspace_state,
        "state": workspace_state,
        "framework_root": binding.framework_root,
        "project_root": project,
        "workspace_state_root": workspace_state_root,
        "workspace_scope_root": scope_root,
        "workspace_id": workspace_id or binding.workspace_id,
        "session_id": session_id,
        "manifest_status": manifest_status,
        "manifest_exists": binding.manifest_exists,
        "manifest_path": binding.manifest_path,
        "binding_confirmed": workspace_state == "linked_confirmed",
        "binding_reason": binding.binding_reason,
        "allowed_actions": allowed_actions_by_state[workspace_state],
        "acciones_permitidas": allowed_actions_by_state[workspace_state],
        "blocked_operations": blocked_by_state[workspace_state],
        "operaciones_bloqueadas": blocked_by_state[workspace_state],
        "context_revision": context_revision,
        "warnings": warnings,
        "advertencias": warnings,
        "legacy_root": legacy_root if legacy_exists else "",
        "legacy_exists": legacy_exists,
        "request_id": request_id or str(uuid4()),
    }


def build_welcome_state(
    workspace_state: dict[str, Any],
    *,
    summary: str = "",
    recommended_actions: list[str] | None = None,
    allowed_actions: list[str] | None = None,
    blocked_operations: list[str] | None = None,
    request_id: str = "",
) -> dict[str, Any]:
    allowed = list(allowed_actions or workspace_state.get("allowed_actions", []) or [])
    blocked = list(blocked_operations or workspace_state.get("blocked_operations", []) or [])
    recommended = list(recommended_actions or allowed[:4])
    return {
        "contract_version": workspace_state.get("contract_version", CONTRACT_VERSION),
        "workspace_state": workspace_state,
        "identity": {
            "framework_root": workspace_state.get("framework_root", ""),
            "project_root": workspace_state.get("project_root", ""),
            "workspace_state_root": workspace_state.get("workspace_state_root", ""),
            "workspace_id": workspace_state.get("workspace_id", ""),
            "session_id": workspace_state.get("session_id", ""),
        },
        "summary": summary or workspace_state.get("binding_reason", ""),
        "recommended_actions": recommended,
        "allowed_actions": allowed,
        "blocked_operations": blocked,
        "warnings": list(workspace_state.get("warnings", []) or []),
        "request_id": request_id or workspace_state.get("request_id", ""),
    }


def build_menu_state(
    workspace_state: dict[str, Any],
    sections: list[dict[str, Any]],
    *,
    active_center: str = "",
    selected_item: str = "",
    request_id: str = "",
) -> dict[str, Any]:
    centers: list[dict[str, Any]] = []
    direct_commands: list[dict[str, Any]] = []
    section_map = {
        "sesion y estado": "session",
        "proyectos y directorio": "workspace",
        "roadmap y verificacion": "roadmap",
        "providers y modelos": "model",
        "herramientas y automatizacion": "tools",
        "agentes y memoria": "evidence",
        "configuracion y control": "system",
    }
    for section in sections:
        title = str(section.get("title", "")).strip()
        center_id = section_map.get(title.lower(), _center_id(title))
        items = []
        for item in section.get("items", []):
            command = str(item.get("command", "")).strip()
            if not command:
                continue
            action = _action_line(command, item)
            items.append(action)
            direct_commands.append(action)
        centers.append({
            "center_id": center_id,
            "nombre": title,
            "descripción": section.get("description", ""),
            "estado": workspace_state.get("state", "blocked"),
            "resumen": section.get("description", ""),
            "selección_actual": selected_item if center_id == active_center else "",
            "cantidad_de_elementos": len(items),
            "acciones_visibles": [item["command_id"] for item in items],
            "acciones_bloqueadas": list(workspace_state.get("blocked_operations", []) or []),
            "advertencias": list(workspace_state.get("warnings", []) or []),
            "actividad_reciente": [],
            "profundidad_disponible": 2 if len(items) > 1 else 1,
            "items": items,
        })

    if not centers:
        for center_id, nombre in [
            ("task", "/task"),
            ("session", "/session"),
            ("workspace", "/workspace"),
            ("context", "/context"),
            ("model", "/model"),
            ("tools", "/tools"),
            ("evidence", "/evidence"),
            ("system", "/system"),
            ("view", "/view"),
            ("advanced", "/advanced"),
        ]:
            centers.append({
                "center_id": center_id,
                "nombre": nombre,
                "descripción": "",
                "estado": workspace_state.get("state", "blocked"),
                "resumen": "",
                "selección_actual": "",
                "cantidad_de_elementos": 0,
                "acciones_visibles": [],
                "acciones_bloqueadas": list(workspace_state.get("blocked_operations", []) or []),
                "advertencias": list(workspace_state.get("warnings", []) or []),
                "actividad_reciente": [],
                "profundidad_disponible": 1,
                "items": [],
            })

    active = active_center or (
        "workspace" if workspace_state.get("workspace_state") in {"absent", "invalid", "legacy_only"} else "session"
    )
    sections_visible = [center["center_id"] for center in centers]
    recommended = list(workspace_state.get("allowed_actions", [])[:4] or [])
    return {
        "contract_version": workspace_state.get("contract_version", CONTRACT_VERSION),
        "workspace_state": workspace_state,
        "centros_operativos": centers,
        "centers": centers,
        "centro_activo": active,
        "active_center": active,
        "secciones_visibles": sections_visible,
        "visible_sections": sections_visible,
        "elemento_seleccionado": selected_item,
        "selected_item": selected_item,
        "estado_de_seleccion": "effective" if selected_item else "visual",
        "selection_state": "effective" if selected_item else "visual",
        "resumen_de_estado": workspace_state.get("binding_reason", ""),
        "acciones_recomendadas": recommended,
        "acciones_permitidas": list(workspace_state.get("allowed_actions", []) or []),
        "acciones_secundarias": [],
        "acciones_bloqueadas": list(workspace_state.get("blocked_operations", []) or []),
        "razones_de_bloqueo": list(workspace_state.get("warnings", []) or []),
        "comandos_directos_disponibles": [item["nombre"] for item in direct_commands],
        "direct_commands": direct_commands,
        "operaciones_activas": [],
        "advertencias": list(workspace_state.get("warnings", []) or []),
        "navegacion": {
            "nivel_actual": 1,
            "ruta_visual": [active],
            "nivel_anterior": "",
            "puede_volver": False,
            "puede_buscar": True,
            "puede_filtrar": True,
            "paginacion": False,
            "filtros_activos": [],
        },
        "request_id": request_id or workspace_state.get("request_id", ""),
    }


def build_roadmap_state(*, request_id: str = "") -> dict[str, Any]:
    iterations = [
        {
            "id": "iteration-1",
            "title": "Base Operativa",
            "goal": "cerrar el núcleo verificable antes de ampliar superficie",
            "status": "verified",
            "phases": [
                "Phase 0 - Scope Freeze",
                "Phase 1 - Real Baseline",
                "Phase 2 - Security Gate",
                "Phase 3 - Launcher And Provider Session",
                "Phase 4 - Provider Contract",
            ],
            "verification": [
                "python -m pytest tests/test_plan_engine_contract.py tests/test_workspace_seed_contract.py tests/test_ollama_discovery.py tests/test_ollama_autostart.py tests/test_tool_approval_policy.py -q",
                "python bago_core\\cli.py validate",
            ],
        },
        {
            "id": "iteration-2",
            "title": "Producto Visible",
            "goal": "exponer capacidad útil sin mover la autoridad fuera del backend",
            "status": "verified",
            "phases": [
                "Phase 5 - React UI",
                "Phase 6 - Evidence And Contracts",
            ],
            "verification": [
                "npm run manager:build-ui",
                "UI manager with backend snapshot and command bridge",
            ],
        },
        {
            "id": "iteration-3",
            "title": "Distribución Y Cierre",
            "goal": "dejar el producto documentado, empaquetable y con gate final",
            "status": "verified",
            "phases": [
                "Phase 7 - OSS Documentation",
                "Phase 8 - Packaging",
                "Phase 9 - Final Gate",
            ],
            "verification": [
                "docs/ROADMAP.md grouped by iterations",
                "/roadmap command exposed in Terminal and UI",
            ],
        },
    ]
    completed = sum(1 for item in iterations if item["status"] == "verified")
    phase_count = sum(len(item["phases"]) for item in iterations)
    return {
        "contract_version": CONTRACT_VERSION,
        "roadmap_version": "bago.roadmap/v1",
        "status": "verified" if completed == len(iterations) else "partial",
        "summary": f"{completed}/{len(iterations)} iteraciones verificadas, {phase_count} fases agrupadas",
        "current_iteration": iterations[-1]["id"] if completed == len(iterations) else iterations[completed]["id"],
        "iterations": iterations,
        "request_id": request_id,
    }


def build_model_catalog_state(
    provider: str,
    items: list[dict[str, Any]],
    *,
    selected_model: str = "",
    effective_model: str = "",
    request_id: str = "",
) -> dict[str, Any]:
    catalog_items = []
    capabilities: list[str] = []
    for item in items:
        model_id = str(item.get("id") or item.get("model_id") or "").strip()
        if not model_id:
            continue
        caps = item.get("capabilities")
        if isinstance(caps, list):
            capabilities.extend([str(x) for x in caps if str(x).strip()])
        catalog_items.append({
            "id": model_id,
            "model_id": model_id,
            "wire_name": item.get("wire_name", model_id),
            "provider": item.get("provider", provider),
            "context_tokens": item.get("context_tokens"),
            "max_output_tokens": item.get("max_output_tokens"),
            "best_for": item.get("best_for", ""),
            "cost": item.get("cost", ""),
            "available": bool(item.get("available", True)),
        })
    selected = selected_model or effective_model or (catalog_items[0]["id"] if catalog_items else "")
    effective = effective_model or selected
    return {
        "contract_version": CONTRACT_VERSION,
        "provider": provider,
        "items": catalog_items,
        "models": [item["id"] for item in catalog_items],
        "model_items": catalog_items,
        "selected_model": selected,
        "effective_model": effective,
        "capabilities": sorted(set(capabilities)),
        "request_id": request_id or str(uuid4()),
    }
