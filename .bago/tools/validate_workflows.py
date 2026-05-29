"""Validaciones auxiliares de workflows."""

from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso


def check_w10_desync(sprint_status: dict) -> list[str]:
    warnings: list[str] = []
    active_wf = sprint_status.get("active_workflow")
    last = sprint_status.get("last_completed_workflow") or {}
    last_code = last.get("code") if isinstance(last, dict) else None

    if (
        active_wf is not None
        and last_code is not None
        and active_wf == last_code
    ):
        title = last.get("title", "")
        ended = last.get("ended", "")
        warnings.append(
            f"WARN-W010: active_workflow='{active_wf}' coincide con "
            f"last_completed_workflow='{last_code}' ('{title}', ended={ended}) "
            "— el flujo parece completado pero active_workflow no fue limpiado"
        )
    return warnings


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

