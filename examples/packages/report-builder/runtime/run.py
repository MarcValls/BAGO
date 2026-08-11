import json
import sys


payload = json.load(sys.stdin)
inputs = payload.get("input", {})
title = str(inputs.get("title", "Informe"))
summary = str(inputs.get("summary", "")).strip()
sections = json.loads(str(inputs.get("sections_json", "[]")))
if not isinstance(sections, list):
    raise SystemExit("sections_json must contain a JSON list")

normalized = [
    {"title": str(item.get("title", "Seccion")), "content": str(item.get("content", ""))}
    for item in sections
    if isinstance(item, dict)
]
if payload.get("config", {}).get("format") == "json":
    content = json.dumps({"title": title, "summary": summary, "sections": normalized}, ensure_ascii=False, indent=2)
    output_format = "json"
else:
    blocks = [f"# {title}"]
    if summary:
        blocks.append(summary)
    blocks.extend(f"## {item['title']}\n\n{item['content']}" for item in normalized)
    content = "\n\n".join(blocks) + "\n"
    output_format = "markdown"

print(json.dumps({"format": output_format, "content": content}, ensure_ascii=False))
