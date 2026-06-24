#!/usr/bin/env python3
"""project_scaffold.py — BAGO tool: scaffold a new project structure.

Usage:
    python project_scaffold.py --name <project-name> --template <template-name>
    python project_scaffold.py --name my-app --template react-vite
    python project_scaffold.py --name my-api --template python-fastapi

Creates a new project directory with standard files based on a template.
The project is created inside the workspace root.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

def _get_workspace_root() -> Path:
    root = os.environ.get("BAGO_WORKSPACE_ROOT", "")
    if root:
        return Path(root).resolve()
    return Path.cwd().resolve()

def _dev_mode() -> bool:
    return os.environ.get("BAGO_DEV_MODE", "").strip() in ("1", "true", "TRUE", "yes", "YES")

FORBIDDEN = (".git", ".env", "state", "dist", "release", "__pycache__", ".bago", "node_modules", ".venv", "venv")

def _is_forbidden(path_str: str) -> bool:
    if _dev_mode():
        return False
    normalized = path_str.replace("\\", "/").lower()
    for seg in FORBIDDEN:
        if seg.lower() in normalized.split("/"):
            return True
    return False

TEMPLATES: dict[str, dict] = {
    "react-vite": {
        "description": "React 19 + Vite + TypeScript + Tailwind CSS v4",
        "files": {
            "package.json": json.dumps({
                "name": "{{PROJECT_NAME}}",
                "private": True,
                "version": "0.0.0",
                "type": "module",
                "scripts": {
                    "dev": "vite",
                    "build": "tsc -b && vite build",
                    "preview": "vite preview"
                },
                "dependencies": {
                    "react": "^19.0.0",
                    "react-dom": "^19.0.0"
                },
                "devDependencies": {
                    "@types/react": "^19.0.0",
                    "@types/react-dom": "^19.0.0",
                    "@vitejs/plugin-react-swc": "^4.2.2",
                    "typescript": "~5.7.2",
                    "vite": "^7.0.0"
                }
            }, indent=2, ensure_ascii=False),
            "vite.config.ts": """import {{ defineConfig }} from 'vite'
import react from '@vitejs/plugin-react-swc'

export default defineConfig({{
  plugins: [react()],
}})
""",
            "tsconfig.json": json.dumps({
                "compilerOptions": {
                    "target": "ES2020",
                    "useDefineForClassFields": True,
                    "lib": ["ES2020", "DOM", "DOM.Iterable"],
                    "module": "ESNext",
                    "skipLibCheck": True,
                    "moduleResolution": "bundler",
                    "allowImportingTsExtensions": True,
                    "isolatedModules": True,
                    "moduleDetection": "force",
                    "noEmit": True,
                    "jsx": "react-jsx",
                    "strict": True
                },
                "include": ["src"]
            }, indent=2, ensure_ascii=False),
            "index.html": """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{{PROJECT_NAME}}</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
""",
            "src/main.tsx": """import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
""",
            "src/App.tsx": """export default function App() {
  return (
    <div>
      <h1>{{PROJECT_NAME}}</h1>
      <p>Welcome to your new project.</p>
    </div>
  )
}
""",
            ".gitignore": """node_modules/
dist/
.env
*.log
__pycache__/
""",
        },
    },
    "python-fastapi": {
        "description": "Python + FastAPI + uvicorn",
        "files": {
            "requirements.txt": """fastapi>=0.100.0
uvicorn[standard]>=0.20.0
""",
            "main.py": '''"""{{PROJECT_NAME}} — FastAPI application."""
from fastapi import FastAPI

app = FastAPI(title="{{PROJECT_NAME}}")

@app.get("/")
def root():
    return {"name": "{{PROJECT_NAME}}", "status": "ok"}

@app.get("/health")
def health():
    return {"status": "healthy"}
''',
            ".gitignore": """__pycache__/
*.pyc
.env
venv/
.venv/
""",
            "README.md": """# {{PROJECT_NAME}}

A FastAPI application.

## Setup

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```
""",
        },
    },
    "python-cli": {
        "description": "Python CLI tool with argparse",
        "files": {
            "main.py": '''#!/usr/bin/env python3
"""{{PROJECT_NAME}} — CLI tool."""
import argparse
import sys

def main() -> int:
    parser = argparse.ArgumentParser(description="{{PROJECT_NAME}}")
    parser.add_argument("command", nargs="?", default="help", help="Command to run")
    args = parser.parse_args()

    if args.command == "help":
        print("{{PROJECT_NAME}} — available commands: help")
        return 0

    print(f"Unknown command: {args.command}")
    return 1

if __name__ == "__main__":
    sys.exit(main())
''',
            "requirements.txt": "",
            ".gitignore": """__pycache__/
*.pyc
.env
""",
            "README.md": """# {{PROJECT_NAME}}

A Python CLI tool.

## Usage

```bash
python main.py help
```
""",
        },
    },
    "static-web": {
        "description": "Static HTML/CSS/JS website",
        "files": {
            "index.html": """<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{PROJECT_NAME}}</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <h1>{{PROJECT_NAME}}</h1>
  <p>Welcome to your new website.</p>
  <script src="script.js"></script>
</body>
</html>
""",
            "styles.css": """* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: system-ui, sans-serif; padding: 2rem; }
""",
            "script.js": """console.log('{{PROJECT_NAME}} loaded');
""",
            ".gitignore": """.env
*.log
""",
        },
    },
}


def main() -> int:
    args = sys.argv[1:]
    name_arg = ""
    template_arg = "react-vite"
    list_templates = False

    i = 0
    while i < len(args):
        if args[i] == "--name" and i + 1 < len(args):
            name_arg = args[i + 1]
            i += 2
        elif args[i] == "--template" and i + 1 < len(args):
            template_arg = args[i + 1]
            i += 2
        elif args[i] == "--list":
            list_templates = True
            i += 1
        else:
            i += 1

    if list_templates:
        templates = {k: {"description": v["description"], "files": list(v["files"].keys())} for k, v in TEMPLATES.items()}
        print(json.dumps({"ok": True, "templates": templates}, ensure_ascii=False, indent=2))
        return 0

    if not name_arg:
        print(json.dumps({"ok": False, "error": "Missing --name argument"}, ensure_ascii=False))
        return 1

    if _is_forbidden(name_arg):
        print(json.dumps({"ok": False, "error": f"Forbidden project name: {name_arg}"}, ensure_ascii=False))
        return 1

    if template_arg not in TEMPLATES:
        available = ", ".join(TEMPLATES.keys())
        print(json.dumps({"ok": False, "error": f"Unknown template: {template_arg}. Available: {available}"}, ensure_ascii=False))
        return 1

    ws_root = _get_workspace_root()
    project_dir = ws_root / name_arg
    if project_dir.exists():
        print(json.dumps({"ok": False, "error": f"Project directory already exists: {name_arg}"}, ensure_ascii=False))
        return 1

    template = TEMPLATES[template_arg]
    files = template["files"]
    created_files: list[str] = []

    try:
        for rel_path, content in files.items():
            file_path = project_dir / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            final_content = content.replace("{{PROJECT_NAME}}", name_arg)
            file_path.write_text(final_content, encoding="utf-8")
            created_files.append(rel_path)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"Create error: {exc}"}, ensure_ascii=False))
        return 1

    result = {
        "ok": True,
        "name": name_arg,
        "template": template_arg,
        "description": template["description"],
        "path": str(project_dir.relative_to(ws_root)) if str(project_dir) != str(ws_root) else name_arg,
        "files_created": created_files,
        "file_count": len(created_files),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())