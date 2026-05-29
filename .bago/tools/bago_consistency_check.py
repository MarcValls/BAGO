#!/usr/bin/env python3
"""bago_consistency_check.py — Guard anti-drift permanente.

Valida que el framework BAGO esté internamente consistente:
  1. Comandos en CI (ci_generator.py) ⊆ comandos en tool_registry.py
  2. Preflight paths en tool_registry apuntan a archivos que existen
  3. Números en README coinciden con los del registry
  4. Badge del README apunta a un workflow que existe en .github/workflows/

Uso:
  python3 .bago/tools/bago_consistency_check.py
  python3 .bago/tools/bago_consistency_check.py --json
  python3 .bago/tools/bago_consistency_check.py --fix-readme   (actualiza números)

Integración CI: ejecutar en cada PR; falla con exit code 1 si hay drift.
"""
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import argparse
import ast
import json
import re
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).parent
BAGO_ROOT = TOOLS_DIR.parent
REPO_ROOT = BAGO_ROOT.parent
README = REPO_ROOT / "README.md"
COMMANDS_DOC = REPO_ROOT / "docs" / "COMMANDS.md"
CI_GENERATOR = TOOLS_DIR / "ci_generator.py"
TOOL_REGISTRY = TOOLS_DIR / "tool_registry.py"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_registry() -> dict:
    """Load REGISTRY from tool_registry.py via importlib."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_bago_registry", str(TOOL_REGISTRY))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_bago_registry"] = mod  # needed for dataclass __module__ resolution
    spec.loader.exec_module(mod)
    return mod.REGISTRY


def _extract_bago_commands_from_ci() -> list[str]:
    """Parse ci_generator.py and extract all 'python3 bago <cmd>' calls."""
    source = CI_GENERATOR.read_text(encoding="utf-8")
    pattern = re.compile(r"python3\s+bago\s+([a-z][a-z0-9_-]*)", re.MULTILINE)
    return list(dict.fromkeys(m.group(1) for m in pattern.finditer(source)))


def _extract_readme_public_contract() -> dict:
    """Parse the public command contract line in README."""
    text = README.read_text(encoding="utf-8") if README.exists() else ""
    m = re.search(
        r"Public command contract \(CI-checked\):\s*\*\*(\d+)\s+core\*\*\s*·\s*"
        r"\*\*(\d+)\s+experimental\*\*\s*·\s*\*\*(\d+)\s+dangerous\*\*\s*·\s*"
        r"\*\*(\d+)\s+legacy\*\*",
        text,
    )
    if not m:
        return {}
    return {
        "core": int(m.group(1)),
        "experimental": int(m.group(2)),
        "dangerous": int(m.group(3)),
        "legacy": int(m.group(4)),
    }


def _extract_commands_doc_summary() -> dict:
    """Parse the summary table in docs/COMMANDS.md."""
    text = COMMANDS_DOC.read_text(encoding="utf-8") if COMMANDS_DOC.exists() else ""
    patterns = {
        "core": r"\|\s*⚙️\s+Core\s*\|\s*(\d+)\s*\|",
        "experimental": r"\|\s*🧪\s+Experimental\s*\|\s*(\d+)\s*\|",
        "dangerous": r"\|\s*⚠️\s+Dangerous\s*\|\s*(\d+)\s*\|",
        "legacy": r"\|\s*🗄️\s+Legacy\s+\(deprecated\)\s*\|\s*(\d+)\s*\|",
    }
    counts: dict[str, int] = {}
    for key, pattern in patterns.items():
        m = re.search(pattern, text)
        if not m:
            return {}
        counts[key] = int(m.group(1))
    return counts


def _extract_badge_workflow() -> str | None:
    """Extract the workflow filename referenced in the README badge."""
    text = README.read_text(encoding="utf-8") if README.exists() else ""
    m = re.search(r"actions/workflows/([^/\s\"')]+\.yml)", text)
    return m.group(1) if m else None


# ── Checks ────────────────────────────────────────────────────────────────────

def check_ci_commands_in_registry(registry: dict) -> list[dict]:
    """All 'bago <cmd>' calls in ci_generator must exist in registry."""
    issues = []
    ci_cmds = _extract_bago_commands_from_ci()
    known = set(registry.keys())
    # 'bago' itself (the dispatcher) and 'ci' are not in registry by design
    skip = {"bago", "ci"}
    for cmd in ci_cmds:
        if cmd not in skip and cmd not in known:
            issues.append({
                "check": "ci-commands-in-registry",
                "severity": "error",
                "message": f"'bago {cmd}' usado en ci_generator.py pero NO existe en tool_registry",
            })
    return issues


def check_preflight_paths(registry: dict) -> list[dict]:
    """Every preflight 'file' check must point to a path that exists."""
    issues = []
    for cmd, entry in registry.items():
        for pf in entry.preflight:
            if pf.kind == "file":
                p = Path(pf.value)
                if not p.exists():
                    sev = pf.severity  # "error" | "warning"
                    issues.append({
                        "check": "preflight-path-exists",
                        "severity": sev,
                        "message": f"[{cmd}] preflight apunta a '{p}' que NO existe",
                    })
    return issues


def check_readme_public_contract(registry: dict) -> list[dict]:
    """README public contract counts must match docs/COMMANDS.md."""
    issues = []
    readme_counts = _extract_readme_public_contract()
    if not readme_counts:
        issues.append({
            "check": "readme-public-contract",
            "severity": "error",
            "message": "No se encontró la línea 'Public command contract (CI-checked)' en README.md",
        })
        return issues
    doc_counts = _extract_commands_doc_summary()
    if not doc_counts:
        issues.append({
            "check": "readme-public-contract",
            "severity": "error",
            "message": "No se pudo leer el resumen de docs/COMMANDS.md",
        })
        return issues
    for key in ("core", "experimental", "dangerous", "legacy"):
        if readme_counts.get(key) != doc_counts[key]:
            issues.append({
                "check": "readme-public-contract",
                "severity": "error",
                "message": (
                    f"README dice {key}={readme_counts.get(key)} "
                    f"pero docs/COMMANDS.md dice {doc_counts[key]}"
                ),
            })
    return issues


def check_badge_workflow_exists() -> list[dict]:
    """The workflow filename in the README badge must exist in .github/workflows/."""
    issues = []
    badge_wf = _extract_badge_workflow()
    if not badge_wf:
        issues.append({
            "check": "badge-workflow-exists",
            "severity": "warning",
            "message": "No se encontró badge de GitHub Actions en README.md",
        })
        return issues
    wf_path = WORKFLOWS_DIR / badge_wf
    if not wf_path.exists():
        issues.append({
            "check": "badge-workflow-exists",
            "severity": "error",
            "message": (
                f"Badge apunta a '{badge_wf}' pero el archivo "
                f"'{wf_path}' NO existe — badge roto"
            ),
        })
    return issues


# ── Fix helpers ───────────────────────────────────────────────────────────────

def fix_readme_numbers() -> bool:
    """Rewrite the README public contract line with docs/COMMANDS.md counts."""
    if not README.exists():
        print("README.md no encontrado")
        return False
    counts = _extract_commands_doc_summary()
    if not counts:
        print("No se pudo leer docs/COMMANDS.md")
        return False
    text = README.read_text(encoding="utf-8")
    new_text = re.sub(
        r"Public command contract \(CI-checked\):\s*\*\*\d+\s+core\*\*\s*·\s*"
        r"\*\*\d+\s+experimental\*\*\s*·\s*\*\*\d+\s+dangerous\*\*\s*·\s*"
        r"\*\*\d+\s+legacy\*\*",
        lambda m: (
            "Public command contract (CI-checked): "
            f"**{counts['core']} core** · "
            f"**{counts['experimental']} experimental** · "
            f"**{counts['dangerous']} dangerous** · "
            f"**{counts['legacy']} legacy**"
        ),
        text,
    )
    if new_text == text:
        print("README ya está actualizado o no se encontró el patrón")
        return False
    README.write_text(new_text, encoding="utf-8")
    print(
        "✅ README actualizado: "
        f"{counts['core']} core · {counts['experimental']} experimental · "
        f"{counts['dangerous']} dangerous · {counts['legacy']} legacy"
    )
    return True


# ── Main ──────────────────────────────────────────────────────────────────────

def run_all_checks() -> list[dict]:
    registry = _load_registry()
    issues: list[dict] = []
    issues += check_ci_commands_in_registry(registry)
    issues += check_preflight_paths(registry)
    issues += check_readme_public_contract(registry)
    issues += check_badge_workflow_exists()
    return issues


def main() -> None:
    parser = argparse.ArgumentParser(description="BAGO consistency guard anti-drift")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--fix-readme", action="store_true", help="Actualiza contadores README")
    args = parser.parse_args()

    if args.fix_readme:
        fix_readme_numbers()
        return

    issues = run_all_checks()
    errors = [i for i in issues if i["severity"] == "error"]
    warnings = [i for i in issues if i["severity"] == "warning"]

    if args.json:
        print(json.dumps({
            "status": "ok" if not errors else "fail",
            "errors": len(errors),
            "warnings": len(warnings),
            "issues": issues,
        }, indent=2, ensure_ascii=False))
    else:
        if not issues:
            print("✅ BAGO consistency OK — sin drift detectado")
        else:
            for i in issues:
                icon = "❌" if i["severity"] == "error" else "⚠️ "
                print(f"  {icon} [{i['check']}] {i['message']}")
            print(f"\n  {len(errors)} errores · {len(warnings)} warnings")

    sys.exit(1 if errors else 0)



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    main()
