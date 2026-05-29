import json, subprocess, sys
from pathlib import Path

def get_dirty(root: Path) -> dict:
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=str(root), timeout=10
        )
        lines = [l for l in r.stdout.splitlines() if l.strip()]
        modified = [l[3:].strip() for l in lines if l.startswith(" M") or l.startswith("M ") or l.startswith("MM")]
        untracked = [l[3:].strip() for l in lines if l.startswith("??")]
        return {
            "dirty": len(lines) > 0,
            "modified": modified,
            "untracked": untracked,
            "risk": "HIGH" if modified else ("MEDIUM" if untracked else "NONE"),
        }
    except Exception as e:
        return {"dirty": False, "modified": [], "untracked": [], "risk": "UNKNOWN", "error": str(e)}

def main():
    root = Path(__file__).resolve().parents[2]
    data = get_dirty(root)
    if "--json" in sys.argv:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print("GO git" if not data["dirty"] else "KO git dirty")
        if data["dirty"]:
            print(f"  modified: {len(data['modified'])}, untracked: {len(data['untracked'])}")
    return 0 if not data["dirty"] else 1



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
    sys.exit(main())