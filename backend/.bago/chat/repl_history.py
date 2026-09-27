"""Server-owned persistence adapters for interactive REPL history."""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

try:
    from prompt_toolkit.history import FileHistory
except Exception:  # pragma: no cover - optional terminal dependency
    FileHistory = None  # type: ignore[assignment,misc]


def save_readline_history(readline: Any, path: Path, *, trusted_root: Path, session_id: str) -> None:
    """Replace readline's canonical history file through the state owner."""
    from bago_core.server_effects import write_text_atomic

    entries = [
        str(readline.get_history_item(index))
        for index in range(1, int(readline.get_current_history_length()) + 1)
    ]
    content = "".join(f"{entry}\n" for entry in entries)
    write_text_atomic(
        path,
        content,
        trusted_root=trusted_root,
        source_surface="chat.readline_history",
        session_id=session_id,
    )


if FileHistory is not None:
    class GatewayFileHistory(FileHistory):
        """Keep prompt_toolkit's compatible format, with gateway-owned appends."""

        def __init__(self, filename: str | Path, *, trusted_root: Path, session_id: str):
            super().__init__(str(filename))
            self._trusted_root = Path(trusted_root)
            self._session_id = str(session_id)

        def store_string(self, value: str) -> None:
            from bago_core.server_effects import append_text_durable

            content = f"\n# {datetime.datetime.now()}\n"
            content += "".join(f"+{line}\n" for line in value.split("\n"))
            append_text_durable(
                Path(self.filename),
                content,
                trusted_root=self._trusted_root,
                source_surface="chat.prompt_history",
                session_id=self._session_id,
            )
else:  # pragma: no cover - optional terminal dependency
    GatewayFileHistory = None  # type: ignore[assignment,misc]


__all__ = ["GatewayFileHistory", "save_readline_history"]
