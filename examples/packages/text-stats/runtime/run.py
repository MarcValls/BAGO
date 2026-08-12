import json
import sys


payload = json.load(sys.stdin)
text = payload["input"]["text"]
if payload["config"].get("lowercase"):
    text = text.lower()
print(json.dumps({
    "text": text,
    "words": len(text.split()),
    "characters": len(text),
}, ensure_ascii=False))
