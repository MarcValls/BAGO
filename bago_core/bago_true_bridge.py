from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_TRUE_ROOT = Path(r"C:\bago_true\.bago")
DEFAULT_APPDATA_ROOT = Path(r"C:\Users\AMTEC_Terminal_1o\AppData\Local\Programs\BAGO")

EXPECTED_TRUE_SUBSYSTEMS = [
    "agents",
    "core",
    "tools",
    "workflows",
    "supervision",
    "knowledge",
    "mcp",
    "roles",
    "rl",
    "prompts",
]

EXCLUDED_NAMES = {
    "state",
    "logs",
    "backups",
    "snapshots",
    "traces",
    "user",
    "credentials",
    "checkpoints",
    "__pycache__",
}

def _safe_read_text(path: Path, limit: int = 300_000) -> str:
    if not path.exists() or not path.is_file():
        return ""
    with path.open("rb") as fh:
        return fh.read(limit).decode("utf-8", errors="replace")

def _json_file(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _dir_status(root: Path, names: list[str]) -> list[dict[str, Any]]:
    items = []
    for name in names:
        path = root / name
        items.append({
            "name": name,
            "exists": path.exists(),
            "path": str(path),
            "excluded": name in EXCLUDED_NAMES,
        })
    return items

def detect_bago_true(root: str | Path | None = None) -> dict[str, Any]:
    true_root = Path(root) if root else DEFAULT_TRUE_ROOT
    available = true_root.exists() and true_root.is_dir()
    install_config = _json_file(true_root / "install_config.json") if available else {}

    present_exclusions = []
    if available:
        for name in sorted(EXCLUDED_NAMES):
            if (true_root / name).exists():
                present_exclusions.append(name)

    rl_root = true_root / "rl"
    policies = rl_root / "training" / "policies.py"
    shadow = rl_root / "adapters" / "bago_rl_shadow.py"

    return {
        "name": "bago_true",
        "available": available,
        "root": str(true_root),
        "install_config": install_config,
        "subsystems": _dir_status(true_root, EXPECTED_TRUE_SUBSYSTEMS) if available else [],
        "excluded_present": present_exclusions,
        "rl": {
            "available": rl_root.exists(),
            "root": str(rl_root),
            "policies_py": policies.exists(),
            "shadow_adapter": shadow.exists(),
        },
        "rules": {
            "copy_whole_tree": False,
            "import_live_state": False,
            "bridge_only": True,
        },
    }

def detect_appdata(root: str | Path | None = None) -> dict[str, Any]:
    app_root = Path(root) if root else DEFAULT_APPDATA_ROOT
    available = app_root.exists() and app_root.is_dir()
    launcher = app_root / "bago_core" / "launcher.py"
    runtime_contract = app_root / "runtime_contract.json"
    launcher_text = _safe_read_text(launcher) if available else ""
    contract = _json_file(runtime_contract) if available else {}

    return {
        "name": "appdata_bago",
        "available": available,
        "root": str(app_root),
        "launcher": str(launcher),
        "launcher_exists": launcher.exists(),
        "runtime_contract": str(runtime_contract),
        "runtime_contract_exists": runtime_contract.exists(),
        "cmd_rl_supported": "cmd-rl" in launcher_text,
        "spiral_signals": ("Spiral" in launcher_text) or ("spiral" in launcher_text),
        "state_hint": contract.get("state_root") or contract.get("user_state") or contract.get("state_path"),
        "rules": {
            "required_for_boot": False,
            "migration_only": True,
        },
    }

def collect_status(
    true_root: str | Path | None = None,
    appdata_root: str | Path | None = None,
) -> dict[str, Any]:
    return {
        "bago_true": detect_bago_true(true_root),
        "appdata": detect_appdata(appdata_root),
    }

def render_status(status: dict[str, Any], section: str = "engine") -> str:
    true_status = status["bago_true"]
    appdata = status["appdata"]
    lines: list[str] = []

    if section in {"engine", "all"}:
        lines.append("BAGO ENGINE STATUS")
        lines.append("-" * 40)
        lines.append(f"bago_true: {'available' if true_status['available'] else 'unavailable'}")
        lines.append(f"root      : {true_status['root']}")
        if true_status["available"]:
            present = [item["name"] for item in true_status["subsystems"] if item["exists"]]
            missing = [item["name"] for item in true_status["subsystems"] if not item["exists"]]
            lines.append(f"subsystems: {', '.join(present) if present else 'none'}")
            if missing:
                lines.append(f"missing   : {', '.join(missing)}")
            lines.append(f"rl        : {'available' if true_status['rl']['available'] else 'unavailable'}")
            lines.append(f"rl shadow : {'yes' if true_status['rl']['shadow_adapter'] else 'no'}")
            lines.append(f"rl policy : {'yes' if true_status['rl']['policies_py'] else 'no'}")
            if true_status["excluded_present"]:
                lines.append(f"excluded  : {', '.join(true_status['excluded_present'])}")
        lines.append("rule      : bridge only; no live state import")

    if section in {"appdata", "cmd-rl", "all"}:
        if lines:
            lines.append("")
        lines.append("BAGO APPDATA STATUS")
        lines.append("-" * 40)
        lines.append(f"appdata   : {'available' if appdata['available'] else 'unavailable'}")
        lines.append(f"root      : {appdata['root']}")
        lines.append(f"launcher  : {'yes' if appdata['launcher_exists'] else 'no'}")
        lines.append(f"contract  : {'yes' if appdata['runtime_contract_exists'] else 'no'}")
        lines.append(f"cmd-rl    : {'yes' if appdata['cmd_rl_supported'] else 'no'}")
        lines.append(f"spiral    : {'yes' if appdata['spiral_signals'] else 'no'}")
        if appdata.get("state_hint"):
            lines.append(f"state hint: {appdata['state_hint']}")
        lines.append("rule      : optional migration source; not required for boot")

    return "\n".join(lines)
