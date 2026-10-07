import json
import sys


payload = json.load(sys.stdin)
data = payload["input"]


def bullet_items(value):
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [line.strip() for line in str(value or "").splitlines() if line.strip()]


name = "-".join((
    data["project"].strip(),
    data["agent_role"].strip(),
    data["work_item"].strip(),
    data["version"].strip(),
    data["status"].strip(),
    data["cycle"].strip(),
))

sections = [
    ("Resultado producido", data.get("result", "")),
    ("Decisiones", bullet_items(data.get("decisions", ""))),
    ("Pendientes", bullet_items(data.get("open_items", ""))),
    ("Siguiente rol", data.get("next_role", "")),
    ("Instrucción siguiente", data.get("next_instruction", "")),
    ("Herencia contextual", data.get("inherited_context", "")),
    ("Fuentes", bullet_items(data.get("sources", ""))),
    ("Criterio de éxito", data.get("success_criteria", "")),
]

lines = [f"# {name}", "", f"Estado: `{data['status']}`", ""]
for title, value in sections:
    if not value:
        continue
    lines.extend((f"## {title}", ""))
    if isinstance(value, list):
        lines.extend(f"- {item}" for item in value)
    else:
        lines.append(str(value))
    lines.append("")

print(json.dumps({
    "title": name,
    "status": data["status"],
    "handoff_markdown": "\n".join(lines).rstrip() + "\n",
}, ensure_ascii=False))
