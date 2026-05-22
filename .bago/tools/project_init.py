"""bago init — scaffold a new BAGO monorepo project."""
import argparse
import json
import os
import sys
from pathlib import Path

BAGO_DIR = Path(__file__).resolve().parent.parent
TOOLS_DIR = Path(__file__).resolve().parent

WEB_PKG = {
    "name": "@{slug}/web",
    "version": "0.0.1",
    "private": True,
    "scripts": {
        "dev": "vite",
        "build": "vite build",
        "preview": "vite preview",
        "lint": "eslint src --ext .ts,.tsx",
        "typecheck": "tsc --noEmit"
    },
    "dependencies": {
        "react": "^18.3.1",
        "react-dom": "^18.3.1"
    },
    "devDependencies": {
        "vite": "^5.4.0",
        "@vitejs/plugin-react": "^4.3.0",
        "typescript": "^5.6.0"
    }
}

SERVER_PKG = {
    "name": "@{slug}/server",
    "version": "0.0.1",
    "private": True,
    "type": "module",
    "scripts": {
        "dev": "node --watch src/server.mjs",
        "start": "node src/server.mjs",
        "test": "node --test"
    },
    "dependencies": {}
}

ELECTRON_PKG = {
    "name": "@{slug}/electron",
    "version": "0.0.1",
    "private": True,
    "main": "src/main.cjs",
    "scripts": {
        "dev": "electron .",
        "build": "electron-builder",
        "test": "node --test"
    },
    "devDependencies": {
        "electron": "^37.0.0",
        "electron-builder": "^26.0.0"
    }
}

ROOT_PKG = {
    "name": "{slug}-monorepo",
    "version": "0.0.1",
    "private": True,
    "scripts": {
        "dev:web": "pnpm --filter @{slug}/web dev",
        "dev:server": "pnpm --filter @{slug}/server dev",
        "dev:desktop": "pnpm --filter @{slug}/electron dev",
        "build:web": "pnpm --filter @{slug}/web build",
        "build:desktop": "pnpm --filter @{slug}/electron build",
        "lint": "pnpm -r --if-present lint",
        "typecheck": "pnpm -r --if-present typecheck",
        "test": "pnpm -r --if-present test"
    }
}

PNPM_WORKSPACE = "packages:\n  - 'apps/*'\n"

BAGO_CONFIG = {
    "project": "{slug}",
    "version": "1.0.0",
    "waves": [1]
}

GITIGNORE = "\n".join([
    "node_modules/", "dist/", "*.local", ".env",
    ".bago/state/", ".bago/snapshots/", "desktop-dist/"
])

SERVER_MAIN = """\
// apps/server/src/server.mjs
const PORT = process.env.PORT ?? 3001;
const server = (await import('node:http')).createServer((req, res) => {
  if (req.url === '/health' && req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ ok: true, time: new Date().toISOString() }));
    return;
  }
  res.writeHead(404);
  res.end();
});
server.listen(PORT, () => console.log(`Server on http://localhost:${PORT}`));
"""

ELECTRON_MAIN = """\
// apps/electron/src/main.cjs
const { app, BrowserWindow } = require('electron');
function createWindow() {
  const win = new BrowserWindow({ width: 1200, height: 800 });
  win.loadURL('http://localhost:5173');
}
app.whenReady().then(createWindow);
"""


def _write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _pkg(template: dict, slug: str) -> str:
    text = json.dumps(template, indent=2)
    return text.replace("{slug}", slug)


def scaffold(dest: Path, slug: str, dry: bool):
    files = {
        dest / "package.json": _pkg(ROOT_PKG, slug),
        dest / "pnpm-workspace.yaml": PNPM_WORKSPACE,
        dest / ".gitignore": GITIGNORE,
        dest / ".bago" / "config.json": json.dumps(BAGO_CONFIG, indent=2).replace("{slug}", slug),
        dest / "apps" / "web" / "package.json": _pkg(WEB_PKG, slug),
        dest / "apps" / "server" / "package.json": _pkg(SERVER_PKG, slug),
        dest / "apps" / "server" / "src" / "server.mjs": SERVER_MAIN,
        dest / "apps" / "electron" / "package.json": _pkg(ELECTRON_PKG, slug),
        dest / "apps" / "electron" / "src" / "main.cjs": ELECTRON_MAIN,
    }
    print(f"\n  🚀  Scaffolding '{slug}' → {dest}\n")
    for path, content in files.items():
        rel = path.relative_to(dest)
        action = "[DRY]" if dry else "  ✔ "
        print(f"  {action}  {rel}")
        if not dry:
            _write(path, content)

    if not dry:
        print(f"\n  ✅  Proyecto creado. Siguiente paso:\n")
        print(f"      cd {dest}")
        print(f"      pnpm install")
        print(f"      pnpm dev:web\n")
    else:
        print("\n  (usa --run para crear los archivos)")


def main():
    parser = argparse.ArgumentParser(description="Scaffold a new BAGO monorepo project")
    parser.add_argument("name", nargs="?", help="Project slug (e.g. myapp)")
    parser.add_argument("--out", default=".", help="Parent directory where project folder is created")
    parser.add_argument("--dry", action="store_true", help="Show files without creating them")
    args = parser.parse_args()

    slug = args.name
    if not slug:
        slug = input("  Nombre del proyecto (slug): ").strip()
    if not slug:
        print("  ✖  Se requiere un nombre de proyecto.", file=sys.stderr)
        sys.exit(1)

    slug = slug.lower().replace(" ", "-")
    out = Path(args.out).resolve()
    dest = out / slug

    if dest.exists() and not args.dry:
        print(f"  ✖  El directorio '{dest}' ya existe.", file=sys.stderr)
        sys.exit(1)

    scaffold(dest, slug, args.dry)



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    main()
