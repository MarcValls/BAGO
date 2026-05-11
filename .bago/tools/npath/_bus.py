"""npath._bus — Neural Bus fire-and-forget event emitter."""
from __future__ import annotations

import json
import os
from pathlib import Path

from npath._db import BAGO_ROOT

_BUS_URL    = os.environ.get("BAGO_NEURAL_URL", "http://localhost:6789")
_TOKEN_FILE = BAGO_ROOT / "state" / "neural_token.txt"


def _neural_bus_emit(topic: str, payload: dict) -> None:
    """Non-blocking emit to Neural Bus. Silently fails if bus is not running."""
    import threading
    import urllib.request as _req

    token = _TOKEN_FILE.read_text(encoding="utf-8").strip() if _TOKEN_FILE.exists() else ""
    body  = json.dumps({
        "from": "npath",
        "to":   "*",
        "topic": topic,
        "payload": payload,
        "durable": True,
    }).encode()

    def _post() -> None:
        try:
            req = _req.Request(
                f"{_BUS_URL}/emit", data=body,
                headers={"Content-Type": "application/json", "X-Bago-Token": token},
                method="POST",
            )
            with _req.urlopen(req, timeout=1):
                pass
        except Exception:
            pass  # Bus not running — npath works standalone

    threading.Thread(target=_post, daemon=True).start()
