"""Generate and verify the production WorldStateSnapshot callsite inventory."""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT / ".bago" / "core"))
from effect_registry import REGISTRY  # noqa: E402

OUTPUT = BACKEND_ROOT / "docs" / "contracts" / "world_state_snapshot_inventory.md"
BUILDERS = (BACKEND_ROOT / ".bago", BACKEND_ROOT / "bago_core")
AUTHORITY_KEYS = frozenset({"world_state_authority"})


def _enclosing_function(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> str:
    parent = parents.get(node)
    while parent is not None:
        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return parent.name
        parent = parents.get(parent)
    return "<module>"


def scan_inventory() -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    unbound: list[str] = []
    for root in BUILDERS:
        for source in sorted(root.rglob("*.py")):
            if source.name in {"execution_request.py", "world_state_snapshot.py"}:
                continue
            try:
                tree = ast.parse(source.read_text(encoding="utf-8-sig"), filename=str(source))
            except (OSError, SyntaxError) as exc:
                unbound.append(f"scanner_error:{source.relative_to(REPOSITORY_ROOT).as_posix()}:{exc}")
                continue
            parents = {
                child: parent
                for parent in ast.walk(tree)
                for child in ast.iter_child_nodes(parent)
            }
            for call in ast.walk(tree):
                if not (
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Name)
                    and call.func.id == "build_execution_request"
                ):
                    continue
                keywords = {item.arg: item.value for item in call.keywords}
                effect_node = keywords.get("effect_id")
                effect_id = (
                    effect_node.value
                    if isinstance(effect_node, ast.Constant) and isinstance(effect_node.value, str)
                    else "<dynamic>"
                )
                descriptor = REGISTRY.get(effect_id) if REGISTRY.contains(effect_id) else None
                authority_key = next((key for key in AUTHORITY_KEYS if key in keywords), "MISSING")
                authority_value = (
                    ast.unparse(keywords[authority_key])
                    if authority_key != "MISSING"
                    else "MISSING"
                )
                relative = source.relative_to(REPOSITORY_ROOT).as_posix()
                row = {
                    "file": relative,
                    "line": call.lineno,
                    "function": _enclosing_function(call, parents),
                    "effect": effect_id,
                    "mutates": str(descriptor.mutates) if descriptor else "dynamic",
                    "risk": descriptor.risk_level if descriptor else "dynamic",
                    "authority": authority_value,
                }
                rows.append(row)
                must_bind = descriptor.mutates if descriptor else True
                if must_bind and (
                    authority_key == "MISSING"
                    or isinstance(keywords.get(authority_key), ast.Constant)
                    and keywords[authority_key].value is None
                ):
                    unbound.append(f"{relative}:{call.lineno}:{effect_id}")
    return rows, unbound


def render_inventory(rows: list[dict[str, Any]], unbound: list[str]) -> str:
    lines = [
        "# WorldStateSnapshot production request inventory",
        "",
        f"Effect registry: `{REGISTRY.contract}` `{REGISTRY.version}` SHA-256 `{REGISTRY.digest}`.",
        "Scope: direct `build_execution_request` calls in `backend/.bago/` and `backend/bago_core/`.",
        f"Callsites: {len(rows)}; mutating or dynamic-effect calls without a usable `world_state_authority` input: {len(unbound)}.",
        "Gateway: mutating requests reject unspecified state and revalidate their authority-bound snapshot before Permit consumption and immediately before adapter dispatch.",
        "Strong effects: every registered mutating E5/E6 adapter must expose `revalidate_world_state`; missing hooks fail Gateway registry construction and unadapted effects remain denied.",
        "Process termination: `cleanup_zombies` binds PID, executable, command line, and creation time into the Permit target; the Gateway re-enumerates candidates before consumption/dispatch and the Windows terminator rechecks exact identities before acting.",
        "",
        "| File | Line | Function | Effect | Mutates | Risk | Snapshot authority value |",
        "|---|---:|---|---|---:|---|---|",
    ]
    for row in rows:
        lines.append(
            "| " + " | ".join(str(row[key]) for key in (
                "file", "line", "function", "effect", "mutates", "risk", "authority"
            )) + " |"
        )
    lines.extend(["", "Unbound callsites:"])
    lines.extend(f"- `{item}`" for item in unbound) if unbound else lines.append("- None.")
    lines.extend(["", "Result: " + ("PASS" if not unbound else "FAIL"), ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail when the checked-in inventory is stale")
    args = parser.parse_args()
    rows, unbound = scan_inventory()
    rendered = render_inventory(rows, unbound)
    if args.check:
        try:
            current = OUTPUT.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"FAIL: inventory is unavailable: {exc}")
            return 2
        if current != rendered:
            print(f"FAIL: {OUTPUT.relative_to(REPOSITORY_ROOT)} is stale; regenerate without --check")
            return 1
        print(f"PASS: {len(rows)} callsites, {len(unbound)} unbound; inventory matches registry {REGISTRY.digest}")
    else:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(rendered, encoding="utf-8", newline="\n")
        print(f"Wrote {OUTPUT.relative_to(REPOSITORY_ROOT)}: {len(rows)} callsites, {len(unbound)} unbound")
    return 1 if unbound else 0


if __name__ == "__main__":
    raise SystemExit(main())
