import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BAGO_DIR = ROOT / ".bago"
TEMPLATES = BAGO_DIR / "templates"
STATE_DIR = BAGO_DIR / "state"
CLEAN_STATE = TEMPLATES / "global_state.clean.json"

def bootstrap_state() -> int:
    if not CLEAN_STATE.exists():
        print("KO install_contract")
        print(f"  missing template: {CLEAN_STATE}")
        return 1
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    for sub in ("sessions", "changes", "evidences", "reports", "config"):
        (STATE_DIR / sub).mkdir(parents=True, exist_ok=True)
    target = STATE_DIR / "global_state.json"
    # copy and inject runtime values
    data = json.loads(CLEAN_STATE.read_text(encoding="utf-8"))
    import datetime, uuid
    data["install_id"] = str(uuid.uuid4())[:8]
    data["created_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    data["updated_at"] = data["created_at"]
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("GO install_contract")
    print(f"  created {target}")
    print(f"  install_id = {data['install_id']}")
    return 0

def validate_install() -> int:
    missing = []
    if not (STATE_DIR / "global_state.json").exists():
        missing.append(".bago/state/global_state.json")
    for sub in ("sessions", "changes", "evidences", "reports", "config"):
        if not (STATE_DIR / sub).exists():
            missing.append(f".bago/state/{sub}/")
    if missing:
        print("KO install_contract")
        for m in missing:
            print(f"  missing: {m}")
        print("  run: python3 bago bootstrap-state")
        return 1
    print("GO install_contract")
    return 0

def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] == "validate":
        return validate_install()
    if args[0] == "bootstrap":
        return bootstrap_state()
    print("Usage: install_contract.py [validate|bootstrap]")
    return 1



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