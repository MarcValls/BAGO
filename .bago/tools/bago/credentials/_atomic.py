"""bago.credentials._atomic — Helper de escritura atómica con permisos 0o600.

Patrón replicado de bago.tumba._save() para evitar pérdida total de
tokens si el proceso crashea en medio de la escritura.
"""

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import json
import os
import tempfile
from pathlib import Path


def atomic_write_json(path: Path, data: dict, *, indent: int = 2,
                      ensure_ascii: bool = True) -> None:
    """Escribe `data` a `path` de forma atómica con permisos 0o600.

    1. mkdir -p del directorio padre
    2. mkstemp en el MISMO directorio (para que os.replace sea atómico)
    3. chmod 0o600 sobre el temporal
    4. os.replace(tmp, path) — atómico en POSIX y NTFS

    Si algo falla en medio, el archivo original queda intacto.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=indent, ensure_ascii=ensure_ascii).encode("utf-8")
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=path.parent, prefix="." + path.name + "_tmp_", suffix=".json"
    )
    try:
        with os.fdopen(tmp_fd, "wb") as fh:
            fh.write(payload)
        try:
            os.chmod(tmp_path, 0o600)
        except Exception:
            pass
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(f"{Path(__file__).name} --test: PASS (imports OK)")
    return 0
if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
