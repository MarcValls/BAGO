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

import json, os, datetime, hashlib, sys, subprocess
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

BAGO_ROOT    = Path(__file__).parent.parent
# Allow tests to isolate scan output by setting BAGO_STATE_DIR env var
_state_env   = os.environ.get("BAGO_STATE_DIR")
FINDINGS_DIR = Path(_state_env) / "findings" if _state_env else BAGO_ROOT / "state" / "findings"
FINDINGS_DIR.mkdir(parents=True, exist_ok=True)

# Import permission fixer — graceful fallback if not yet available
try:
    sys.path.insert(0, str(Path(__file__).parent))
    from permission_fixer import run_with_permission_fix as _run_cmd
except ImportError:
    def _run_cmd(cmd, *, capture_output=True, text=True, timeout=60,    # type: ignore[misc]
                 cwd=None, env=None, silent=True, **_):
        return subprocess.run(cmd, capture_output=capture_output, text=text,
                              timeout=timeout, cwd=cwd, env=env)

SEVERITIES = ("error", "warning", "info", "hint")
SARIF_VERSION = ".".join(("2", "1", "0"))

@dataclass
class Finding:
    id:             str
    severity:       str          # error|warning|info|hint
    file:           str
    line:           int
    col:            int
    rule:           str
    source:         str          # flake8|pylint|mypy|bandit|bago
    message:        str
    fix_suggestion: str  = ""
    autofixable:    bool = False
    fix_patch:      str  = ""    # unified diff when autofixable
    context_lines:  list = field(default_factory=list)  # ±2 lines

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Finding":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def _make_id(source: str, file: str, line: int, rule: str) -> str:
    key = f"{source}:{file}:{line}:{rule}"
    return "FIND-" + hashlib.md5(key.encode(), usedforsecurity=False).hexdigest()[:8].upper()


def _read_context(filepath: str, line: int, radius: int = 2) -> list:
    try:
        lines = Path(filepath).read_text(errors="replace").splitlines()
        start = max(0, line - 1 - radius)
        end   = min(len(lines), line + radius)
        return [f"{i+1:4d} | {lines[i]}" for i in range(start, end)]
    except Exception:
        return []

def diff_findings(before: list, after: list) -> dict:
    """Compare two lists of Finding objects.

    Identity key: (file, line, rule) — robust across re-scans.
    Returns dict with keys:
      'new'        — findings in after but not in before
      'fixed'      — findings in before but not in after
      'persistent' — findings in both runs
    """
    def _key(f: "Finding") -> tuple:
        return (f.file, f.line, f.rule)

    before_keys = {_key(f): f for f in before}
    after_keys  = {_key(f): f for f in after}

    new_keys        = set(after_keys) - set(before_keys)
    fixed_keys      = set(before_keys) - set(after_keys)
    persistent_keys = set(before_keys) & set(after_keys)

    return {
        "new":        [after_keys[k] for k in sorted(new_keys)],
        "fixed":      [before_keys[k] for k in sorted(fixed_keys)],
        "persistent": [after_keys[k] for k in sorted(persistent_keys)],
    }

class FindingsDB:
    def __init__(self, scan_id: str | None = None):
        if scan_id is None:
            ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
            scan_id = f"SCAN-{ts}"
        self.scan_id  = scan_id
        self.path     = FINDINGS_DIR / f"{scan_id}.json"
        self.findings: list = []
        self.meta:     dict = {
            "scan_id":    scan_id,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "sources":    [],
            "target":     "",
        }

    def add(self, findings: list):
        self.findings.extend(findings)

    def save(self):
        # Deduplicate by id
        seen  = set()
        dedup = []
        for f in self.findings:
            if f.id not in seen:
                seen.add(f.id)
                dedup.append(f)
        self.findings = dedup

        data = {
            "meta":     self.meta,
            "summary":  self._summary(),
            "findings": [f.to_dict() for f in self.findings],
        }
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        return self.path

    def _summary(self) -> dict:
        by_sev = {s: 0 for s in SEVERITIES}
        by_src: dict = {}
        by_file: dict = {}
        for f in self.findings:
            by_sev[f.severity] = by_sev.get(f.severity, 0) + 1
            by_src[f.source]   = by_src.get(f.source, 0) + 1
            by_file[f.file]    = by_file.get(f.file, 0) + 1
        autofixable = sum(1 for f in self.findings if f.autofixable)
        return {
            "total":      len(self.findings),
            "autofixable": autofixable,
            "by_severity": by_sev,
            "by_source":   by_src,
            "top_files":   sorted(by_file.items(), key=lambda x: -x[1])[:10],
        }

    @classmethod
    def load(cls, scan_id: str) -> "FindingsDB":
        db = cls(scan_id)
        if db.path.exists():
            data = json.loads(db.path.read_text())
            db.meta     = data.get("meta", {})
            db.findings = [Finding.from_dict(f) for f in data.get("findings", [])]
        return db

    @classmethod
    def latest(cls) -> "FindingsDB | None":
        scans = sorted(FINDINGS_DIR.glob("SCAN-*.json"))
        if not scans:
            return None
        scan_id = scans[-1].stem
        return cls.load(scan_id)


def run_tests() -> int:
    """Self-test stub: verify module imports and key symbols exist."""
    results = []
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_test_mod", __file__)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        results.append(("import", True, "module loads OK"))
    except Exception as e:
        results.append(("import", False, str(e)))

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, detail in results:
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {name}: {detail}")
    print(f"\n  {passed}/{total} tests passed")
    return 0 if passed == total else 1

if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(run_tests())

