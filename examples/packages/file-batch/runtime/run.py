import json
from pathlib import Path
import sys


payload = json.load(sys.stdin)
inputs = payload.get("input", {})
limit = max(1, min(int(payload.get("config", {}).get("max_files", 100)), 200))
root = Path(str(inputs.get("root", ""))).expanduser().resolve()
pattern = str(inputs.get("pattern") or "*")

if not root.is_dir():
    raise SystemExit("root must be an existing directory")

files = []
for path in root.rglob(pattern):
    if not path.is_file():
        continue
    stat = path.stat()
    files.append({
        "path": path.relative_to(root).as_posix(),
        "size": stat.st_size,
        "modified_ns": stat.st_mtime_ns,
    })
    if len(files) >= limit:
        break

print(json.dumps({"root": str(root), "count": len(files), "files": files}, ensure_ascii=False))
