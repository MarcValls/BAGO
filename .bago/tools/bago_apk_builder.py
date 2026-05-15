#!/usr/bin/env python3
"""BAGO APK Builder — Genera APK desde PWA usando Bubblewrap (TWA)

Uso:
    python bago_apk_builder.py --url https://mi-pwa.com --name "Mi App" --package com.example.app
    python bago_apk_builder.py --manifest https://mi-pwa.com/manifest.json

Requiere:
    - Node.js + npm
    - Bubblewrap CLI: npm install -g @bubblewrap/cli
    - JDK 17 (Bubblewrap puede auto-instalar)
    - Android SDK (Bubblewrap puede auto-instalar)

Salida:
    - APK firmado listo para Google Play o sideload
    - AAB (Android App Bundle) para Play Store
"""
import argparse, json, os, subprocess, sys, tempfile, shutil
from pathlib import Path

BAGO_ROOT = Path(__file__).resolve().parents[2]
BUILD_DIR = BAGO_ROOT / ".bago" / "builds"
BUILD_DIR.mkdir(parents=True, exist_ok=True)

def run(cmd, cwd=None, timeout=300):
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=timeout)
    if result.returncode != 0:
        print(f"  ERR: {result.stderr}")
    return result

def check_deps():
    deps = {}
    for name, cmd in [("node", ["node", "--version"]), ("npm", ["npm", "--version"])]:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            deps[name] = r.stdout.strip() if r.returncode == 0 else None
        except Exception:
            deps[name] = None
    return deps

def build_apk(url: str, name: str, package_id: str, output_dir: Path):
    deps = check_deps()
    if not deps.get("node"):
        print("❌ Node.js no encontrado. Instala desde https://nodejs.org")
        return 1
    if not deps.get("npm"):
        print("❌ npm no encontrado")
        return 1

    # Verificar/instalar bubblewrap
    try:
        subprocess.run(["bubblewrap", "--version"], capture_output=True, timeout=5)
    except FileNotFoundError:
        print("📦 Instalando Bubblewrap CLI...")
        r = run(["npm", "install", "-g", "@bubblewrap/cli"])
        if r.returncode != 0:
            print("❌ Fallo instalacion Bubblewrap")
            return 1

    workdir = output_dir / f"twa_{package_id.replace('.', '_')}"
    workdir.mkdir(parents=True, exist_ok=True)

    print(f"🚀 Iniciando TWA build...")
    print(f"   URL: {url}")
    print(f"   Nombre: {name}")
    print(f"   Package: {package_id}")
    print(f"   Workdir: {workdir}")

    # bubblewrap init
    init_cmd = [
        "bubblewrap", "init",
        "--manifest", url if url.endswith("/manifest.json") else f"{url.rstrip('/')}/manifest.json",
        "--directory", str(workdir),
    ]
    # Si no hay manifest.json, generar uno basico
    manifest_url = url if url.endswith("/manifest.json") else f"{url.rstrip('/')}/manifest.json"
    r = run(init_cmd)
    if r.returncode != 0:
        print("⚠️  init fallo, intentando con manifest generado...")
        manifest = {
            "name": name,
            "short_name": name[:12],
            "start_url": "/",
            "display": "standalone",
            "background_color": "#0c0c0c",
            "theme_color": "#00d4aa",
            "icons": [{"src": "/icon-192.png", "sizes": "192x192"}]
        }
        manifest_path = workdir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        init_cmd = [
            "bubblewrap", "init",
            "--manifest", str(manifest_path),
            "--directory", str(workdir),
        ]
        r = run(init_cmd)
        if r.returncode != 0:
            print("❌ init fallo definitivamente")
            return 1

    # build
    build_cmd = ["bubblewrap", "build", "--directory", str(workdir)]
    r = run(build_cmd, cwd=workdir)
    if r.returncode != 0:
        print("❌ Build fallo")
        return 1

    # Buscar APK generado
    apks = list(workdir.glob("*.apk")) + list(workdir.glob("app/build/outputs/apk/**/*.apk"))
    aabs = list(workdir.glob("*.aab")) + list(workdir.glob("app/build/outputs/bundle/**/*.aab"))

    print(f"✅ Build completo")
    for apk in apks[:3]:
        print(f"   APK: {apk}")
    for aab in aabs[:3]:
        print(f"   AAB: {aab}")

    return 0

def main():
    parser = argparse.ArgumentParser(description="BAGO APK Builder (TWA)")
    parser.add_argument("--url", required=True, help="URL de la PWA")
    parser.add_argument("--name", default="BAGO App", help="Nombre de la app")
    parser.add_argument("--package", default="dev.bago.app", help="Package ID Android")
    parser.add_argument("--out", default=str(BUILD_DIR), help="Directorio de salida")
    args = parser.parse_args()

    return build_apk(args.url, args.name, args.package, Path(args.out))

if __name__ == "__main__":
    raise SystemExit(main())
