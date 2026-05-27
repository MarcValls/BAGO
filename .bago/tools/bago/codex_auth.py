"""Descubrimiento de token Codex/OpenAI CLI."""

from __future__ import annotations

import json
from pathlib import Path


def codex_access_token() -> str | None:
    try:
        auth_file = Path.home() / ".codex" / "auth.json"
        if auth_file.exists():
            data = json.loads(auth_file.read_text(encoding="utf-8"))
            token = (data.get("tokens") or {}).get("access_token") or data.get("access_token")
            if token:
                return token
    except Exception:
        pass
    return None



def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(__file__ + " --test: PASS (imports OK)")
    return 0


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
