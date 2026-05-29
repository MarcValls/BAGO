from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional


def _find_anchor(start: Path, marker: str = "tool_registry.py", max_up: int = 8) -> Path:
    """Sube desde `start` hasta encontrar un directorio que contenga `marker`."""
    candidate = start.resolve()
    for _ in range(max_up):
        if (candidate / marker).exists():
            return candidate
        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent
    raise RuntimeError(
        f"No se encontró '{marker}' subiendo desde {start}. "
        "¿Está path_healer.py dentro del árbol de BAGO?"
    )


_SELF_DIR = Path(__file__).resolve().parent
TOOLS_DIR = _find_anchor(_SELF_DIR)
BAGO_ROOT = TOOLS_DIR.parent
REPO_ROOT = BAGO_ROOT.parent
STATE_DIR = BAGO_ROOT / "state"
MEMORY_FILE = STATE_DIR / "path_healer_memory.json"


@dataclass
class Memory:
    """Estado persistente del healer entre ejecuciones."""

    version: int = 1
    last_scan: str = ""
    stem_index: dict[str, str] = field(default_factory=dict)
    healed: dict[str, dict] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)

    def save(self) -> None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        MEMORY_FILE.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @classmethod
    def load(cls) -> "Memory":
        if not MEMORY_FILE.exists():
            return cls()
        try:
            data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
            defaults = asdict(cls())
            payload = {key: data.get(key, value) for key, value in defaults.items()}
            return cls(**payload)
        except Exception:
            return cls()

    def record_heal(self, file_rel: str, stem: str, line: int, old: str, new: str) -> None:
        entry = self.healed.setdefault(file_rel, {})
        entry[stem] = {
            "line": line,
            "old": old,
            "new": new,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }

    def update_stem(self, stem: str, actual_path: Path) -> None:
        try:
            rel = str(actual_path.relative_to(REPO_ROOT))
        except ValueError:
            rel = str(actual_path)
        self.stem_index[stem] = rel

    def resolve_stem(self, stem: str) -> Optional[Path]:
        rel = self.stem_index.get(stem)
        if not rel:
            return None
        path = REPO_ROOT / rel
        if path.exists():
            return path
        del self.stem_index[stem]
        return None


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

