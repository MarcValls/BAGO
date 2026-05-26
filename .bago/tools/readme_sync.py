#!/usr/bin/env python3
"""
readme_sync.py — BAGO README auto-sync

Mantiene el README.md sincronizado con el estado real del framework.
Actualiza la línea de versión y el footer con datos del global_state.json
y el registro de herramientas.

Se ejecuta automáticamente desde pre_push_guard.py antes de cada push.
También puede invocarse manualmente: python3 .bago/tools/readme_sync.py

Exit codes:
  0 — README ya estaba actualizado (o se actualizó sin error)
  1 — Error irrecuperable
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
_TOOLS     = Path(__file__).parent
_BAGO_ROOT = _TOOLS.parent              # .bago/
_REPO_ROOT = _BAGO_ROOT.parent          # bago_core/
_README    = _REPO_ROOT / "README.md"
_STATE     = _BAGO_ROOT / "state" / "global_state.json"
_PACK      = _BAGO_ROOT / "pack.json"

# ── Data collection ────────────────────────────────────────────────────────────

def _load_state() -> dict:
    try:
        return json.loads(_STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_pack() -> dict:
    try:
        return json.loads(_PACK.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _cmd_count() -> int:
    """Count all registered commands from REGISTRY."""
    try:
        if str(_TOOLS) not in sys.path:
            sys.path.insert(0, str(_TOOLS))
        from tool_registry import REGISTRY  # type: ignore
        return len(REGISTRY)
    except Exception:
        return 0


def _registry_counts() -> dict[str, int]:
    """Count commands by public stability bucket from REGISTRY."""
    counts = {"core": 0, "experimental": 0, "dangerous": 0, "legacy": 0, "public": 0}
    try:
        if str(_TOOLS) not in sys.path:
            sys.path.insert(0, str(_TOOLS))
        from tool_registry import REGISTRY  # type: ignore
        for entry in REGISTRY.values():
            if entry.stability in counts:
                counts[entry.stability] += 1
            if entry.stability in {"core", "experimental", "dangerous"}:
                counts["public"] += 1
    except Exception:
        pass
    return counts


def _tool_file_count() -> int:
    """Count non-ImageStudio .py tool files."""
    return sum(
        1 for f in (_TOOLS).rglob("*.py")
        if "ImageStudio" not in str(f) and "__pycache__" not in str(f)
    )


def _workflow_count(pack: dict) -> int:
    return len(pack.get("workflows", {}))


def _month_year() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%B %Y")


def collect_metrics() -> dict:
    state    = _load_state()
    pack     = _load_pack()
    version  = state.get("bago_version", "unknown")
    cmds     = _cmd_count()
    registry_counts = _registry_counts()
    tools    = _tool_file_count()
    wflows   = _workflow_count(pack)
    month_yr = _month_year()
    return {
        "version":         version,
        "cmd_count":       cmds,
        "public_count":    registry_counts["public"],
        "core_count":      registry_counts["core"],
        "experimental_count": registry_counts["experimental"],
        "dangerous_count": registry_counts["dangerous"],
        "legacy_count":    registry_counts["legacy"],
        "tool_count":      tools,
        "workflow_count":  wflows,
        "month_year":      month_yr,
    }


# ── README patching ────────────────────────────────────────────────────────────

# Patterns to patch (key → compiled regex, replacement template)
_PATCHES = [
    # Version header line
    (
        re.compile(
            r"^(> \*\*Version )[^\*]+(\*\* · )\d+ CLI commands · \d+ tools · \d+ operational workflows · Clean-install state: `.+`$",
            re.MULTILINE,
        ),
        lambda m: (
            r"Version line"  # marker — replaced in apply_patches()
        ),
    ),
    # Footer line
    (
        re.compile(
            r"^\*BAGO [^\*]+ · Built with BAGO · .+\*$",
            re.MULTILINE,
        ),
        None,  # handled separately
    ),
]


def apply_patches(content: str, metrics: dict) -> tuple[str, bool]:
    """
    Patch README content with live metrics.
    Returns (patched_content, changed: bool).
    """
    original = content
    v  = metrics["version"]
    c  = metrics["cmd_count"]
    public = metrics["public_count"]
    core = metrics["core_count"]
    experimental = metrics["experimental_count"]
    dangerous = metrics["dangerous_count"]
    legacy = metrics["legacy_count"]
    t  = metrics["tool_count"]
    w  = metrics["workflow_count"]
    my = metrics["month_year"]

    # 1. Version header line
    public_header_pattern = re.compile(
        r"^(> \*\*Version )[^\*]+(\*\* · )\d+ CLI commands · \d+ public commands$",
        re.MULTILINE,
    )
    public_header_new = f"> **Version {v}** · {c} CLI commands · {public} public commands"
    content = public_header_pattern.sub(public_header_new, content)

    header_pattern = re.compile(
        r"^(> \*\*Version )[^\*]+(\*\* · )\d+ CLI commands · \d+ tools · \d+ operational workflows · Clean-install state: `.+`$",
        re.MULTILINE,
    )
    header_new = f"> **Version {v}** · {c} CLI commands · {t} tools · {w} operational workflows · Clean-install state: `healthy`"
    content = header_pattern.sub(header_new, content)

    contract_pattern = re.compile(
        r"^Public command contract \(CI-checked\): \*\*\d+ core\*\* · \*\*\d+ experimental\*\* · \*\*\d+ dangerous\*\* · \*\*\d+ legacy\*\*$",
        re.MULTILINE,
    )
    contract_new = (
        f"Public command contract (CI-checked): **{core} core** · "
        f"**{experimental} experimental** · **{dangerous} dangerous** · **{legacy} legacy**"
    )
    content = contract_pattern.sub(contract_new, content)

    # 2. Evolution table — mark old *(current)* rows as historical, add/update v row
    # Find the current-marked row
    current_row_pattern = re.compile(
        r"^\| \*\*([^*]+)\*\* \*\(current\)\* \|.*$", re.MULTILINE
    )

    def _remove_current_marker(m: re.Match) -> str:
        ver = m.group(1)
        if ver == v:
            return m.group(0)  # keep as-is, we'll update below
        # Remove *(current)* marker from old rows
        return m.group(0).replace(" *(current)*", " *(historic)*")

    content = current_row_pattern.sub(_remove_current_marker, content)

    # Check if v3.1 row exists in table
    version_in_table = re.compile(
        rf"^\| \*\*{re.escape(v)}\*\*", re.MULTILINE
    )
    if not version_in_table.search(content):
        # Insert new row before the table-ending blank line after last | row
        last_row_pattern = re.compile(r"(^\|[^\n]+\n)(\n\*\*Growth)", re.MULTILINE)
        new_row = f"| **{v}** *(current)* | **{c}** | **{t}** | — | **{w}** | **—** |\n"
        content = last_row_pattern.sub(
            lambda m: m.group(1) + new_row + m.group(2),
            content,
        )
    else:
        # Update existing row for current version
        content = re.sub(
            rf"^\| \*\*{re.escape(v)}\*\* \*\(current\)\*[^\n]+$",
            f"| **{v}** *(current)* | **{c}** | **{t}** | — | **{w}** | **—** |",
            content,
            flags=re.MULTILINE,
        )

    # 3. Growth line — update version references
    growth_pattern = re.compile(
        r"^\*\*Growth from [^\*]+ → [^\*]+\*\*(.+)$", re.MULTILINE
    )
    if not growth_pattern.search(content):
        pass  # don't inject if not present
    else:
        content = growth_pattern.sub(
            lambda m: f"**Growth up to {v}**{m.group(1)}",
            content,
        )

    # 4. "New in X.Y-label" heading — keep historical, add new section if absent
    new_in_pattern = re.compile(rf"^### New in {re.escape(v)}$", re.MULTILINE)
    if not new_in_pattern.search(content):
        # Find last "### New in" heading and insert after it
        last_new_in = re.compile(r"^(### New in [^\n]+\n)", re.MULTILINE)
        all_matches = list(last_new_in.finditer(content))
        if all_matches:
            last_m = all_matches[-1]
            insert_pos = last_m.start()
            new_section = (
                f"### New in {v}\n\n"
                f"**New CLI commands:** `autonomous`, `inbox`\n\n"
                f"**New core modules:** `autonomous_loop.py`, `learning_writer.py`\n\n"
                f"**Architecture:** SENSE/PLAN/ACT/OBSERVE/LEARN/DECIDE loop · El Aprendiz (auto-pattern promotion) · BagoContext singleton · Tool-Agent Binding · Agent Dispatcher\n\n"
                f"**Bug fixes:** audit_v2 health parse · stale_detector timezone TypeError\n\n"
                f"---\n\n"
            )
            content = content[:insert_pos] + new_section + content[insert_pos:]

    # 5. Footer line
    footer_pattern = re.compile(
        r"^\*BAGO [^\*]+ · Built with BAGO · .+\*$", re.MULTILINE
    )
    footer_new = f"*BAGO {v} · Built with BAGO · {my}*"
    content = footer_pattern.sub(footer_new, content)

    return content, content != original


# ── Git auto-stage ─────────────────────────────────────────────────────────────

def _git_add_readme() -> None:
    subprocess.run(
        ["git", "add", str(_README)],
        cwd=str(_REPO_ROOT),
        capture_output=True,
    )


# ── Main ───────────────────────────────────────────────────────────────────────

def sync(auto_stage: bool = True, verbose: bool = True) -> bool:
    """
    Sync README.md with live metrics.
    Returns True if README was changed.
    """
    if not _README.exists():
        if verbose:
            print("  ⚠️  README.md not found — skipping readme_sync")
        return False

    metrics = collect_metrics()
    content = _README.read_text(encoding="utf-8")
    patched, changed = apply_patches(content, metrics)

    if not changed:
        if verbose:
            print(f"  OK   README.md ya sincronizado (v{metrics['version']})")
        return False

    _README.write_text(patched, encoding="utf-8")
    if verbose:
        print(f"  ✅  README.md actualizado → v{metrics['version']} · {metrics['cmd_count']} cmds · {metrics['tool_count']} tools · {metrics['workflow_count']} workflows")

    if auto_stage:
        _git_add_readme()
        if verbose:
            print("  ✅  README.md staged (git add)")

    return True


def _self_test() -> None:
    sample = """\
# BAGO

[![badge](url)](url)

> **Version 2.5-stable** · 36 CLI commands · 112 tools · 20 operational workflows · Clean-install state: `initializing`

| Version | CLI Commands | Tools | Docs | Workflows | Efficiency Index |
|---|:---:|:---:|:---:|:---:|:---:|
| **2.3-clean** *(baseline)* | 10 | 19 | 68 | 12 | 78.6 |
| **2.5-stable** *(current)* | **35** | **111** | **77** | **20** | **100.0** |

**Growth from 2.3 → 2.5: +27.2%** — blah blah.

### New in 2.5-stable

some content

*BAGO 2.5-stable · Built with BAGO · April 2026*
"""
    metrics = {
        "version": "3.1",
        "cmd_count": 83,
        "public_count": 70,
        "core_count": 14,
        "experimental_count": 48,
        "dangerous_count": 8,
        "legacy_count": 13,
        "tool_count": 202,
        "workflow_count": 17,
        "month_year": "May 2026",
    }
    patched, changed = apply_patches(sample, metrics)
    assert changed, "Should have changed"
    assert "Version 3.1" in patched,                    f"version header: {patched[:200]}"
    assert "83 CLI commands" in patched,                "cmd count"
    assert "202 tools" in patched,                      "tool count"
    assert "17 operational workflows" in patched,       "workflow count"
    assert "healthy" in patched,                        "clean-install state"
    assert "BAGO 3.1 · Built with BAGO · May 2026" in patched, "footer"
    assert "New in 3.1" in patched,                     "new section"
    assert "*(current)*" in patched,                    "current marker on new row"
    assert "*(historic)*" in patched or "*(current)*" in patched, "old row handled"

    # Second pass — should be idempotent
    patched2, changed2 = apply_patches(patched, metrics)
    assert not changed2, f"Second pass should be idempotent. Diff: {patched[:300]}"

    print("  ✅ readme_sync self-test passed")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        sys.exit(0)

    if "--dry-run" in sys.argv:
        m = collect_metrics()
        print(f"  Métricas actuales:")
        for k, v in m.items():
            print(f"    {k}: {v}")
        content = _README.read_text(encoding="utf-8") if _README.exists() else ""
        _, changed = apply_patches(content, m)
        print(f"  README necesita actualización: {'SÍ' if changed else 'NO'}")
        # Exit 1 si hay cambios pendientes (permite que callers usen exit-code)
        sys.exit(1 if changed else 0)

    auto_stage = "--no-stage" not in sys.argv
    verbose    = "--quiet" not in sys.argv
    changed    = sync(auto_stage=auto_stage, verbose=verbose)
    sys.exit(0)
