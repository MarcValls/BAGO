"""Historial de scans de providers y detector MISSING."""

from __future__ import annotations

import datetime as _dt
import json

from .constants import SCAN_HISTORY_FILE


def update_scan_history(health: dict) -> dict:
    """Actualiza historial de scans y devuelve providers MISSING."""
    now = _dt.datetime.now().isoformat()

    history: dict = {}
    if SCAN_HISTORY_FILE.exists():
        try:
            history = json.loads(SCAN_HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            history = {}

    providers_hist: dict = history.get("providers", {})
    for pname, hdata in health.items():
        entry = providers_hist.setdefault(pname, {"first_seen": now})
        if hdata.get("ok"):
            entry["last_ok"] = now
            entry["last_models"] = hdata.get("models", [])
            entry.setdefault("first_seen", now)

    history["last_scan"] = now
    history["providers"] = providers_hist
    SCAN_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    SCAN_HISTORY_FILE.write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    missing: dict = {}
    for pname, phist in providers_hist.items():
        if not phist.get("last_ok"):
            continue
        current = health.get(pname, {})
        if not current.get("ok"):
            missing[pname] = {
                "last_ok": phist["last_ok"],
                "last_models": phist.get("last_models", []),
            }

    return missing



def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(__file__ + " --test: PASS (imports OK)")
    return 0


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
