#!/usr/bin/env python3
"""
install_bago.py — Instalador autónomo de BAGO
Descarga la version especificada (o la mas reciente) desde send.cm
y la extrae en el directorio actual.

Uso:
  python install_bago.py                         # ultima version
  python install_bago.py --version v3.4.0        # version concreta
  python install_bago.py --from URL              # URL directa al zip
  python install_bago.py --manifest URL          # manifest alternativo
  python install_bago.py --list                  # listar versiones
"""

import argparse, json, os, sys, urllib.request, zipfile
from pathlib import Path

MANIFEST_URL = ""


def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode())


def download(url: str, dest: Path):
    print(f"  Descargando {url[:70]}...")
    with urllib.request.urlopen(url, timeout=300) as r, open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length", 0))
        done  = 0
        while chunk := r.read(65536):
            f.write(chunk)
            done += len(chunk)
            if total:
                pct = done * 100 // total
                print(f"\r  {pct:3d}% {done // 1048576} MB / {total // 1048576} MB", end="", flush=True)
    print()


def main():
    parser = argparse.ArgumentParser(description="Instalador BAGO desde send.cm")
    parser.add_argument("--manifest", default=MANIFEST_URL, help="URL del manifest JSON")
    parser.add_argument("--from",    dest="direct_url",    help="URL directa al zip")
    parser.add_argument("--version", default="",           help="Version a instalar (ej: v3.4.0)")
    parser.add_argument("--list",    action="store_true",  help="Listar versiones disponibles")
    parser.add_argument("--dest",    default=".",          help="Directorio de instalacion")
    args = parser.parse_args()

    # Manifest
    if not args.direct_url:
        if not args.manifest:
            print("ERROR: No hay manifest URL. Proporciona --manifest URL o --from URL")
            sys.exit(1)
        print(f"Leyendo manifest: {args.manifest}")
        try:
            manifest = fetch_json(args.manifest)
        except Exception as e:
            print(f"ERROR leyendo manifest: {e}"); sys.exit(1)

        versions = manifest.get("versions", [])
        if not versions:
            print("Sin versiones en el manifest."); sys.exit(1)

        if args.list:
            print("\nVersiones disponibles en BAGO cloud:")
            for v in versions:
                print(f"  {v['version']:12}  {v['date'][:10]}  {v['size_mb']:.1f} MB  {v['url']}")
            sys.exit(0)

        if args.version:
            entry = next((v for v in versions if v["version"] == args.version), None)
            if not entry:
                print(f"Version {args.version} no encontrada."); sys.exit(1)
        else:
            entry = versions[-1]
            print(f"Ultima version: {entry['version']} ({entry['date'][:10]})")

        download_url = entry["url"]
        fname        = f"bago_{entry['version']}.zip"
    else:
        download_url = args.direct_url
        fname        = "bago_download.zip"

    dest_dir = Path(args.dest).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    zip_path = dest_dir / fname

    print(f"\nInstalando BAGO en: {dest_dir}")
    download(download_url, zip_path)

    print("  Extrayendo...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest_dir)
    zip_path.unlink()

    print(f"\n✅  BAGO instalado en {dest_dir}")
    print("   Ejecuta:  python .bago/tools/bago_chat.py")


if __name__ == "__main__":
    main()
