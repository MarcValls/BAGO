"""Registry contract parity tests (README ↔ tool_registry)."""
from __future__ import annotations

import re
from pathlib import Path

from registry_ast_contract import analyze_registry_literal
from tool_registry import REGISTRY

REPO_ROOT = Path(__file__).resolve().parent.parent
README = REPO_ROOT / "README.md"
REGISTRY_FILE = REPO_ROOT / ".bago" / "tools" / "tool_registry.py"


def _readme_section(title_fragment: str) -> str:
    text = README.read_text(encoding="utf-8")
    headers = list(re.finditer(r"^##\s+\d+\.\s+(.+)$", text, flags=re.MULTILINE))
    for idx, header in enumerate(headers):
        title = header.group(1)
        if title_fragment.lower() not in title.lower():
            continue
        start = header.end()
        end = headers[idx + 1].start() if idx + 1 < len(headers) else len(text)
        return text[start:end]
    raise AssertionError(f"README section not found: {title_fragment!r}")


def _commands_from_table(section: str) -> set[str]:
    cmds: set[str] = set()
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or "---" in stripped:
            continue
        m = re.search(r"`([a-z0-9_-]+)`", stripped)
        if m:
            cmds.add(m.group(1))
    return cmds


def _commands_from_inline_list(section: str) -> set[str]:
    return set(re.findall(r"`([a-z0-9_-]+)`", section))


def _registry_cmds_by_stability(stability: str) -> set[str]:
    return {cmd for cmd, entry in REGISTRY.items() if entry.stability == stability}


def _registry_legacy_cmds() -> set[str]:
    return {cmd for cmd, entry in REGISTRY.items() if entry.deprecated}


def test_registry_literal_has_no_duplicate_keys_ast():
    """Detect duplicate dict keys in REGISTRY literal before Python overwrites them."""
    report = analyze_registry_literal(REGISTRY_FILE)
    assert not report.non_string_key_lines, (
        f"Non-string REGISTRY literal keys found at lines: {report.non_string_key_lines}"
    )
    assert not report.duplicate_keys, f"Duplicate REGISTRY literal keys found: {report.duplicate_keys}"


def test_readme_core_commands_match_registry():
    section = _readme_section("Core commands")
    readme_core = set(re.findall(r"`bago\s+([a-z0-9_-]+)`", section))
    registry_core = _registry_cmds_by_stability("core")
    assert readme_core == registry_core, (
        f"README core mismatch: extra={sorted(readme_core - registry_core)}, "
        f"missing={sorted(registry_core - readme_core)}"
    )


def test_readme_dangerous_commands_match_registry():
    section = _readme_section("Dangerous commands")
    readme_dangerous = _commands_from_table(section)
    registry_dangerous = _registry_cmds_by_stability("dangerous")
    assert readme_dangerous == registry_dangerous, (
        f"README dangerous mismatch: extra={sorted(readme_dangerous - registry_dangerous)}, "
        f"missing={sorted(registry_dangerous - readme_dangerous)}"
    )


def test_readme_legacy_commands_match_registry():
    section = _readme_section("Legacy commands")
    readme_legacy = _commands_from_inline_list(section)
    registry_legacy = _registry_legacy_cmds()
    assert readme_legacy == registry_legacy, (
        f"README legacy mismatch: extra={sorted(readme_legacy - registry_legacy)}, "
        f"missing={sorted(registry_legacy - readme_legacy)}"
    )
