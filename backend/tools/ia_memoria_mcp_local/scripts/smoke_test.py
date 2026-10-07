from __future__ import annotations

import tempfile
from pathlib import Path

from ia_memoria.config import Settings
from ia_memoria.repository import MemoryRepository
from ia_memoria.security import SecurityError, safe_resolve

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    settings = Settings(root, "stdio", "127.0.0.1", 8765, 524288, 20, frozenset({".md", ".txt", ".json", ".jsonl", ".yaml", ".yml", ".toml"}))
    repo = MemoryRepository(settings)
    repo.initialize()
    repo.create_project("TEST", "Prueba", "Verificar el sistema.")
    proposal = repo.propose_memory("TEST", "La salida debe verificarse.", "regla", "smoke_test", proposed_class="MEM_CONFIRMED")
    memory = repo.commit_memory(proposal["proposal_id"], "smoke_test")
    found = repo.search("verificarse", "TEST")
    assert memory["status"] == "active"
    assert found["memories"]
    try:
        safe_resolve(root, "../fuera.txt", must_exist=False)
        raise AssertionError("La frontera de rutas no bloqueó '..'.")
    except SecurityError:
        pass

import mcp  # noqa: F401
print("SMOKE TEST: OK")
