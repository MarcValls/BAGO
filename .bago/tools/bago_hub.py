# -*- coding: utf-8 -*-
"""
bago_hub.py — Interfaz central de BAGO.

Lanzar con:
    python bago_hub.py
    python bago_hub.py --port <HUB_PORT>
    bago hub
"""
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import json
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime

import gradio as gr

from bago.ollama_runtime import DEFAULT_BAGO_HUB_PORT, env_port

# ── Rutas ──────────────────────────────────────────────────────────────────────
TOOLS_DIR  = Path(__file__).resolve().parent
BAGO_ROOT  = TOOLS_DIR.parent
STATE_DIR  = BAGO_ROOT / "state"
PACK_JSON  = BAGO_ROOT / "pack.json"
HUB_PORT   = env_port("BAGO_HUB_PORT", "BAGO_PORT", default=DEFAULT_BAGO_HUB_PORT)

_SAFE_MODULE_RE = re.compile(r"^[A-Za-z0-9_]+$")
_SAFE_ARG_RE = re.compile(r"^[A-Za-z0-9._:/=+-]+$")
IDEAS_JSON = BAGO_ROOT / "ideas_catalog.json"
GLOBAL_STATE = STATE_DIR / "global_state.json"
PYTHON     = sys.executable

sys.path.insert(0, str(TOOLS_DIR))

# ── Helpers de datos ──────────────────────────────────────────────────────────

def _load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text("utf-8", errors="replace"))
    except Exception:
        return default if default is not None else {}

def _pack() -> dict:
    return _load_json(PACK_JSON)

def _state() -> dict:
    return _load_json(GLOBAL_STATE)

def _ideas() -> dict:
    return _load_json(IDEAS_JSON)

def _registry() -> dict:
    try:
        from tool_registry import REGISTRY
        return REGISTRY
    except Exception:
        return {}

# ── Estilos ───────────────────────────────────────────────────────────────────

CSS = """
body { font-family: 'Segoe UI', monospace; }
.bago-title { font-size: 2rem; font-weight: 700; color: #4da8ff; }
.stat-card { background: #1a1a2e; border-radius: 8px; padding: 12px; margin: 4px; }
footer { display: none !important; }
.gradio-container { max-width: 1280px; }
.tool-output { font-family: monospace; font-size: 0.85rem; }
"""

THEME = gr.themes.Base(
    primary_hue="blue",
    secondary_hue="slate",
    neutral_hue="slate",
).set(
    body_background_fill="#0d1117",
    body_text_color="#c9d1d9",
    block_background_fill="#161b22",
    block_border_color="#30363d",
)

# ── Tab: Dashboard ─────────────────────────────────────────────────────────────

def _dashboard_md() -> str:
    pack   = _pack()
    state  = _state()
    reg    = _registry()

    version  = pack.get("version", "?")
    name     = pack.get("name", "BAGO")
    desc     = pack.get("description", "")
    health   = state.get("system_health", "?")
    sprint   = state.get("sprint_status", {})
    workflow = sprint.get("active_workflow", {})
    wf_title = workflow.get("title", "—") if isinstance(workflow, dict) else "—"
    wf_code  = workflow.get("code",  "")  if isinstance(workflow, dict) else ""
    task     = sprint.get("pending_w2_task", "—")
    n_tools  = len(reg)
    updated  = state.get("updated_at", state.get("last_updated", ""))

    health_icon = "🟢" if health == "ok" else ("🟡" if health == "warn" else "🔴")

    lines = [
        f"# 🅱 {name}  `v{version}`",
        f"> {desc}",
        "",
        "---",
        "## Estado del sistema",
        "",
        f"| | |",
        f"|---|---|",
        f"| **Salud** | {health_icon} `{health}` |",
        f"| **Workflow activo** | {wf_code} — {wf_title} |",
        f"| **Tarea pendiente** | {task} |",
        f"| **Herramientas registradas** | {n_tools} |",
        f"| **Última actualización** | {updated[:19] if updated else '—'} |",
        "",
    ]

    # Health report compacto si existe
    h_score = state.get("health_score") or {}
    if isinstance(h_score, dict) and h_score:
        score = h_score.get("score") or h_score.get("overall_score")
        if score is not None:
            lines += [f"**Health score:** `{score}%`", ""]

    # Notas/knowledge_base
    kb = state.get("knowledge_base") or state.get("notes")
    if kb:
        if isinstance(kb, list) and kb:
            lines += ["## Notas recientes", ""]
            for n in kb[:3]:
                lines.append(f"- {n}")
            lines.append("")
        elif isinstance(kb, str) and kb.strip():
            lines += ["## Notas", kb.strip()[:400], ""]

    return "\n".join(lines)


def _tab_dashboard() -> None:
    with gr.Column():
        md = gr.Markdown(_dashboard_md())
        with gr.Row():
            btn_refresh = gr.Button("🔄 Actualizar", size="sm", variant="secondary")
            btn_studio  = gr.Button("🎨 Abrir Image Studio", size="sm", variant="primary")
        status_msg = gr.Textbox(visible=False, interactive=False)

    def refresh():
        return _dashboard_md()

    def open_studio():
        # Lanza Image Studio en segundo plano
        subprocess.Popen(
            [PYTHON, str(TOOLS_DIR / "image_studio.py"), "--ui", "--port", "7861", "--no-browser"],
            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
        )
        return gr.update(visible=True, value="🎨 Image Studio lanzado en http://localhost:7861")

    btn_refresh.click(refresh, outputs=md)
    btn_studio.click(open_studio, outputs=status_msg)


# ── Tab: Herramientas ──────────────────────────────────────────────────────────

def _build_tools_table() -> list[list]:
    reg = _registry()
    rows = []
    for cmd, entry in sorted(reg.items()):
        module_file = TOOLS_DIR / f"{entry.module}.py"
        exists = "✅" if module_file.exists() else "❌"
        rows.append([exists, f"bago {cmd}", entry.description, entry.module])
    return rows


def _run_tool(cmd_row: list, args_str: str) -> str:
    """Ejecuta el comando seleccionado y devuelve su output."""
    if not cmd_row:
        return "⚠️ Selecciona una herramienta primero."
    # cmd_row puede ser una lista de celdas: [estado, cmd, desc, module]
    if isinstance(cmd_row, list):
        module_name = cmd_row[-1] if cmd_row else ""
    else:
        return "⚠️ Formato inesperado."

    reg = _registry()
    if (
        not isinstance(module_name, str)
        or not _SAFE_MODULE_RE.fullmatch(module_name)
        or module_name not in {entry.module for entry in reg.values()}
    ):
        return "❌ Herramienta no permitida."

    script = TOOLS_DIR / f"{module_name}.py"
    if not script.exists():
        return f"❌ Archivo no encontrado: {script}"

    try:
        parsed_args = shlex.split(args_str.strip()) if args_str.strip() else []
    except ValueError:
        return "❌ Argumentos inválidos."

    extra: list[str] = []
    for arg in parsed_args:
        if not arg:
            continue
        if arg.startswith("-"):
            if not _SAFE_ARG_RE.fullmatch(arg):
                return f"❌ Argumento no permitido: {arg}"
        else:
            if not _SAFE_ARG_RE.fullmatch(arg):
                return f"❌ Valor de argumento no permitido: {arg}"
        extra.append(arg)

    cmd = [PYTHON, str(script)] + extra

    try:
        result = subprocess.run(
            cmd,
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=30,
            cwd=str(BAGO_ROOT),
        )
        out = result.stdout + result.stderr
        return out.strip() or "(Sin output)"
    except subprocess.TimeoutExpired:
        return "⏱️ Timeout (30s). La herramienta tardó demasiado."
    except Exception as e:
        return f"❌ Error: {e}"


def _search_tools(query: str) -> list[list]:
    rows = _build_tools_table()
    if not query.strip():
        return rows
    q = query.lower()
    return [r for r in rows if q in r[1].lower() or q in r[2].lower()]


def _tab_tools() -> None:
    with gr.Column():
        gr.Markdown("### 🔧 Herramientas BAGO")
        with gr.Row():
            search = gr.Textbox(placeholder="Buscar herramienta...", label="", scale=4)
            btn_refresh = gr.Button("🔄", size="sm", scale=1)

        table = gr.Dataframe(
            value=_build_tools_table(),
                headers=["", "Comando", "Descripcion", "Modulo"],
            column_count=(4, "fixed"),
            interactive=False,
            label="Herramientas registradas",
        )
        with gr.Row():
            args_box = gr.Textbox(
                label="Argumentos extra (opcional)",
                placeholder='ej: --help  o  --list-types',
                scale=4,
            )
            btn_run = gr.Button("▶ Ejecutar", variant="primary", scale=1)

        output = gr.Textbox(
            label="Output",
            lines=12,
            interactive=False,
            elem_classes=["tool-output"],
        )

        selected_row: gr.State = gr.State([])

        def on_select(evt: gr.SelectData):
            rows = _build_tools_table()
            idx  = evt.index[0] if isinstance(evt.index, (list, tuple)) else evt.index
            if 0 <= idx < len(rows):
                return rows[idx]
            return []

        table.select(on_select, outputs=selected_row)
        search.change(_search_tools, inputs=search, outputs=table)
        btn_refresh.click(lambda: _build_tools_table(), outputs=table)
        btn_run.click(_run_tool, inputs=[selected_row, args_box], outputs=output)


# ── Tab: Ideas ────────────────────────────────────────────────────────────────

def _ideas_md() -> str:
    data = _ideas()
    if not data:
        return "_No se encontró ideas_catalog.json_"

    # Filtrar sólo las ideas (ignorar _comment, _guide)
    ideas = {k: v for k, v in data.items() if not k.startswith("_")}
    if not ideas:
        return "_Catálogo vacío_"

    lines = ["## 💡 Ideas BAGO", ""]
    for slot_key, slot in ideas.items():
        if not isinstance(slot, dict):
            continue
        slot_ideas = slot.get("ideas", [])
        slot_name  = slot.get("name", slot_key)
        if slot_ideas:
            lines.append(f"### {slot_name}")
            for idea in slot_ideas[:5]:  # máx 5 por slot
                title  = idea.get("title", idea.get("name", "?"))
                impact = idea.get("impact", "")
                effort = idea.get("effort", "")
                badge  = f" `{impact}/{effort}`" if impact and effort else ""
                lines.append(f"- **{title}**{badge}")
            if len(slot_ideas) > 5:
                lines.append(f"  _… y {len(slot_ideas)-5} más_")
            lines.append("")

    return "\n".join(lines)


def _tab_ideas() -> None:
    with gr.Column():
        md = gr.Markdown(_ideas_md())
        btn_refresh = gr.Button("🔄 Actualizar", size="sm", variant="secondary")
        btn_refresh.click(lambda: _ideas_md(), outputs=md)


# ── Tab: Estado (raw JSON viewer) ─────────────────────────────────────────────

def _state_md() -> str:
    state = _state()
    pack  = _pack()

    lines = [
        "## 📦 pack.json",
        "```json",
        json.dumps({k: v for k, v in pack.items() if k != "principles"}, indent=2, ensure_ascii=False)[:1200],
        "```",
        "",
        "## 🗂 global_state.json",
        "```json",
        json.dumps(state, indent=2, ensure_ascii=False, default=str)[:2000],
        "```",
    ]
    return "\n".join(lines)


def _tab_state() -> None:
    with gr.Column():
        md = gr.Markdown(_state_md())
        btn_refresh = gr.Button("🔄 Actualizar", size="sm", variant="secondary")
        btn_refresh.click(lambda: _state_md(), outputs=md)


# ── Tab: Image Studio (launcher) ──────────────────────────────────────────────

def _tab_image_studio() -> None:
    with gr.Column():
        gr.Markdown("""
## 🎨 Image Studio

Generador de assets visuales coherentes: sprites, botones, fondos, iconos, tiles, banners.

**Para lanzar la interfaz completa:**
""")
        with gr.Row():
            port_box = gr.Number(value=7861, label="Puerto", minimum=1024, maximum=65535, scale=1)
            btn_launch = gr.Button("🚀 Lanzar Image Studio UI", variant="primary", scale=3)

        status = gr.Textbox(label="Estado", interactive=False, lines=2)

        gr.Markdown("""
---
### Uso rápido (CLI)

```
bago image-studio --ui
bago image-studio --type sprite --project bianca
bago image-studio --batch assets.csv
```

### Formato CSV para batch

```csv
type,prompt,size,name,group
sprite,heroína anime con capa azul,sprite,hero,personajes
button,botón START brillante,button,btn_start,ui
bg,bosque mágico al atardecer,bg-small,forest_bg,escenarios
```
""")

        def launch_studio(port):
            port = int(port)
            script = TOOLS_DIR / "image_studio.py"
            if not script.exists():
                return f"❌ No encontrado: {script}"
            subprocess.Popen(
                [PYTHON, str(script), "--ui", "--port", str(port), "--no-browser"],
                creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
                cwd=str(BAGO_ROOT),
            )
            time.sleep(1)
            return f"✅ Image Studio lanzado en http://localhost:{port}\n(Abre esa URL en tu navegador)"

        btn_launch.click(launch_studio, inputs=port_box, outputs=status)


# ── Tab: Neural Bus ────────────────────────────────────────────────────────────

def _neural_status() -> str:
    """Poll Neural Bus /nodes and return a markdown summary."""
    import urllib.request
    import os
    port = int(os.environ.get("BAGO_NEURAL_PORT", 7865))
    url  = f"http://127.0.0.1:{port}/nodes"
    try:
        with urllib.request.urlopen(url, timeout=1) as r:
            data = json.loads(r.read())
        nodes = data if isinstance(data, list) else data.get("nodes", [])
        if not nodes:
            return f"🟢 Neural Bus activo en puerto {port} — sin nodos conectados aún."
        lines = [f"🟢 Neural Bus activo en puerto {port} — {len(nodes)} nodo(s):", ""]
        for n in nodes:
            if isinstance(n, dict):
                nid  = n.get("id", n.get("node_id", "?"))
                tags = ", ".join(n.get("tags", [])) or "—"
                ts   = n.get("last_seen", n.get("registered_at", ""))[:19] if n.get("last_seen") or n.get("registered_at") else ""
                lines.append(f"| `{nid}` | tags: {tags} | {ts} |")
            else:
                lines.append(f"- `{n}`")
        return "\n".join(lines)
    except Exception as e:
        return f"🔴 Neural Bus no responde en puerto {port}  _(bago neural start)_\n\n`{e}`"


def _neural_map() -> str:
    """Fetch /map from Neural Bus and return mermaid diagram."""
    import urllib.request
    import os
    port = int(os.environ.get("BAGO_NEURAL_PORT", 7865))
    url  = f"http://127.0.0.1:{port}/map"
    try:
        with urllib.request.urlopen(url, timeout=1) as r:
            data = json.loads(r.read())
        edges = data.get("edges", [])
        nodes = data.get("nodes", [])
        if not edges and not nodes:
            return "```mermaid\ngraph LR\n    A[No hay nodos registrados]\n```"
        lines = ["```mermaid", "graph LR"]
        for n in nodes:
            nid = (n.get("id") or n) if isinstance(n, dict) else n
            lines.append(f'    {nid}["{nid}"]')
        for e in edges:
            if isinstance(e, (list, tuple)) and len(e) >= 2:
                lines.append(f"    {e[0]} --> {e[1]}")
            elif isinstance(e, dict):
                src = e.get("from") or e.get("source", "?")
                dst = e.get("to")   or e.get("target", "?")
                lbl = e.get("topic", "")
                if lbl:
                    lines.append(f"    {src} -->|{lbl}| {dst}")
                else:
                    lines.append(f"    {src} --> {dst}")
        lines.append("```")
        return "\n".join(lines)
    except Exception:
        return "```mermaid\ngraph LR\n    A[Bus offline]\n```"


def _tab_neural() -> None:
    """Gradio tab: Neural Bus live monitor."""
    import os
    with gr.Column():
        gr.Markdown("## 🧠 Neural Bus\nMonitor en tiempo real del bus de mensajes inter-agente.")

        with gr.Row():
            port_label = gr.Textbox(
                value=f"Puerto: {os.environ.get('BAGO_NEURAL_PORT', '7865')}",
                interactive=False, label="Configuración", scale=2
            )
            btn_start  = gr.Button("▶ Iniciar Neural Bus", variant="primary", scale=2)
            btn_stop   = gr.Button("⏹ Detener", variant="secondary", scale=1)
            btn_refresh = gr.Button("🔄 Actualizar", scale=1)

        status_md = gr.Markdown(_neural_status())
        map_md    = gr.Markdown(_neural_map())
        log_box   = gr.Textbox(label="Resultado", interactive=False, lines=4, visible=False)

        def do_start():
            script = TOOLS_DIR / "bago_neural.py"
            if not script.exists():
                return gr.update(visible=True, value="❌ bago_neural.py no encontrado"), _neural_status(), _neural_map()
            subprocess.Popen(
                [PYTHON, str(script), "start"],
                creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
                cwd=str(BAGO_ROOT),
            )
            time.sleep(1.5)
            return gr.update(visible=True, value="▶ Neural Bus iniciado en segundo plano"), _neural_status(), _neural_map()

        def do_stop():
            script = TOOLS_DIR / "bago_neural.py"
            if not script.exists():
                return gr.update(visible=True, value="❌ bago_neural.py no encontrado"), _neural_status()
            result = subprocess.run([PYTHON, str(script), "stop"], capture_output=True, text=True, cwd=str(BAGO_ROOT))
            out = result.stdout.strip() or result.stderr.strip() or "Señal de parada enviada."
            return gr.update(visible=True, value=out), _neural_status()

        def do_refresh():
            return _neural_status(), _neural_map()

        btn_start.click(do_start, outputs=[log_box, status_md, map_md])
        btn_stop.click(do_stop, outputs=[log_box, status_md])
        btn_refresh.click(do_refresh, outputs=[status_md, map_md])


# ── App principal ─────────────────────────────────────────────────────────────

def build_app() -> gr.Blocks:
    pack = _pack()
    title = f"BAGO Hub — {pack.get('name','BAGO')} v{pack.get('version','?')}"

    with gr.Blocks(title=title) as app:
        gr.Markdown(f"<div class='bago-title'>🅱 BAGO Hub</div> <sub>v{pack.get('version','?')} — {pack.get('description','')}</sub>")

        with gr.Tabs():
            with gr.TabItem("🏠 Dashboard"):
                _tab_dashboard()
            with gr.TabItem("🔧 Herramientas"):
                _tab_tools()
            with gr.TabItem("🎨 Image Studio"):
                _tab_image_studio()
            with gr.TabItem("🧠 Neural Bus"):
                _tab_neural()
            with gr.TabItem("💡 Ideas"):
                _tab_ideas()
            with gr.TabItem("📊 Estado"):
                _tab_state()

    return app


def launch(port: int = HUB_PORT, open_browser: bool = True, share: bool = False) -> None:
    app = build_app()
    app.launch(
        server_port=port,
        inbrowser=open_browser,
        share=share,
        theme=THEME,
        css=CSS,
    )


# ── CLI ───────────────────────────────────────────────────────────────────────



def run_tests() -> int:
    """Self-test stub: verify module imports and key symbols exist."""
    results = []
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_test_mod", __file__)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        results.append(("import", True, "module loads OK"))
    except Exception as e:
        results.append(("import", False, str(e)))

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, detail in results:
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {name}: {detail}")
    print(f"\n  {passed}/{total} tests passed")
    return 0 if passed == total else 1

if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(run_tests())
    import argparse
    ap = argparse.ArgumentParser(description="BAGO Hub — interfaz central")
    ap.add_argument("--port",       type=int, default=HUB_PORT)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--share",      action="store_true")
    args = ap.parse_args()

    print(f"🅱  BAGO Hub → http://localhost:{args.port}")
    launch(port=args.port, open_browser=not args.no_browser, share=args.share)