import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BAGO_DIR = ROOT / ".bago"
TOOLS = BAGO_DIR / "tools"

def run(cmd: list[str], timeout: int = 30) -> dict:
    try:
        r = subprocess.run(
            [sys.executable] + cmd,
            capture_output=True, text=True, timeout=timeout, cwd=str(ROOT)
        )
        return {"rc": r.returncode, "stdout": r.stdout, "stderr": r.stderr, "ok": r.returncode == 0}
    except subprocess.TimeoutExpired:
        return {"rc": -1, "stdout": "", "stderr": "TIMEOUT", "ok": False, "timeout": True}
    except Exception as e:
        return {"rc": -2, "stdout": "", "stderr": str(e), "ok": False}

def sense_all() -> dict:
    # version truth
    vt = run([str(TOOLS / "version_truth.py"), "check"])
    # validate
    val = run([str(TOOLS / "validate.py")])
    # install contract
    inst = run([str(TOOLS / "install_contract.py"), "validate"])
    # audit
    aud = run([str(TOOLS / "audit" / "_v2.py")], timeout=30)
    # git dirty
    git = run([str(TOOLS / "git_dirty_guard.py"), "--json"], timeout=10)
    # encoding
    enc = run([str(TOOLS / "terminal_encoding.py")], timeout=5)
    # tests (quick subset)
    test = run(["-m", "pytest", "tests/test_runtime_state.py", "tests/test_registry_contract.py", "-q"], timeout=60)

    return {
        "version_truth": vt["ok"],
        "validate": val["ok"],
        "install_contract": inst["ok"],
        "audit": aud["ok"],
        "git_dirty": not json.loads(git["stdout"]).get("dirty", True) if git["ok"] else False,
        "encoding": enc["ok"],
        "tests": test["ok"],
        "details": {
            "version_truth_rc": vt["rc"],
            "validate_rc": val["rc"],
            "audit_rc": aud["rc"],
            "test_rc": test["rc"],
        }
    }

def main():
    data = sense_all()
    ok = all([
        data["version_truth"],
        data["validate"],
        data["install_contract"],
        data["audit"],
        data["encoding"],
        data["tests"],
    ])
    if "--json" in sys.argv:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print("GO integrity" if ok else "KO integrity")
        for k, v in data.items():
            if k != "details":
                status = "GO" if v else "KO"
                print(f"  {status} {k}")
    return 0 if ok else 1



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