import json, re, sys
from pathlib import Path

PACK_JSON = Path(__file__).resolve().parents[2] / ".bago" / "pack.json"

CHECK_FILES = {
    "pyproject.toml": r'^version\s*=\s*"([^"]+)"',
    "bago_core/__init__.py": r'__version__\s*=\s*"([^"]+)"',
    "README.md": r'(?i)version[\s:]*([0-9]+\.[0-9]+\.[0-9]+[^\s]*)',
    "INSTALL.md": r'(?i)version[\s:]*([0-9]+\.[0-9]+\.[0-9]+[^\s]*)',
    "QUICKSTART.md": r'(?i)version[\s:]*([0-9]+\.[0-9]+\.[0-9]+[^\s]*)',
    ".bago/templates/global_state.clean.json": r'"bago_version"\s*:\s*"([^"]+)"',
    ".bago/state.example/global_state.json": r'"bago_version"\s*:\s*"([^"]+)"',
    "install.sh": r'(?i)version[=: ]*([0-9]+\.[0-9]+\.[0-9]+[^\s]*)',
    "install.ps1": r'(?i)version[=: ]*([0-9]+\.[0-9]+\.[0-9]+[^\s]*)',
    "install-bago.sh": r'(?i)version[=: ]*([0-9]+\.[0-9]+\.[0-9]+[^\s]*)',
    "install-bago.cmd": r'(?i)version[=: ]*([0-9]+\.[0-9]+\.[0-9]+[^\s]*)',
}

def get_source_version():
    d = json.loads(PACK_JSON.read_text(encoding="utf-8"))
    return d.get("version", "unknown")

def check_all(root):
    truth = get_source_version()
    mismatches = []
    found = {}
    for rel_path, pattern in CHECK_FILES.items():
        p = root / rel_path
        if not p.exists():
            mismatches.append({"file": rel_path, "expected": truth, "found": "MISSING", "status": "MISSING"})
            continue
        text = p.read_text(encoding="utf-8")
        m = re.search(pattern, text, re.MULTILINE)
        ver = m.group(1) if m else "NOT_FOUND"
        found[rel_path] = ver
        if ver != truth:
            mismatches.append({"file": rel_path, "expected": truth, "found": ver, "status": "MISMATCH"})
    return {"truth": truth, "mismatches": mismatches, "found": found, "go": len(mismatches) == 0}

def sync_all(root, target):
    pack = root / ".bago/pack.json"
    d = json.loads(pack.read_text(encoding="utf-8"))
    d["version"] = target
    pack.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    updates = []
    for rel_path, pattern in CHECK_FILES.items():
        p = root / rel_path
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        def repl(m):
            return m.group(0).replace(m.group(1), target)
        new_text, count = re.subn(pattern, repl, text, count=1, flags=re.MULTILINE)
        if count:
            p.write_text(new_text, encoding="utf-8")
            updates.append(rel_path)
    return updates

def main():
    args = sys.argv[1:]
    root = Path(__file__).resolve().parents[2]
    if not args or args[0] == "check":
        result = check_all(root)
        if result["go"]:
            print("GO version_truth")
            print(f"  truth = {result['truth']}")
        else:
            print("KO version_truth")
            for m in result["mismatches"]:
                print(f"  {m['file']}: expected {m['expected']} found {m['found']}")
        return 0 if result["go"] else 1
    if args[0] == "sync" and len(args) >= 2:
        target = args[1]
        updated = sync_all(root, target)
        print(f"GO version sync -> {target}")
        print(f"  updated {len(updated)} files")
        for u in updated:
            print(f"    + {u}")
        return 0
    if args[0] == "audit" and "--json" in args:
        import json as _json
        result = check_all(root)
        print(_json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["go"] else 1
    print("Usage: version_truth.py [check|sync <version>|audit --json]")
    return 1

if __name__ == "__main__":
    sys.exit(main())