"""
test_no_snapshot_leakage.py
Verifies that the BAGO-3.5-CLEAN-CORE-RC1 codebase does NOT contain hardcoded
values that came from the 2026-05 snapshot audit.

These are claims/concrete numbers that were true in the snapshot but are
historical now and must never be re-introduced as if they were current.

Test categories:
  1. Concrete numbers from the snapshot (counts, sizes, hashes, dates)
  2. Concrete instance IDs / URLs / usernames
  3. Concrete file paths from snapshot-specific projects (BIANCA assets, etc.)
  4. Concrete commit SHAs and dates from the snapshot
  5. Concrete health/score values that were point-in-time

Run: python3 tests/test_no_snapshot_leakage.py
Exit 0 = clean, Exit 1 = leaked snapshot value detected.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# Resolve repo root assuming this file is in tests/
TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent

# Patterns that must NOT appear anywhere in tracked text files of the repo.
# Each entry: (pattern, human-readable reason)
FORBIDDEN_PATTERNS: list[tuple[str, str]] = [
    # --- 1. Concrete counts (regenerated each release) ---
    (r"\b177\b\s*(?:tools|herramientas)", "snapshot count 177 tools"),
    (r"\b80\b\s*(?:commands|comandos)\b", "snapshot count 80 commands"),
    (r"\b51\s+activos?\s*\+\s*29\s+deprecated", "snapshot 51+29 split"),
    (r"\b14\s+roles?\b", "snapshot 14 roles (use REGISTRY/manifest, not literal)"),
    (r"6\s*capas\s*taxonómicas", "snapshot 6-layer taxonomy (RC1 uses 5 layers)"),
    (r"\bejecución\s*\|\s*calidad\s*\|\s*salud\s*\|\s*analítica\s*\|\s*visual\s*\|\s*avanzado",
     "snapshot layer enum"),

    # --- 2. Concrete instance IDs / URLs / usernames ---
    (r"7107610433", "snapshot WhatsApp green-api instance id"),
    (r"bagofk7m8m@deltajohnsons\.com", "snapshot green-api account email"),
    (r"@bago_amtec_bot", "snapshot Telegram bot username"),
    (r"unmuddled-ashly-endoparasitic\.ngrok-free\.dev", "snapshot miniapp ngrok URL"),
    (r"7107\.api\.greenapi\.com", "snapshot green-api base URL"),
    (r"\+34684798513", "snapshot phone number"),

    # --- 3. Snapshot-specific asset paths (BIANCA) ---
    (r"char_bianca_walk_6x8\.png", "snapshot BIANCA sprite filename"),
    (r"isoRenderer\.render\(\)", "snapshot BIANCA buggy code reference"),
    (r"dos juegos encima", "snapshot BIANCA bug label"),

    # --- 4. Snapshot commit SHAs and dates ---
    (r"\be3cba7b\b", "snapshot commit SHA (banner RGB)"),
    (r"\ba8ba572\b", "snapshot commit SHA (v3.3.0)"),
    (r"\b2564428\b", "snapshot commit SHA (health reconcile)"),
    (r"\b65126b1\b", "snapshot commit SHA (v3.1 autonomy)"),
    (r"\b2026-05-05T20:27:55", "snapshot WhatsApp daemon activation"),
    (r"\b2026-05-05T20:36:41", "snapshot Telegram activation"),
    (r"\b2026-05-05T19:14:21", "snapshot sprite generation"),

    # --- 5. Point-in-time health/score values ---
    (r"health_score[\"']?\s*[:=]\s*[\"']?75", "snapshot health_score 75 (KO legacy ref)"),
    (r"health[\"']?\s*[:=]\s*[\"']?100/100", "snapshot last_validation 100/100 literal"),
    (r"ImageStudio/_internal/fastapi/applications\.py", "snapshot KO location"),

    # --- 6. Snapshot version drift (RC1 is 3.5.0-rc1) ---
    (r"\bbago_version[\"']?\s*[:=]\s*[\"']3\.3\.0[\"']", "snapshot pack.json 3.3.0"),
    (r"\bversion\s*=\s*[\"']3\.2\.0[\"']", "snapshot pyproject 3.2.0"),
    (r"\bv3\.3\.0-structural\b", "snapshot version label"),
    (r"\bv3\.2-kernel\b", "snapshot QUICKSTART version label"),

    # --- 7. Snapshot-specific project claims ---
    (r"sprints?\s+289-290", "snapshot BIANCA sprint range"),
    (r"sprints?\s+288-292", "snapshot BIANCA sprint range"),
    (r"\bPID\s+32932\b", "snapshot miniapp server PID"),

    # --- 8. Mac paths that never apply to RC1 ---
    (r"/Volumes/Warehouse", "snapshot macOS warehouse path"),
    (r"/Volumes/bago_fw", "snapshot macOS bago_fw path"),
    (r"/SistemaSSD/", "snapshot macOS SistemaSSD path"),
    (r"~/bago-framework/", "snapshot macOS home path"),
]


def is_text_file(path: Path) -> bool:
    """Skip binaries, archives, release-assets, evidence, examples."""
    if path.name == "test_no_snapshot_leakage.py":
        return False
    skip_dirs = {
        ".git", "__pycache__", "node_modules", "dist", "release-assets",
        "evidence", "examples", ".pytest_cache", "__pycache__",
        "BAGO_LAST.zip", ".bago/state", ".bago/state.example",
        ".bago/core", ".bago/tools", ".bago/agents", ".bago/roles",
        ".bago/workflows", ".bago/templates", ".bago/prompts",
        ".bago/mcp", ".bago/extensions",
        ".bago/knowledge/topics",
        "archive",  # 2026-Q2 cleanup: archive/ holds historical artifacts
    }
    if any(part in skip_dirs for part in path.parts):
        return False
    # Only scan text extensions
    text_exts = {
        ".py", ".md", ".json", ".yaml", ".yml", ".toml", ".txt", ".cfg",
        ".ini", ".sh", ".ps1", ".cmd", ".html", ".css", ".js", ".mjs",
        ".ts", ".tsx", ".lock", ".gitignore", ".gitattributes",
    }
    return path.suffix.lower() in text_exts or path.name in {
        "AGENTS.md", "BOOTSTRAP.md", "README.md", "HANDOFF.md",
        "MANIFEST.in", "LICENSE", ".gitignore", ".gitattributes",
    }


def main() -> int:
    if not REPO_ROOT.exists():
        print(f"❌ Repo root not found: {REPO_ROOT}")
        return 2

    print(f"Scanning: {REPO_ROOT}")
    print(f"Patterns: {len(FORBIDDEN_PATTERNS)}")

    violations: list[tuple[Path, int, str, str]] = []

    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if not is_text_file(path):
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for pattern, reason in FORBIDDEN_PATTERNS:
            for match in re.finditer(pattern, content):
                # Find line number
                line_no = content[: match.start()].count("\n") + 1
                violations.append((path, line_no, pattern, reason))

    if violations:
        print(f"\n❌ Snapshot leakage detected: {len(violations)} violation(s)\n")
        for path, line_no, pattern, reason in violations[:30]:
            rel = path.relative_to(REPO_ROOT)
            print(f"  {rel}:{line_no}  [{reason}]")
            print(f"    pattern: {pattern}")
        if len(violations) > 30:
            print(f"  ... and {len(violations) - 30} more")
        print("\nThese values were true in the 2026-05-05/07 snapshot")
        print("but are historical. They must not reappear as if current.")
        return 1

    print("\n✅ No snapshot leakage detected. Clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
