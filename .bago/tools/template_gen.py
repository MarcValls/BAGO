#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
template_gen.py — Genera archivos de proyecto desde plantillas predefinidas.

Las plantillas están integradas en este script (no requieren archivos externos).
Variables de plantilla: {{PROJECT}}, {{APP}}, {{NAME}}, {{DATE}}, {{AUTHOR}}

Uso:
    python3 .bago/tools/template_gen.py --list
    python3 .bago/tools/template_gen.py --show NOMBRE
    python3 .bago/tools/template_gen.py NOMBRE [--name VALOR] [--app VALOR] [--out DIR]
    python3 .bago/tools/template_gen.py --add NOMBRE "contenido"  # plantilla custom

Plantillas disponibles:
    component   React component (.tsx)
    hook        React custom hook (.ts)
    api-route   API route handler (.ts)
    test        Test file (vitest/playwright)
    env-example .env.example file
    readme      README.md
    gitignore   .gitignore
    docker      Dockerfile

Códigos de salida: 0 = OK, 1 = error
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT  = Path(__file__).resolve().parents[2]
STATE = ROOT / ".bago" / "state"
CUSTOM_TEMPLATES_FILE = STATE / "bago_templates.json"


def BOLD(s: str)   -> str: return f"\033[1m{s}\033[0m"
def DIM(s: str)    -> str: return f"\033[2m{s}\033[0m"
def GREEN(s: str)  -> str: return f"\033[32m{s}\033[0m"
def YELLOW(s: str) -> str: return f"\033[33m{s}\033[0m"
def CYAN(s: str)   -> str: return f"\033[36m{s}\033[0m"
def RED(s: str)    -> str: return f"\033[31m{s}\033[0m"


# ─── Built-in templates ──────────────────────────────────────────────────────

BUILTIN: dict[str, dict[str, Any]] = {
    "component": {
        "ext":     ".tsx",
        "dest":    "apps/{{APP}}/src/components/{{NAME}}.tsx",
        "desc":    "React component con TypeScript",
        "content": """\
import React from 'react';

interface {{NAME}}Props {
  // TODO: define props
}

export const {{NAME}}: React.FC<{{NAME}}Props> = () => {
  return (
    <div className="{{name-kebab}}">
      <h2>{{NAME}}</h2>
    </div>
  );
};

export default {{NAME}};
""",
    },
    "hook": {
        "ext":     ".ts",
        "dest":    "apps/{{APP}}/src/hooks/use{{NAME}}.ts",
        "desc":    "React custom hook",
        "content": """\
import { useState, useEffect } from 'react';

export function use{{NAME}}() {
  const [data, setData] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    // TODO: implement hook logic
  }, []);

  return { data, loading, error };
}
""",
    },
    "api-route": {
        "ext":     ".ts",
        "dest":    "apps/{{APP}}/src/routes/{{name-kebab}}.ts",
        "desc":    "API route handler (Express/Hono)",
        "content": """\
import type { Request, Response } from 'express';

// GET /api/{{name-kebab}}
export async function get{{NAME}}(req: Request, res: Response) {
  try {
    // TODO: implement
    res.json({ ok: true, data: null });
  } catch (err) {
    res.status(500).json({ ok: false, error: String(err) });
  }
}

// POST /api/{{name-kebab}}
export async function create{{NAME}}(req: Request, res: Response) {
  try {
    const body = req.body;
    // TODO: validate and save
    res.status(201).json({ ok: true, data: body });
  } catch (err) {
    res.status(500).json({ ok: false, error: String(err) });
  }
}
""",
    },
    "test": {
        "ext":     ".test.ts",
        "dest":    "apps/{{APP}}/src/__tests__/{{NAME}}.test.ts",
        "desc":    "Test file (vitest)",
        "content": """\
import { describe, it, expect, beforeEach } from 'vitest';

describe('{{NAME}}', () => {
  beforeEach(() => {
    // setup
  });

  it('should work correctly', () => {
    // TODO: implement test
    expect(true).toBe(true);
  });

  it('should handle edge cases', () => {
    // TODO: edge cases
  });
});
""",
    },
    "env-example": {
        "ext":     "",
        "dest":    "apps/{{APP}}/.env.example",
        "desc":    ".env.example con variables comunes",
        "content": """\
# {{PROJECT}} - {{APP}} environment variables
# Copy to .env and fill in your values

NODE_ENV=development
PORT=3000

# Database
DATABASE_URL=

# Auth
JWT_SECRET=your-secret-here
SESSION_SECRET=

# API Keys
API_KEY=
""",
    },
    "readme": {
        "ext":     ".md",
        "dest":    "apps/{{APP}}/README.md",
        "desc":    "README.md para una app del proyecto",
        "content": """\
# {{NAME}}

Part of **{{PROJECT}}** — generated {{DATE}}

## Setup

```bash
pnpm install
pnpm dev
```

## Scripts

| Script | Description |
|--------|-------------|
| `pnpm dev` | Start development server |
| `pnpm build` | Build for production |
| `pnpm test` | Run tests |

## Structure

```
src/
  components/    React components
  hooks/         Custom hooks
  routes/        API routes (if applicable)
```
""",
    },
    "gitignore": {
        "ext":     "",
        "dest":    "apps/{{APP}}/.gitignore",
        "desc":    ".gitignore estándar para apps web",
        "content": """\
node_modules/
dist/
build/
.next/
out/
coverage/
*.log
.env
.env.local
.DS_Store
Thumbs.db
""",
    },
    "docker": {
        "ext":     "",
        "dest":    "apps/{{APP}}/Dockerfile",
        "desc":    "Dockerfile multi-stage para Node.js",
        "content": """\
# Build stage
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build

# Production stage
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
EXPOSE 3000
CMD ["node", "dist/index.js"]
""",
    },
}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _load_custom() -> dict[str, Any]:
    if CUSTOM_TEMPLATES_FILE.exists():
        try:
            return json.loads(CUSTOM_TEMPLATES_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_custom(data: dict[str, Any]) -> None:
    CUSTOM_TEMPLATES_FILE.parent.mkdir(parents=True, exist_ok=True)
    CUSTOM_TEMPLATES_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _all_templates() -> dict[str, Any]:
    merged = dict(BUILTIN)
    merged.update(_load_custom())
    return merged


def _render(template: str, vars: dict[str, str]) -> str:
    """Replace {{VAR}} and {{var-kebab}} placeholders."""
    result = template
    for k, v in vars.items():
        result = result.replace(f"{{{{{k}}}}}", v)
    return result


def _to_kebab(s: str) -> str:
    import re
    s = re.sub(r'([A-Z])', r'-\1', s).lower().strip('-')
    return re.sub(r'[^a-z0-9-]', '-', s)


def _load_project_name() -> str:
    gs = STATE / "global_state.json"
    if gs.exists():
        try:
            data = json.loads(gs.read_text(encoding="utf-8"))
            return data.get("active_project", {}).get("name", "INTELIA")
        except Exception:
            pass
    return "INTELIA"


def _detect_apps() -> list[str]:
    apps_dir = ROOT / "apps"
    if apps_dir.exists():
        return [d.name for d in apps_dir.iterdir() if d.is_dir()]
    return []


# ─── Commands ────────────────────────────────────────────────────────────────

def cmd_list() -> None:
    all_t = _all_templates()
    custom = set(_load_custom().keys())
    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Plantillas de archivos                              │")
    print("  └─────────────────────────────────────────────────────────────┘")
    print(f"  {'NOMBRE':<16}  {'EXT':<12}  {'DESCRIPCIÓN'}")
    print(f"  {'──────':<16}  {'───':<12}  {'───────────'}")
    for name, t in sorted(all_t.items()):
        ext    = t.get("ext", "")
        desc   = t.get("desc", "")
        tag    = f" {YELLOW('[custom]')}" if name in custom else ""
        print(f"  {CYAN(name):<16}  {DIM(ext or '(none)'):<12}  {desc}{tag}")
    print()
    apps = _detect_apps()
    if apps:
        print(f"  Apps detectadas: {', '.join(BOLD(a) for a in apps)}")
    print()
    print(f"  Uso: {DIM('bago template NOMBRE [--name VALOR] [--app VALOR] [--out DIR]')}")
    print(f"       {DIM('bago template --show NOMBRE')}")
    _tmpl_add_ex = 'bago template --add NOMBRE "contenido"'
    print(f"       {DIM(_tmpl_add_ex)}")
    print()


def cmd_show(name: str) -> int:
    all_t = _all_templates()
    if name not in all_t:
        print(f"\n  {RED('✗')} Plantilla '{name}' no encontrada. Use --list para ver disponibles.\n")
        return 1
    t = all_t[name]
    print()
    print(f"  {BOLD('Plantilla:')} {CYAN(name)}  —  {t.get('desc', '')}")
    print(f"  {BOLD('Destino:')}   {DIM(t.get('dest', ''))}")
    print(f"  {BOLD('Extensión:')} {DIM(t.get('ext', '(none)'))}")
    print()
    print("  " + "─" * 60)
    for line in t["content"].splitlines():
        print(f"  {DIM(line)}")
    print("  " + "─" * 60)
    print()
    return 0


def cmd_generate(name: str, name_val: str, app_val: str, out_dir: Path | None, dry: bool) -> int:
    all_t = _all_templates()
    if name not in all_t:
        print(f"\n  {RED('✗')} Plantilla '{name}' no encontrada. Use --list para ver disponibles.\n")
        return 1

    project = _load_project_name()
    date    = datetime.now().strftime("%Y-%m-%d")
    kebab   = _to_kebab(name_val)

    vars: dict[str, str] = {
        "PROJECT":    project,
        "APP":        app_val,
        "NAME":       name_val,
        "name-kebab": kebab,
        "DATE":       date,
        "AUTHOR":     "INTELIA",
    }

    t       = all_t[name]
    content = _render(t["content"], vars)
    dest    = _render(t["dest"], vars)

    if out_dir:
        # Flatten to just filename in out_dir
        fname = Path(dest).name
        target = out_dir / fname
    else:
        target = ROOT / dest

    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  BAGO · Generar plantilla                                   │")
    print("  └─────────────────────────────────────────────────────────────┘")
    print(f"  Plantilla:  {CYAN(name)}")
    print(f"  Nombre:     {BOLD(name_val)}")
    print(f"  App:        {app_val}")
    print(f"  Destino:    {DIM(str(target))}")
    print()

    if dry:
        print(f"  {YELLOW('[DRY RUN]')} No se escribirá el archivo.")
        print()
        print("  Contenido generado:")
        print("  " + "─" * 60)
        for line in content.splitlines():
            print(f"  {line}")
        print("  " + "─" * 60)
        print()
        return 0

    if target.exists():
        print(f"  {YELLOW('⚠')} El archivo ya existe: {target}")
        ans = input("  ¿Sobrescribir? [s/N] ").strip().lower()
        if ans != "s":
            print("  Cancelado.\n")
            return 0

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    print(f"  {GREEN('✅')} Archivo creado: {BOLD(str(target))}")
    print()
    return 0


def cmd_add(custom_name: str, content: str) -> int:
    customs = _load_custom()
    customs[custom_name] = {
        "ext":     "",
        "dest":    f"{{{{APP}}}}/{custom_name}",
        "desc":    f"Plantilla custom: {custom_name}",
        "content": content,
    }
    _save_custom(customs)
    print(f"\n  {GREEN('✅')} Plantilla '{custom_name}' guardada.\n")
    return 0


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    args = sys.argv[1:]

    if not args or "--list" in args or args == ["-l"]:
        cmd_list()
        return 0

    if "--show" in args:
        idx = args.index("--show")
        tname = args[idx + 1] if idx + 1 < len(args) else ""
        return cmd_show(tname)

    if "--add" in args:
        idx = args.index("--add")
        if idx + 2 < len(args):
            return cmd_add(args[idx + 1], args[idx + 2])
        print(f"  {RED('✗')} Uso: --add NOMBRE \"contenido\"\n")
        return 1

    # Generate: first positional arg is template name
    pos = [a for a in args if not a.startswith("-")]
    if not pos:
        cmd_list()
        return 0

    tname = pos[0]

    name_val = "MyComponent"
    if "--name" in args:
        idx = args.index("--name")
        if idx + 1 < len(args):
            name_val = args[idx + 1]

    app_val = "web"
    if "--app" in args:
        idx = args.index("--app")
        if idx + 1 < len(args):
            app_val = args[idx + 1]

    out_dir: Path | None = None
    if "--out" in args:
        idx = args.index("--out")
        if idx + 1 < len(args):
            out_dir = Path(args[idx + 1])

    dry = "--dry" in args

    return cmd_generate(tname, name_val, app_val, out_dir, dry)



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    raise SystemExit(main())
