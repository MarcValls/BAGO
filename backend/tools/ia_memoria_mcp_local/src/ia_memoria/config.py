from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MEMORY_ROOT = PACKAGE_ROOT / "memory_root"

@dataclass(frozen=True)
class Settings:
    memory_root: Path
    transport: str
    host: str
    port: int
    max_read_bytes: int
    max_results: int
    allowed_extensions: frozenset[str]

    @classmethod
    def from_env(cls) -> "Settings":
        root = Path(os.environ.get("IA_MEMORY_ROOT", str(DEFAULT_MEMORY_ROOT))).expanduser()
        transport = os.environ.get("IA_MEMORY_TRANSPORT", "stdio").strip().lower()
        if transport not in {"stdio", "streamable-http"}:
            raise ValueError("IA_MEMORY_TRANSPORT debe ser 'stdio' o 'streamable-http'.")
        return cls(
            memory_root=root.resolve(),
            transport=transport,
            host=os.environ.get("IA_MEMORY_HOST", "127.0.0.1"),
            port=int(os.environ.get("IA_MEMORY_PORT", "8765")),
            max_read_bytes=int(os.environ.get("IA_MEMORY_MAX_READ_BYTES", "524288")),
            max_results=min(max(int(os.environ.get("IA_MEMORY_MAX_RESULTS", "20")), 1), 100),
            allowed_extensions=frozenset({".md", ".txt", ".json", ".jsonl", ".yaml", ".yml", ".toml"}),
        )
