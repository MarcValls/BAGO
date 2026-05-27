"""Helpers de compatibilidad para validar sesiones BAGO."""

from __future__ import annotations

from pathlib import Path


def is_cli_invocation_log(data: dict) -> bool:
    """session_logger.py legacy records are not protocol sessions."""
    return (
        {"cmd", "module", "args", "start_time"}.issubset(data.keys())
        and "selected_workflow" not in data
        and "roles_activated" not in data
    )


def quarantine_cli_invocation_logs(sessions_dir: Path, root: Path, loader) -> list[str]:
    moved: list[str] = []
    if not sessions_dir.exists():
        return moved
    quarantine_dir = root / "state" / "cli_sessions"
    for path in sorted(sessions_dir.glob("*.json")):
        try:
            data = loader(path)
        except Exception:
            continue
        if not is_cli_invocation_log(data):
            continue
        quarantine_dir.mkdir(parents=True, exist_ok=True)
        dest = quarantine_dir / path.name
        if dest.exists():
            base = dest.with_suffix("")
            suffix = dest.suffix
            n = 2
            while dest.exists():
                dest = Path(f"{base}_{n}{suffix}")
                n += 1
        path.replace(dest)
        moved.append(path.name)
    return moved


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

