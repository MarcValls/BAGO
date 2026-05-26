#!/usr/bin/env python3
"""BAGO Electron Packager — Empaqueta web app como app de escritorio

Uso:
    python bago_electron_packager.py --url https://mi-app.com --name "Mi App"
    python bago_electron_packager.py --dir ./static --name "BAGO Music"

Requiere:
    - Node.js + npm
    - electron-builder o electron-packager (auto-instala)

Salida:
    - .exe (Windows)
    - .dmg (macOS, si se build en Mac)
    - .AppImage / .deb (Linux)
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

import argparse, json, os, shutil, subprocess, sys
from pathlib import Path

BAGO_ROOT = Path(__file__).resolve().parents[2]
BUILD_DIR = BAGO_ROOT / ".bago" / "builds"
BUILD_DIR.mkdir(parents=True, exist_ok=True)

def run(cmd, cwd=None, timeout=300):
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout)
    if result.returncode != 0:
        print(f"  ERR: {result.stderr[:500]}")
    return result

def scaffold_electron_project(name: str, url: str, output_dir: Path):
    proj = output_dir / f"electron_{name.lower().replace(' ', '_')}"
    if proj.exists():
        shutil.rmtree(proj)
    proj.mkdir(parents=True)

    # package.json
    pkg = {
        "name": name.lower().replace(" ", "-"),
        "version": "1.0.0",
        "description": f"{name} — packaged by BAGO",
        "main": "main.js",
        "scripts": {
            "start": "electron .",
            "dist": "electron-builder",
            "dist:dir": "electron-builder --dir"
        },
        "devDependencies": {
            "electron": "^30.0.0",
            "electron-builder": "^24.0.0"
        },
        "build": {
            "appId": f"dev.bago.{name.lower().replace(' ', '.')}",
            "productName": name,
            "directories": {"output": "dist"},
            "files": ["main.js", "preload.js", "renderer/**/*"],
            "win": {"target": "nsis"},
            "mac": {"target": "dmg"},
            "linux": {"target": "AppImage"}
        }
    }
    (proj / "package.json").write_text(json.dumps(pkg, indent=2), encoding="utf-8")

    # main.js
    main_js = f"""const {{ app, BrowserWindow }} = require('electron');
const path = require('path');

function createWindow() {{
  const win = new BrowserWindow({{
    width: 1280,
    height: 800,
    webPreferences: {{
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }},
    title: '{name}',
    icon: path.join(__dirname, 'icon.png')
  }});

  win.loadURL('{url}');
}}

app.whenReady().then(createWindow);
app.on('window-all-closed', () => {{ if (process.platform !== 'darwin') app.quit(); }});
app.on('activate', () => {{ if (BrowserWindow.getAllWindows().length === 0) createWindow(); }});
"""
    (proj / "main.js").write_text(main_js, encoding="utf-8")

    # preload.js
    preload = """window.addEventListener('DOMContentLoaded', () => {
  console.log('BAGO Electron app loaded');
});
"""
    (proj / "preload.js").write_text(preload, encoding="utf-8")

    return proj

def build(project_dir: Path):
    print("📦 Instalando dependencias Electron...")
    r = run(["npm", "install"], cwd=project_dir)
    if r.returncode != 0:
        print("❌ npm install fallo")
        return 1

    print("🔨 Build con electron-builder...")
    r = run(["npm", "run", "dist:dir"], cwd=project_dir)
    if r.returncode != 0:
        print("❌ Build fallo")
        return 1

    dist = project_dir / "dist"
    print(f"✅ Build completo en: {dist}")
    for f in dist.rglob("*"):
        if f.is_file():
            print(f"   {f.relative_to(dist)}")
    return 0

def main():
    parser = argparse.ArgumentParser(description="BAGO Electron Packager")
    parser.add_argument("--url", required=True, help="URL de la web app o PWA")
    parser.add_argument("--name", default="BAGO App", help="Nombre de la app")
    parser.add_argument("--out", default=str(BUILD_DIR), help="Directorio de salida")
    args = parser.parse_args()

    proj = scaffold_electron_project(args.name, args.url, Path(args.out))
    return build(proj)

if __name__ == "__main__":
    raise SystemExit(main())
