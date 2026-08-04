from __future__ import annotations

import json
import sys


payload = json.load(sys.stdin)
text = str(payload.get("input", {}).get("text", ""))
if payload.get("config", {}).get("lowercase"):
    text = text.lower()
print(json.dumps({
    "text": text,
    "words": len(text.split()),
    "characters": len(text),
    "lines": len(text.splitlines()) or 1,
}, ensure_ascii=False))
