#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""creation_studio.py — Orquestador de capas arquitectónicas para BAGO Creation Mode.

Selecciona la capa de trabajo (frontend, backend, db, api, infra, todas) y
delega a creation_mode.py con filtros de archivo por capa.

Uso:
    python3 .bago/tools/creation_studio.py
    python3 .bago/tools/creation_studio.py --layer frontend --sub components
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.align import Align
    from rich.text import Text
except ImportError:
    print("ERROR: pip install rich", file=sys.stderr)
    sys.exit(1)

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.styles import Style
    from prompt_toolkit.formatted_text import HTML
    _HAS_PROMPT_TOOLKIT = True
except ImportError:
    PromptSession = None
    Style = None
    HTML = None
    _HAS_PROMPT_TOOLKIT = False

ROOT      = Path(__file__).resolve().parents[2]
BAGO_ROOT = ROOT / ".bago"
STATE     = BAGO_ROOT / "state"
TOOLS_DIR = BAGO_ROOT / "tools"

console = Console()

LAYERS: dict[str, dict] = {
    "frontend": {
        "label": "🎨  Frontend",
        "desc":  "UI, componentes, estilos, assets, hooks, rutas",
        "sub":   ["ui", "components", "styles", "assets", "hooks", "routes"],
        "patterns": [
            "*/frontend/**", "*/src/components/**", "*/src/ui/**", "*/src/hooks/**",
            "*/src/pages/**", "*/public/**", "*/styles/**", "*/assets/**",
            "*.css", "*.scss", "*.less", "*.tsx", "*.jsx", "*.vue", "*.svelte",
            "*.html", "*.htm",
        ],
    },
    "backend": {
        "label": "⚙️  Backend",
        "desc":  "API interna, servicios, modelos, workers, middleware",
        "sub":   ["api", "services", "models", "workers", "middleware", "infra"],
        "patterns": [
            "*/backend/**", "*/src/api/**", "*/src/services/**", "*/src/models/**",
            "*/src/workers/**", "*/src/middleware/**", "*/src/core/**",
            "*.py", "*.go", "*.rs", "*.java", "*.kt", "*.rb",
        ],
    },
    "db": {
        "label": "🗄️  Base de datos",
        "desc":  "Esquema, migraciones, seeds, queries, ORM",
        "sub":   ["schema", "migrations", "seeds", "queries"],
        "patterns": [
            "*/migrations/**", "*/seeds/**", "*/schema/**", "*/db/**",
            "*.sql", "*.prisma", "*.orm", "*.ddl",
        ],
    },
    "api": {
        "label": "📦  API / Contratos",
        "desc":  "REST, GraphQL, gRPC, OpenAPI, protobuf",
        "sub":   ["rest", "graphql", "grpc", "openapi"],
        "patterns": [
            "*/api/**", "*/openapi/**", "*/swagger/**", "*/proto/**",
            "*.yaml", "*.yml", "*.proto", "*.graphql", "*.gql", "*.wsdl",
        ],
    },
    "infra": {
        "label": "🔧  Infraestructura",
        "desc":  "Docker, K8s, CI/CD, terraform, nginx, variables de entorno",
        "sub":   ["docker", "k8s", "ci", "env", "terraform"],
        "patterns": [
            "Dockerfile*", "docker-compose*", "*/k8s/**", "*/.github/**",
            "*/terraform/**", "*/nginx/**", "*/scripts/**",
            "*.tf", "*.hcl", "*.yml", "*.yaml", ".env*",
        ],
    },
    "all": {
        "label": "🌐  Todas las capas",
        "desc":  "Vista unificada sin filtros",
        "sub":   [],
        "patterns": ["*"],
    },
}


def _save_layer(layer: str, sublayer: str) -> None:
    cfg_path = STATE / "creation_studio.json"
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
    except Exception:
        data = {}
    data["layer"] = layer
    data["sublayer"] = sublayer
    cfg_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _load_layer() -> tuple[str, str]:
    cfg_path = STATE / "creation_studio.json"
    if not cfg_path.exists():
        return "all", ""
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        return data.get("layer", "all"), data.get("sublayer", "")
    except Exception:
        return "all", ""


def _render_selector() -> None:
    console.print()
    t = Table(box=None, padding=(0, 0), show_header=False)
    t.add_column(style="grey82", overflow="fold")
    t.add_row("[bold white]BAGO Creation Studio[/bold white]")
    t.add_row("[grey50]Selecciona la capa arquitectónica de trabajo[/grey50]")
    t.add_row("")
    for key, meta in LAYERS.items():
        t.add_row(f"  [dodger_blue1]{key:<10}[/dodger_blue1]  {meta['label']}  [grey50]— {meta['desc']}[/grey50]")
        if meta["sub"]:
            t.add_row(f"       [grey50]subcapas: {', '.join(meta['sub'])}[/grey50]")
    t.add_row("")
    t.add_row("[grey50]Escribe el nombre de la capa (ej: frontend, backend, db, api, infra, all)[/grey50]")
    t.add_row("[grey50]O escribe 'capa.subcapa' (ej: frontend.components, backend.api)[/grey50]")
    console.print(t)


def _run_interactive() -> int:
    layer, sublayer = _load_layer()

    if _HAS_PROMPT_TOOLKIT:
        try:
            pt_style = Style.from_dict({"prompt": "#5555ff bold", "rprompt": "#666666"})
            session = PromptSession(style=pt_style)
        except Exception:
            session = None
    else:
        session = None

    while True:
        console.clear()
        _render_selector()
        hint = f"  [{layer}]" if layer else ""
        try:
            if session:
                raw = session.prompt(
                    HTML(f"<ansiblue><b>  capa{hint} › </b></ansiblue>"),
                    rprompt=HTML("<ansiblack>creation studio</ansiblack>"),
                ).strip()
            else:
                raw = input(f"  capa{hint} › ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[grey50]  Saliendo.[/grey50]")
            return 0

        if not raw:
            continue
        if raw in (":q", ":quit", "q", "quit", "exit"):
            return 0

        # Parse layer.sublayer
        parts = raw.split(".", 1)
        chosen_layer = parts[0].lower()
        chosen_sub = parts[1] if len(parts) > 1 else ""

        if chosen_layer not in LAYERS:
            console.print(f"[red]  Capa desconocida: {chosen_layer}[/red]")
            continue

        if chosen_sub and chosen_sub not in LAYERS[chosen_layer]["sub"]:
            console.print(f"[yellow]  Subcapa '{chosen_sub}' no definida; usando capa sin filtro de subcapa[/yellow]")
            chosen_sub = ""

        _save_layer(chosen_layer, chosen_sub)

        # Launch creation_mode
        create_script = TOOLS_DIR / "creation_mode.py"
        if create_script.exists():
            cmd = [sys.executable, "-m", "creation_mode", "--layer", chosen_layer]
            if chosen_sub:
                cmd += ["--sublayer", chosen_sub]
            console.print(f"\n[green]  Iniciando modo creación → {LAYERS[chosen_layer]['label']}[/green]")
            if chosen_sub:
                console.print(f"[grey50]  subcapa: {chosen_sub}[/grey50]")
            subprocess.run(cmd, cwd=str(TOOLS_DIR))
        else:
            console.print(f"[red]  No se encuentra creation_mode.py[/red]")

        # After creation_mode exits, loop back to selector
        layer, sublayer = _load_layer()


def main() -> int:
    p = argparse.ArgumentParser(description="BAGO Creation Studio — selector de capas")
    p.add_argument("--layer", choices=list(LAYERS.keys()), help="Capa arquitectónica")
    p.add_argument("--sublayer", default="", help="Subcapa (opcional)")
    p.add_argument("--once", action="store_true", help="Solo selector, no creation_mode")
    args = p.parse_args()

    if args.layer:
        _save_layer(args.layer, args.sublayer)
        if args.once:
            console.print(f"[green]Capa guardada: {args.layer}[/green]")
            return 0
        create_script = TOOLS_DIR / "creation_mode.py"
        if create_script.exists():
            cmd = [sys.executable, "-m", "creation_mode", "--layer", args.layer]
            if args.sublayer:
                cmd += ["--sublayer", args.sublayer]
            return subprocess.run(cmd, cwd=str(TOOLS_DIR)).returncode
        console.print("[red]creation_mode.py no encontrado[/red]")
        return 1

    return _run_interactive()


if __name__ == "__main__":
    sys.exit(main())
