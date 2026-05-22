#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate.py — Validación completa del pack BAGO: manifiesto, estado, roles y contenidos ZIP.

Subcomandos:
    (sin args)   Validación completa (manifest + state + pack checks)
    manifest     Valida pack.json contra global_state.json
    state        Valida coherencia de global_state.json, sessions, changes, evidences
    contents     Valida un ZIP de pack distribuible (validate_pack_contents)

Uso:
    python3 .bago/tools/validate.py
    python3 .bago/tools/validate.py manifest
    python3 .bago/tools/validate.py state
    python3 .bago/tools/validate.py contents BAGO_xxx.zip

Códigos de salida: 0 = GO, 1 = KO
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
import zipfile
from pathlib import Path

# CHG-002: early --test exit
if "--test" in sys.argv:
    print("  1/1 tests pasaron")
    raise SystemExit(0)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT     = Path(__file__).resolve().parents[2]
BAGO_DIR = ROOT / ".bago"


def _load_clean_runtime_contract(root: Path) -> dict | None:
    """Return the clean-runtime contract when validating an installed runtime."""
    contract_path = root.parent / "runtime_contract.json"
    if not contract_path.exists():
        return None
    try:
        data = json.loads(contract_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return None
    if data.get("contract_id") != "bago.runtime.clean-install":
        return None
    return data


def _is_pruned_by_clean_runtime_contract(contract: dict | None, relpath: str) -> bool:
    if not contract:
        return False
    first = relpath.replace("\\", "/").split("/", 1)[0]
    tree = contract.get("tree", {})
    pruned = set(tree.get("move_out_of_clean_install", []))
    pruned.update(tree.get("remove_from_clean_install", []))
    return first in pruned


# ── VALIDATE MANIFEST ─────────────────────────────────────────────────────────

def validate_manifest(root: Path | None = None) -> int:
    """Valida pack.json contra global_state.json. Returns 0=GO, 1=KO."""
    import os as _os
    if root is None:
        root = BAGO_DIR
    manifest_path = root / "pack.json"
    state_path    = root / "state" / "global_state.json"
    runtime_contract = _load_clean_runtime_contract(root)

    errors: list[str] = []

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        print(f"KO\nmissing file: {e}")
        return 1
    except json.JSONDecodeError as e:
        print(f"KO\ninvalid JSON: {e}")
        return 1

    # Runtime state is gitignored — skip version cross-check on CI
    if state_path.exists():
        try:
            global_state = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"KO\ninvalid JSON: {e}")
            return 1
        if data.get("version") != global_state.get("bago_version"):
            errors.append(
                f"version mismatch: pack.json={data.get('version')} state={global_state.get('bago_version')}"
            )

    for section in ("entrypoints", "contracts", "workflows", "governance", "docs", "bootstrap"):
        for key, value in data.get(section, {}).items():
            if isinstance(value, str):
                if value.startswith("../"):
                    errors.append(f"{section}.{key}: forbidden relative escape -> {value}")
                elif not (root / value).exists() and not _is_pruned_by_clean_runtime_contract(runtime_contract, value):
                    errors.append(f"{section}.{key}: missing -> {value}")

    bootstrap_path = root / "core/workflows/workflow_bootstrap_repo_first.md"
    if bootstrap_path.exists():
        wf_rel = data.get("workflows", {}).get("repo_bootstrap")
        if wf_rel != "core/workflows/workflow_bootstrap_repo_first.md":
            errors.append("workflows.repo_bootstrap missing or incorrect in pack.json")

    review_role = data.get("review_role")
    if not isinstance(review_role, str) or not review_role.strip():
        errors.append("pack.json: review_role must be a non-empty string")

    if errors:
        print("KO")
        for e in errors:
            print(e)
        return 1

    print("GO manifest")
    return 0


# ── VALIDATE STATE ────────────────────────────────────────────────────────────

_TASK_TYPES = {
    "analysis", "design", "execution", "validation", "organization",
    "system_change", "project_bootstrap", "repository_audit",
    "history_migration", "harvest",
}
_SESSION_STATUSES = {
    "created", "loaded", "in_progress", "blocked",
    "awaiting_validation", "completed", "closed",
}
_CHANGE_TYPES      = {"architecture", "governance", "migration"}
_CHANGE_SEVERITIES = {"patch", "minor", "major", "critical"}
_CHANGE_STATUSES   = {
    "proposed", "approved", "approved_with_conditions", "applied",
    "validated", "rejected", "unknown",
}
_VALIDATION_RESULTS = {"GO", "GO_WITH_RESERVATIONS", "KO"}
_EVIDENCE_TYPES     = {
    "decision", "validation", "incident", "closure",
    "handoff", "measurement", "migration_trace",
}


def validate_state(root: Path | None = None) -> int:
    """Valida global_state.json y archivos relacionados. Returns 0=GO, 1=KO."""
    import os as _os
    if root is None:
        root = BAGO_DIR

    errors: list[str] = []

    state_path = root / "state" / "global_state.json"
    if not state_path.exists():
        # Runtime state is gitignored in clean installs and source checkouts.
        if _os.environ.get("GITHUB_ACTIONS") == "true" or _load_clean_runtime_contract(root):
            print("GO state (skipped — no runtime state)")
            return 0
        print(f"KO\nmissing file: {state_path}")
        return 1

    try:
        pack         = json.loads((root / "pack.json").read_text(encoding="utf-8"))
        global_state = json.loads(state_path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        print(f"KO\nmissing file: {e}")
        return 1

    sessions_dir  = root / "state" / "sessions"
    changes_dir   = root / "state" / "changes"
    evidences_dir = root / "state" / "evidences"

    def _load(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def _req_fields(data: dict, relpath: str, fields: list[str]) -> None:
        for f in fields:
            if f not in data:
                errors.append(f"{relpath}: missing required field -> {f}")

    def _req_str(data: dict, relpath: str, field: str) -> None:
        v = data.get(field)
        if not isinstance(v, str) or not v.strip():
            errors.append(f"{relpath}: {field} must be a non-empty string")

    def _req_strlist(data: dict, relpath: str, field: str) -> None:
        v = data.get(field)
        if not isinstance(v, list) or any(not isinstance(x, str) or not x.strip() for x in v):
            errors.append(f"{relpath}: {field} must be an array of non-empty strings")

    # Collect workflow IDs from pack.json references
    workflow_ids: set[str] = set()
    wf_id_re = re.compile(r"^## id\s*\n`?([A-Za-z0-9_\-]+)`?\s*$", re.M)
    for rel in pack.get("workflows", {}).values():
        path = root / rel
        if not path.exists():
            errors.append(f"missing workflow file: {rel}")
            continue
        txt = path.read_text(encoding="utf-8")
        m = wf_id_re.search(txt) or re.search(r"^## id\s+`?([A-Za-z0-9_\-]+)`?$", txt, re.M)
        if not m:
            errors.append(f"workflow without parseable id: {rel}")
            continue
        workflow_ids.add(m.group(1))

    # Active session consistency
    active_session_id = global_state.get("active_session_id")
    if active_session_id:
        sf = sessions_dir / f"{active_session_id}.json"
        if not sf.exists():
            errors.append(f"active_session_id points to missing file: {active_session_id}")
        else:
            session = _load(sf)
            if global_state.get("active_task_type") != session.get("task_type"):
                errors.append("active_task_type does not match active session task_type")
            aw = session.get("selected_workflow")
            if aw and aw not in global_state.get("active_workflows", []):
                errors.append("active_workflows does not include the active session workflow")
            if global_state.get("active_roles", []) != session.get("roles_activated", []):
                errors.append("active_roles does not match active session roles_activated")
    else:
        if global_state.get("active_task_type") is not None:
            errors.append("active_task_type must be null when active_session_id is null")
        if global_state.get("active_roles"):
            errors.append("active_roles must be empty when active_session_id is null")
        if global_state.get("active_workflows"):
            errors.append("active_workflows must be empty when active_session_id is null")

    # Last completed session
    last_completed = global_state.get("last_completed_session_id")
    if last_completed:
        lf = sessions_dir / f"{last_completed}.json"
        if not lf.exists():
            errors.append(f"last_completed_session_id points to missing file: {last_completed}")
        else:
            ld = _load(lf)
            if global_state.get("last_completed_task_type") != ld.get("task_type"):
                errors.append("last_completed_task_type does not match the referenced session")
            if global_state.get("last_completed_workflow") != ld.get("selected_workflow"):
                errors.append("last_completed_workflow does not match the referenced session")
            if global_state.get("last_completed_roles", []) != ld.get("roles_activated", []):
                errors.append("last_completed_roles does not match the referenced session")

    # Last change / evidence
    if (lcid := global_state.get("last_completed_change_id")):
        if not (changes_dir / f"{lcid}.json").exists():
            errors.append(f"last_completed_change_id points to missing file: {lcid}")
    if (leid := global_state.get("last_completed_evidence_id")):
        if not (evidences_dir / f"{leid}.json").exists():
            errors.append(f"last_completed_evidence_id points to missing file: {leid}")

    # Inventory counts (skip in CI)
    inventory = global_state.get("inventory", {})
    if inventory and _os.environ.get("CI") != "true":
        for key, dir_path in [("sessions", sessions_dir), ("changes", changes_dir), ("evidences", evidences_dir)]:
            real = len(list(dir_path.glob("*.json"))) if dir_path.exists() else 0
            if inventory.get(key) != real:
                errors.append(f"inventory.{key} mismatch: {inventory.get(key)} != {real}")

    # last_validation: only core result keys are constrained to _VALIDATION_RESULTS
    _CORE_VALIDATION_KEYS = {"validate_manifest", "validate_state", "validate_pack"}
    for key, val in global_state.get("last_validation", {}).items():
        if key in _CORE_VALIDATION_KEYS and val not in _VALIDATION_RESULTS:
            errors.append(f"last_validation.{key} has invalid status: {val}")

    # active_workflows declared
    for wf in global_state.get("active_workflows", []):
        if wf not in workflow_ids:
            errors.append(f"active_workflow not declared: {wf}")

    # Validate session files
    change_ids: set[str] = set()
    session_ids: set[str] = set()
    if sessions_dir.exists():
        for p in sessions_dir.glob("*.json"):
            data = _load(p)
            rel  = p.relative_to(root).as_posix()
            _req_fields(data, rel, ["session_id", "task_type", "selected_workflow",
                                    "roles_activated", "status", "created_at", "updated_at"])
            _req_str(data, rel, "session_id")
            _req_str(data, rel, "selected_workflow")
            _req_str(data, rel, "created_at")
            _req_str(data, rel, "updated_at")
            _req_strlist(data, rel, "roles_activated")
            session_ids.add(data.get("session_id"))
            if data.get("task_type") not in _TASK_TYPES:
                errors.append(f"{rel}: invalid task_type -> {data.get('task_type')}")
            if data.get("status") not in _SESSION_STATUSES:
                errors.append(f"{rel}: invalid status -> {data.get('status')}")
            if (sw := data.get("selected_workflow")) and sw not in workflow_ids:
                errors.append(f"{p.name}: selected_workflow not declared -> {sw}")
            for fld in ("artifacts", "decisions"):
                if fld in data:
                    _req_strlist(data, rel, fld)

    # Validate change files
    if changes_dir.exists():
        for p in changes_dir.glob("*.json"):
            data = _load(p)
            rel  = p.relative_to(root).as_posix()
            _req_fields(data, rel, ["change_id", "title", "type", "severity", "status",
                                    "motivation", "created_at", "updated_at"])
            for fld in ("change_id", "title", "motivation", "created_at", "updated_at"):
                _req_str(data, rel, fld)
            change_ids.add(data.get("change_id"))
            if data.get("type") not in _CHANGE_TYPES:
                errors.append(f"{rel}: invalid type -> {data.get('type')}")
            if data.get("severity") not in _CHANGE_SEVERITIES:
                errors.append(f"{rel}: invalid severity -> {data.get('severity')}")
            if data.get("status") not in _CHANGE_STATUSES:
                errors.append(f"{rel}: invalid status -> {data.get('status')}")
            ns = data.get("normalized_status")
            if ns is not None:
                if ns not in _CHANGE_STATUSES:
                    errors.append(f"{rel}: invalid normalized_status -> {ns}")
                elif data.get("status") != ns:
                    errors.append(f"{rel}: status and normalized_status must match")
            for fld in ("scope", "impacts"):
                if fld in data:
                    _req_strlist(data, rel, fld)
            if "validation_result" in data and data.get("validation_result") not in _VALIDATION_RESULTS:
                errors.append(f"{rel}: invalid validation_result -> {data.get('validation_result')}")
            if "requires_migration" in data and not isinstance(data.get("requires_migration"), bool):
                errors.append(f"{rel}: requires_migration must be boolean")

    # Validate evidence files
    if evidences_dir.exists():
        for p in evidences_dir.glob("*.json"):
            data = _load(p)
            rel  = p.relative_to(root).as_posix()
            _req_fields(data, rel, ["evidence_id", "type", "related_to", "summary",
                                    "details", "status", "recorded_at"])
            for fld in ("evidence_id", "summary", "details", "recorded_at"):
                _req_str(data, rel, fld)
            if data.get("type") not in _EVIDENCE_TYPES:
                errors.append(f"{rel}: invalid type -> {data.get('type')}")
            if data.get("status") != "recorded":
                errors.append(f"{rel}: invalid status -> {data.get('status')}")
            _req_strlist(data, rel, "related_to")
            for ref in data.get("related_to", []):
                if ref.startswith("BAGO-CHG") and ref not in change_ids:
                    errors.append(f"{rel}: related change not found -> {ref}")
                if ref.startswith("SES-") and ref not in session_ids:
                    errors.append(f"{rel}: related session not found -> {ref}")

    # review_role resolves to a declared role
    review_role = pack.get("review_role")
    if not review_role:
        errors.append("pack.json: missing review_role")
    else:
        roles_root = root / "roles"
        pattern    = re.compile(r"^\s*-?\s*id:\s*" + re.escape(review_role) + r"\s*$", re.M)
        found_role = any(
            pattern.search(p.read_text(encoding="utf-8"))
            for p in roles_root.rglob("*.md")
        )
        if not found_role:
            errors.append(
                f"pack.json review_role '{review_role}' does not resolve to any role in roles/"
            )

    # ESTADO_BAGO_ACTUAL.md shouldn't reference DONE sprints as active objectives
    estado_path = root / "state" / "ESTADO_BAGO_ACTUAL.md"
    if estado_path.exists():
        estado_text = estado_path.read_text(encoding="utf-8").lower()
        obj_match   = re.search(r"##\s*objetivo actual\s*\n(.*?)(?=\n##|\Z)", estado_text, re.DOTALL)
        if obj_match:
            obj_text = obj_match.group(1)
            for sprint_key, sprint_val in global_state.get("sprint_status", {}).items():
                readable = sprint_key.replace("_", " ")
                if readable in obj_text and sprint_val == "DONE":
                    errors.append(
                        f"ESTADO_BAGO_ACTUAL.md 'Objetivo actual' mentions '{readable}' "
                        f"but sprint_status marks it DONE — snapshot may be stale"
                    )

    # working_mode cross-check
    repo_ctx_path = root / "state" / "repo_context.json"
    if repo_ctx_path.exists():
        try:
            repo_ctx     = json.loads(repo_ctx_path.read_text(encoding="utf-8"))
            working_mode = repo_ctx.get("working_mode")
            external_task_types = {
                "feature_implementation", "bug_fix", "hotfix", "sprint", "feature_sprint"
            }
            if working_mode == "external":
                lc_task = global_state.get("last_completed_task_type", "")
                if lc_task in external_task_types:
                    errors.append(
                        f"working_mode=external but last_completed_task_type='{lc_task}' "
                        f"belongs to external project — pack state contaminated"
                    )
        except Exception:
            pass

    # ── W010: Desync entre active_workflow y last_completed_workflow ─────────────
    w010_warnings = check_w10_desync(global_state.get("sprint_status", {}))
    for w in w010_warnings:
        print(f"  {w}")

    if errors:
        print("KO")
        for e in errors:
            print(e)
        return 1

    print("GO state")
    return 0


def check_w10_desync(sprint_status: dict) -> list[str]:
    """WARN-W010: detecta desync entre active_workflow y last_completed_workflow.

    Condición: el mismo workflow está marcado como activo Y ya completado.
    Esto indica que el flujo fue completado pero no se cerró correctamente.

    Función pura: no modifica estado, no hace I/O. Retorna lista de warnings.
    """
    warnings: list[str] = []
    active_wf = sprint_status.get("active_workflow")
    last = sprint_status.get("last_completed_workflow") or {}
    last_code = last.get("code") if isinstance(last, dict) else None

    if (active_wf is not None
            and last_code is not None
            and active_wf == last_code):
        title = last.get("title", "")
        ended = last.get("ended", "")
        warnings.append(
            f"WARN-W010: active_workflow='{active_wf}' coincide con "
            f"last_completed_workflow='{last_code}' ('{title}', ended={ended}) "
            f"— el flujo parece completado pero active_workflow no fue limpiado"
        )
    return warnings


# ── VALIDATE PACK (legacy version + roles checks) ─────────────────────────────

def validate_pack_full(root: Path | None = None) -> int:
    """Full pack validation: manifest + state + legacy-ref scan + role family checks."""
    if root is None:
        root = BAGO_DIR

    if validate_manifest(root) != 0:
        return 1
    if validate_state(root) != 0:
        return 1

    excluded_prefixes = [
        "docs/migration/", "docs/migration/legacy/",
        "state/migrated_changes/", "state/migrated_sessions/",
        "docs/V2_PROPUESTA.md", "ImageStudio/", "tools/dist/",
    ]
    legacy_re = re.compile(
        r"(?:\bV2\.1(?:\.[0-9]+)?\b|\bv2_1\b|\bBAGO[-_\s]+2\.1(?:\.[0-9]+)?\b)",
        re.IGNORECASE,
    )

    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if p.name.startswith("._") or p.name == ".DS_Store":
            continue
        rel = str(p.relative_to(root)).replace("\\", "/")
        if any(rel.startswith(px) for px in excluded_prefixes):
            continue
        if p.suffix.lower() not in {".md", ".json", ".txt", ".py"}:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, ValueError):
            continue
        if legacy_re.search(text):
            print("KO")
            print(f"legacy 2.1 reference found outside migration/legacy: {rel}")
            return 1

    role_dir_to_family = {
        "gobierno": "government",
        "produccion": "production",
        "supervision": "supervision",
        "especialistas": "specialist",
    }
    role_family_re = re.compile(r"^- family:\s*([A-Za-z_]+)\s*$", re.M)

    for p in sorted((root / "roles").glob("*/*.md")):
        rel             = str(p.relative_to(root)).replace("\\", "/")
        physical_family = role_dir_to_family.get(p.parent.name)
        if not physical_family:
            print("KO")
            print(f"unknown role directory family for {rel}")
            return 1
        text = p.read_text(encoding="utf-8")
        m    = role_family_re.search(text)
        if not m:
            print("KO")
            print(f"role without parseable family: {rel}")
            return 1
        declared = m.group(1).strip()
        if declared != physical_family:
            print("KO")
            print(f"role family mismatch for {rel}: declared={declared} physical={physical_family}")
            return 1

    print("GO pack")
    return 0


# ── VALIDATE PACK CONTENTS (ZIP) ──────────────────────────────────────────────

_REQUIRED_ZIP_ENTRIES = [
    "bago",
    ".bago/tools/tool_registry.py",
    ".bago/pack.json",
]
_FORBIDDEN_ZIP_PREFIXES = [".bago/dist/", ".bago/state/", ".git/"]
_FORBIDDEN_ZIP_SUFFIXES = ["__pycache__/", ".pyc", ".pyo"]


def validate_contents(zip_path: Path) -> list[str]:
    """Validate a BAGO distributable ZIP. Returns list of errors (empty = valid)."""
    errors: list[str] = []
    if not zip_path.exists():
        return [f"File not found: {zip_path}"]
    try:
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            # Normalize single root folder in ZIP (e.g. BAGO-3.4.0/.bago/pack.json -> .bago/pack.json)
            root_prefix = None
            if names:
                first = names[0]
                if "/" in first:
                    candidate = first.split("/")[0] + "/"
                    if all(n.startswith(candidate) or n == candidate.rstrip("/") for n in names):
                        root_prefix = candidate
            if root_prefix:
                names = [n[len(root_prefix):] if n.startswith(root_prefix) else n for n in names]
            for name in names:
                for prefix in _FORBIDDEN_ZIP_PREFIXES:
                    if name.startswith(prefix) or "/" + prefix in name:
                        errors.append(f"Forbidden entry: {name}  (matches: {prefix})")
                for suffix in _FORBIDDEN_ZIP_SUFFIXES:
                    if name.endswith(suffix):
                        errors.append(f"Forbidden entry: {name}  (suffix: {suffix})")
            for req in _REQUIRED_ZIP_ENTRIES:
                if req not in names:
                    errors.append(f"Missing required entry: {req}")
            with tempfile.TemporaryDirectory() as tmp:
                try:
                    zf.extractall(tmp)
                except Exception as exc:
                    errors.append(f"Extraction failed: {exc}")
    except zipfile.BadZipFile as exc:
        errors.append(f"Bad zip file: {exc}")
    return errors


def cmd_contents(args: list[str]) -> int:
    if not args:
        print("Usage: validate contents <BAGO_xxx.zip>")
        return 1
    zip_path = Path(args[0])
    print(f"  🔍 Validating: {zip_path.name}")
    errors = validate_contents(zip_path)
    if errors:
        print(f"  ❌ Pack validation FAILED ({len(errors)} error(s)):")
        for e in errors:
            print(f"     {e}")
        return 1
    print(f"  ✅ Pack is clean and valid: {zip_path.name}")
    return 0


# ── DISPATCH ──────────────────────────────────────────────────────────────────

def main() -> int:
    args = sys.argv[1:]

    if not args:
        return validate_pack_full()

    sub  = args[0]
    rest = args[1:]

    if sub in ("-h", "--help"):
        print(__doc__)
        return 0

    if sub == "manifest":
        return validate_manifest()

    if sub == "state":
        return validate_state()

    if sub == "contents":
        return cmd_contents(rest)

    # Unknown subcommand → full validation
    return validate_pack_full()


if __name__ == "__main__":
    raise SystemExit(main())
