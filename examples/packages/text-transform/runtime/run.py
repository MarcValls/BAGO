import json
import re
import sys


payload = json.load(sys.stdin)
config = payload.get("config", {})
text = str(payload.get("input", {}).get("text", ""))
operation = config.get("operation", "clean")

if operation == "uppercase":
    result = text.upper()
elif operation == "lowercase":
    result = text.lower()
elif operation == "replace":
    result = text.replace(str(config.get("find", "")), str(config.get("replacement", "")))
else:
    result = re.sub(r"\s+", " ", text).strip()

print(json.dumps({"text": result, "operation": operation}, ensure_ascii=False))
