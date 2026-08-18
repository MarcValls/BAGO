"""Contrato backend de Anatomía de capacidades BAGO v0.2.

Proyecta inventario observado a un contrato de solo lectura. La definición y
la ejecución permanecen separadas: descubrir una pieza nunca significa que se
haya ejecutado.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "0.2"
CONTRACT_VERSION = "bago.capability/v0.2"
CAPABILITY_ID = "bago-runtime-inventory"
FEATURE_FLAG = "capability_anatomy_v02"


class CapabilityContractError(ValueError):
    pass


def _stable_id(prefix: str, value: str) -> str:
    normalized = re.sub(r"[^a-z0-9._-]+", "-", value.lower().replace("\\", "/")).strip("-.")
    digest = hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:8]
    return f"{prefix}-{normalized[:64]}-{digest}"


def _load_inventory_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "bago_inventory.py"
    spec = importlib.util.spec_from_file_location("bago_capability_inventory", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"No se pudo cargar inventario: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def resolve_inventory_root(mgr: Any) -> tuple[Path, str]:
    status = dict(getattr(mgr, "status", lambda: {})() or {})
    binding_confirmed = bool(status.get("binding_confirmed"))
    candidates: list[tuple[str, Any]] = []
    if binding_confirmed:
        candidates.extend([
            ("project_root", status.get("project_root")),
            ("workspace_scope_root", status.get("workspace_scope_root")),
        ])
    candidates.extend([
        ("framework_root", status.get("framework_root")),
        ("backend_root", Path(__file__).resolve().parents[2]),
    ])
    for source, raw in candidates:
        if not raw:
            continue
        path = Path(raw).expanduser().resolve()
        if path.exists() and path.is_dir():
            return path, source
    return Path(__file__).resolve().parents[2], "backend_root"


def _piece_from_inventory(item: dict[str, Any], category: str) -> dict[str, Any]:
    path = str(item.get("path") or "unknown")
    error = str(item.get("error") or "").strip()
    doc = str(item.get("doc") or "").strip().splitlines()
    name = Path(path).stem.replace("_", " ").strip() or path
    piece_type = "agent" if category == "agents" else "tool" if category == "tools" else "transformation"
    implementation_kind = "agent" if category == "agents" else "tool" if category == "tools" else "script"
    return {
        "id": _stable_id(category[:-1], path),
        "name": name,
        "type": piece_type,
        "purpose": doc[0][:240] if doc else f"Pieza {category[:-1]} descubierta en {path}",
        "definition_state": "prepared" if not error else "proposed",
        "availability": "available" if not error else "blocked",
        "implementation": {"kind": implementation_kind, "ref": path, "owner": "backend_inventory"},
        "requires": ["workspace_snapshot"],
        "produces": [f"{category[:-1]}_result"],
        "authorization": {"mode": "inspect", "permissions": [], "approval_required": False},
        "evidence_expected": ["execution_id y receipt backend si se ejecuta en el futuro"],
        "fallback_piece_id": None,
        "block_reason": error or None,
    }


def build_capability_snapshot(mgr: Any) -> dict[str, Any]:
    root, root_source = resolve_inventory_root(mgr)
    inventory_module = _load_inventory_module()
    inventory = inventory_module.gather_inventory(root)
    discovered: list[dict[str, Any]] = []
    for category in ("tools", "agents", "scripts"):
        for item in inventory.get(category, []):
            discovered.append(_piece_from_inventory(dict(item), category))

    input_piece = {
        "id": "workspace-input", "name": "Workspace activo", "type": "input",
        "purpose": "Raíz autorizada resuelta por el backend para inspección.",
        "definition_state": "prepared", "availability": "available",
        "implementation": {"kind": "backend_action", "ref": root_source, "owner": "backend"},
        "requires": [], "produces": ["workspace_snapshot"],
        "authorization": {"mode": "read", "permissions": [], "approval_required": False},
        "evidence_expected": ["binding backend confirmado"], "fallback_piece_id": None, "block_reason": None,
    }
    output_piece = {
        "id": "inventory-output", "name": "Anatomía validada", "type": "output",
        "purpose": "Instantánea declarativa de las piezas observadas.",
        "definition_state": "prepared", "availability": "available",
        "implementation": {"kind": "validator", "ref": CONTRACT_VERSION, "owner": "backend"},
        "requires": ["tool_result", "agent_result", "script_result"], "produces": ["capability_snapshot"],
        "authorization": {"mode": "inspect", "permissions": [], "approval_required": False},
        "evidence_expected": ["contrato validado"], "fallback_piece_id": None, "block_reason": None,
    }
    pieces = [input_piece, *discovered, output_piece]
    routes = []
    for priority, piece in enumerate(discovered, start=1):
        routes.append({
            "id": f"inspect-{piece['id']}",
            "name": f"Inspeccionar {piece['name']}",
            "description": "Ruta declarativa de inspección; no ejecuta la pieza.",
            "priority": priority,
            "condition": f"La pieza {piece['id']} está seleccionada para inspección.",
            "steps": [input_piece["id"], piece["id"], output_piece["id"]],
            "availability": piece["availability"],
            "block_reason": piece["block_reason"],
            "fallback_route_id": None,
            "evidence_expected": ["snapshot de inventario validado"],
        })

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "revision": 1,
        "etag": "",
        "source": {
            "authority": "backend",
            "provenance": f"bago_inventory:{root_source}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "capability": {
            "id": CAPABILITY_ID,
            "name": "Inventario operativo de BAGO",
            "version": "0.2.0",
            "description": "Herramientas, agentes y scripts observados en la raíz autorizada.",
            "definition_state": "prepared",
            "availability": "available" if discovered else "conditional",
            "tags": ["bago", "inventory", "read-only"],
        },
        "construction": {
            "user_goal": "Inspeccionar de qué capacidades reales se compone BAGO sin confundir disponibilidad con ejecución.",
            "confirmed": [{"id": "inventory-observed", "statement": f"Se observaron {len(discovered)} piezas invocables.", "source": "backend_inventory"}],
            "assumptions": [], "missing_information": [], "decisions": [], "conflicts": [],
        },
        "inputs": [{"id": "workspace-root", "name": "Workspace autorizado", "required": True, "media_types": ["inode/directory"], "constraints": [root_source]}],
        "outputs": [{"id": "capability-snapshot", "name": "Instantánea de capacidades", "media_types": ["application/json"], "acceptance_criteria": ["Contrato v0.2 válido", "Sin claims de ejecución"]}],
        "pieces": pieces,
        "routes": routes,
        "governance": {
            "authority": {"decision": "backend", "execution": "backend", "verification": "backend"},
            "recommended_route_id": routes[0]["id"] if routes else None,
            "confirmation_policy": {"required_for": ["process.execute", "file.write", "network", "external_connector", "destructive"], "reason": "La anatomía es de solo lectura."},
            "action_policy": {
                "allowed": [{"id": "inspect", "kind": "inspect", "label": "Inspeccionar"}, {"id": "prepare", "kind": "prepare", "label": "Preparar para chat"}],
                "blocked": [{"id": "execute", "kind": "command", "label": "Ejecutar", "reason": "Requiere flujo backend gobernado."}, {"id": "save", "kind": "mutation", "label": "Guardar", "reason": "Contrato expuesto en modo de solo lectura."}],
            },
            "validation_criteria": [{"id": "contract-valid", "description": "Referencias y rutas cerradas.", "method": "validate_capability", "required": True}],
        },
        "runtime_snapshot": {"source": "none", "run_state": "not_started", "selected_piece_id": None, "active_route_id": None, "execution_id": None, "receipt_id": None, "observed_at": None},
        "host_binding": {"host": "BAGO", "surface": "graph", "mode": "read_only", "feature_flag": FEATURE_FLAG, "persistence_root": "none", "expected_contract_version": "bago.contract.ui.v1"},
        "evidence": [],
    }
    etag_source = json.dumps({"root": str(root), "pieces": pieces, "routes": routes}, sort_keys=True, ensure_ascii=True)
    payload["etag"] = hashlib.sha256(etag_source.encode("utf-8")).hexdigest()
    validate_capability(payload)
    return payload


def validate_capability(data: dict[str, Any]) -> None:
    if data.get("schema_version") != SCHEMA_VERSION or data.get("contract_version") != CONTRACT_VERSION:
        raise CapabilityContractError("Versión de contrato no soportada")
    pieces = data.get("pieces")
    routes = data.get("routes")
    if not isinstance(pieces, list) or len(pieces) < 2 or not isinstance(routes, list):
        raise CapabilityContractError("Piezas o rutas inválidas")
    piece_by_id = {str(piece.get("id")): piece for piece in pieces if isinstance(piece, dict)}
    if len(piece_by_id) != len(pieces):
        raise CapabilityContractError("IDs de pieza duplicados o vacíos")
    for piece in pieces:
        authorization = piece.get("authorization") or {}
        if authorization.get("mode") in {"execute", "mutate"} and not authorization.get("approval_required"):
            raise CapabilityContractError(f"{piece.get('id')}: ejecución o mutación sin aprobación")
        fallback = piece.get("fallback_piece_id")
        if fallback is not None and fallback not in piece_by_id:
            raise CapabilityContractError(f"{piece.get('id')}: fallback desconocido")
    for route in routes:
        steps = route.get("steps") or []
        if len(steps) < 2 or any(step not in piece_by_id for step in steps):
            raise CapabilityContractError(f"{route.get('id')}: referencias de ruta inválidas")
        if piece_by_id[steps[0]].get("type") != "input" or piece_by_id[steps[-1]].get("type") != "output":
            raise CapabilityContractError(f"{route.get('id')}: la ruta no cierra de entrada a salida")
    runtime = data.get("runtime_snapshot") or {}
    if runtime.get("run_state") == "succeeded":
        if not runtime.get("execution_id") or not runtime.get("receipt_id") or not data.get("evidence"):
            raise CapabilityContractError("Éxito sin execution_id, receipt_id y evidencia")
    host = data.get("host_binding") or {}
    if host.get("mode") == "read_only":
        allowed = ((data.get("governance") or {}).get("action_policy") or {}).get("allowed") or []
        if any(action.get("kind") == "mutation" for action in allowed if isinstance(action, dict)):
            raise CapabilityContractError("Mutación permitida en host de solo lectura")
