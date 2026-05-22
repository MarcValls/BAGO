"""_registry_entries_integrity.py — Subset of BAGO tool registry."""
from __future__ import annotations

from _registry_models import PreflightCheck, ToolEntry
from _registry_paths import BAGO_ROOT, TOOLS_DIR

_ENTRIES: dict[str, ToolEntry] = {
    "version-check": ToolEntry(
        cmd="version-check", module="version_truth",
        description="Version Truth Lock: check | sync <ver> | audit --json",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "version_truth.py"))],
        layer="calidad", scope="framework",
        agent="CENTINELA",
        stability="core",
        risk="safe",
        supports_dry_run=True,
        preflight_policy="required",
    ),
    "bootstrap-state": ToolEntry(
        cmd="bootstrap-state", module="install_contract",
        description="Bootstrap clean runtime state from template",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "install_contract.py"))],
        layer="infraestructura", scope="framework",
        agent="ARQUITECTO",
        stability="core",
        risk="mutating",
        supports_dry_run=False,
        preflight_policy="required",
    ),
    "git-dirty": ToolEntry(
        cmd="git-dirty", module="git_dirty_guard",
        description="Detect git dirty state: --json",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "git_dirty_guard.py"))],
        layer="calidad", scope="framework",
        agent="CENTINELA",
        stability="core",
        risk="safe",
        supports_dry_run=True,
        preflight_policy="required",
    ),
    "test": ToolEntry(
        cmd="test", module="test_gate",
        description="Run pytest suite",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "test_gate.py"))],
        layer="calidad", scope="framework",
        agent="VALIDADOR",
        stability="core",
        risk="safe",
        supports_dry_run=True,
        preflight_policy="required",
    ),
    "integrity": ToolEntry(
        cmd="integrity", module="autonomous_integrity",
        description="Full integrity sensor sweep: --json",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "autonomous_integrity.py"))],
        layer="calidad", scope="framework",
        agent="CENTINELA",
        stability="core",
        risk="safe",
        supports_dry_run=True,
        preflight_policy="required",
    ),
    "issues": ToolEntry(
        cmd="issues", module="bago_issues",
        description="Gestiona issues de GitHub asignados a BAGO (label bago): list, show, take, close, create",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "bago_issues.py"))],
        layer="core", scope="framework",
        agent="PLANIFICADOR",
        stability="core",
        risk="safe",
        supports_dry_run=False,
    ),
}
