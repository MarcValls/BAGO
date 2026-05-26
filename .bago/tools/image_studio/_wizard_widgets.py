from __future__ import annotations
import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

"""_wizard_widgets.py — Constructores de secciones UI para el Wizard de Contrato de Arte."""
import gradio as gr

from .contract import (
    STYLE_PRESETS, TONE_OPTIONS, PALETTE_SUGGESTIONS, CONTRACT_TEMPLATES,
    CHARACTER_ROLES, CANONICAL_ANIMATIONS, HUD_DEFAULTS, PROJECT_TYPES,
    list_contracts,
)
from .ai_assist import provider_label
from ._wizard_contract import (
    N_CHARS, N_SCENS, ANIM_NAMES, HUD_LABELS, HUD_DEFAULT_CHECKED, TPL_CHOICES,
)


def build_quickstart_section() -> dict:
    """Construye el acordeón '🚀 Inicio Rápido' y devuelve sus widgets."""
    with gr.Accordion("🚀  Inicio Rápido", open=True):
        gr.Markdown(
            "*Elige plantilla → describe tu proyecto → la IA rellena el contrato.  \n"
            "O carga uno ya guardado / importa un JSON editado con cualquier IA.*"
        )
        tpl_radio = gr.Radio(
            choices=TPL_CHOICES,
            value="platformer_2d",
            label="🚀  Tipo de proyecto",
        )
        qs_desc = gr.Textbox(
            label="✏️  Describe tu proyecto (2-3 líneas) — la IA hace el resto",
            lines=3,
            placeholder="Ej: plataformero 2D oscuro, protagonista es una bruja con magia de sombras, mundo subterráneo...",
        )
        with gr.Row():
            fill_ai_btn = gr.Button("✨ Crear con IA", variant="primary", scale=3)
            apply_tpl_btn = gr.Button("📋 Solo plantilla", variant="secondary", scale=2)
            dl_tpl_btn = gr.Button("🤖 Plantilla para IA (.json)", variant="secondary", scale=2)

        gr.Markdown("---")

        with gr.Row():
            saved_dd = gr.Dropdown(
                choices=["— nuevo —"] + list_contracts(),
                value="— nuevo —",
                label="📂  Cargar contrato guardado",
                allow_custom_value=False,
                scale=3,
            )
            load_saved_btn = gr.Button("📂 Cargar", scale=1)

        with gr.Row():
            import_file = gr.File(
                label="📁  Importar contrato JSON (editado con IA externa)",
                file_types=[".json"],
                scale=3,
            )
            import_btn = gr.Button("📥 Importar", scale=1)

        with gr.Row():
            with gr.Column(scale=4):
                ai_badge = gr.Markdown(f"*{provider_label()}*")
            check_ai_btn = gr.Button("🔍 Verificar IA", size="sm", scale=0)
        qs_status = gr.Markdown("")
        dl_tpl_file = gr.File(label="🤖 Plantilla IA", visible=False)

    return {
        "tpl_radio": tpl_radio,
        "qs_desc": qs_desc,
        "fill_ai_btn": fill_ai_btn,
        "apply_tpl_btn": apply_tpl_btn,
        "dl_tpl_btn": dl_tpl_btn,
        "saved_dd": saved_dd,
        "load_saved_btn": load_saved_btn,
        "import_file": import_file,
        "import_btn": import_btn,
        "check_ai_btn": check_ai_btn,
        "ai_badge": ai_badge,
        "qs_status": qs_status,
        "dl_tpl_file": dl_tpl_file,
    }


def build_project_section() -> dict:
    """Construye '1️⃣ Proyecto' y devuelve sus widgets."""
    with gr.Accordion("1️⃣  Proyecto", open=True):
        with gr.Row():
            f_proj_name = gr.Textbox(label="Nombre del proyecto", placeholder="BIANCA", scale=3)
            f_proj_type = gr.Dropdown(
                label="Tipo",
                choices=list(PROJECT_TYPES.keys()),
                value="Videojuego 2D",
                scale=2,
            )
            f_version = gr.Textbox(label="Versión", value="1.0", scale=1)
        f_description = gr.Textbox(
            label="Descripción breve",
            lines=2,
            placeholder="Plataformero 2D con mecánica de tejido de universos...",
        )

    return {
        "f_proj_name": f_proj_name,
        "f_proj_type": f_proj_type,
        "f_version": f_version,
        "f_description": f_description,
    }


def build_style_section() -> dict:
    """Construye '2️⃣ Estilo + Tono' y devuelve sus widgets."""
    with gr.Accordion("2️⃣  Estilo + Tono", open=True):
        with gr.Row():
            f_style = gr.Dropdown(
                label="Estilo visual",
                choices=[(f"{k} — {v['desc']}", k) for k, v in STYLE_PRESETS.items()],
                value="Pixel Art 32×32",
                scale=2,
            )
            f_tones = gr.CheckboxGroup(
                label="Tono (multi-selección)",
                choices=TONE_OPTIONS,
                value=["Colorido / Alegre"],
                scale=3,
            )
        f_suf = gr.Textbox(
            label="Sufijo de estilo (auto-generado · editable)",
            lines=2,
            interactive=True,
        )
        with gr.Row():
            f_quality_ref = gr.Textbox(
                label="Referencia de calidad",
                placeholder="ej: Celeste, Hollow Knight, Stardew Valley",
                scale=3,
            )
        f_principles = gr.Textbox(
            label="Principios visuales (uno por línea)",
            lines=4,
            placeholder=(
                "Consistencia de paleta en todos los assets\n"
                "Sombras con 2 tonos máximo\n"
                "Sin anti-aliasing en pixel art\n"
                "Silueta clara a tamaño de juego"
            ),
        )

    return {
        "f_style": f_style,
        "f_tones": f_tones,
        "f_suf": f_suf,
        "f_quality_ref": f_quality_ref,
        "f_principles": f_principles,
    }


def build_palette_section() -> tuple:
    """Construye '3️⃣ Paleta de Colores' y devuelve (pal_fields, pal_flat, f_palette_preset)."""
    with gr.Accordion("3️⃣  Paleta de Colores", open=True):
        f_palette_preset = gr.Dropdown(
            label="Cargar paleta sugerida",
            choices=["— Personalizada —"] + list(PALETTE_SUGGESTIONS.keys()),
            value="— Personalizada —",
        )
        pal_fields: list[tuple] = []
        for i in range(6):
            with gr.Row():
                p_hex = gr.ColorPicker(label=f"#{i+1}", scale=1)
                p_role = gr.Textbox(label="Rol", scale=2, placeholder="Primario")
                p_name = gr.Textbox(label="Nombre", scale=2, placeholder="Azul acción")
                p_use = gr.Textbox(label="Uso", scale=3, placeholder="Botones, CTAs")
            pal_fields.append((p_hex, p_role, p_name, p_use))

    pal_flat = [c for row in pal_fields for c in row]
    return pal_fields, pal_flat, f_palette_preset


def build_chars_section() -> tuple:
    """Construye '4️⃣ Personajes' y devuelve (char_groups, char_vis, add_char_btns)."""
    char_vis = [gr.State(i == 0) for i in range(N_CHARS)]

    with gr.Accordion("4️⃣  Personajes", open=True):
        char_groups = []
        for i in range(N_CHARS):
            with gr.Group(visible=(i == 0)) as cg:
                gr.Markdown(f"**Personaje {i+1}**")
                with gr.Row():
                    c_name = gr.Textbox(label="Nombre", scale=2, placeholder="Bianca")
                    c_role = gr.Dropdown(
                        label="Rol",
                        choices=CHARACTER_ROLES,
                        value=CHARACTER_ROLES[0] if i == 0 else CHARACTER_ROLES[min(i, len(CHARACTER_ROLES) - 1)],
                        scale=2,
                    )
                c_desc = gr.Textbox(label="Descripción visual", lines=2, placeholder="Joven guerrera, pelo rojo, armadura azul ligera...")
                with gr.Row():
                    c_ai_btn = gr.Button("✨ Generar Prompt IA", size="sm", scale=2)
                    c_anim_btn = gr.Button("🎬 Sugerir Animaciones", size="sm", scale=2)
                c_prompt = gr.Textbox(label="Prompt canónico", lines=3, interactive=True)
                c_anims = gr.CheckboxGroup(
                    label="Animaciones",
                    choices=ANIM_NAMES,
                    value=["idle", "walk", "jump_up", "attack_a", "hurt", "death"],
                )
                with gr.Row():
                    c_cw = gr.Number(label="Celda W px", value=32, minimum=8, scale=1)
                    c_ch = gr.Number(label="Celda H px", value=32, minimum=8, scale=1)
                    c_cols = gr.Number(label="Columnas", value=8, minimum=1, scale=1)
                    c_rows = gr.Number(label="Filas", value=8, minimum=1, scale=1)
                char_groups.append((cg, c_name, c_role, c_desc, c_ai_btn, c_anim_btn, c_prompt, c_anims, c_cw, c_ch, c_cols, c_rows))

        with gr.Row():
            add_char_btns = [
                gr.Button(f"+ Personaje {i+1}", size="sm", visible=(i > 0))
                for i in range(N_CHARS)
            ]

    return char_groups, char_vis, add_char_btns


def build_scens_section() -> tuple:
    """Construye '5️⃣ Escenarios' y devuelve (scen_groups, scen_vis, add_scen_btns)."""
    scen_vis = [gr.State(i == 0) for i in range(N_SCENS)]

    with gr.Accordion("5️⃣  Escenarios / Zonas", open=True):
        scen_groups = []
        for i in range(N_SCENS):
            with gr.Group(visible=(i == 0)) as sg:
                gr.Markdown(f"**Escenario {i+1}**")
                with gr.Row():
                    s_id = gr.Textbox(label="ID", scale=1, placeholder="zona_bosque")
                    s_name = gr.Textbox(label="Nombre", scale=2, placeholder="Bosque Oscuro")
                s_desc = gr.Textbox(label="Descripción", lines=2, placeholder="Bosque denso de noche, árboles retorcidos...")
                s_pal = gr.Textbox(label="Paleta dominante", placeholder="Verde oscuro, marrón tierra, negro")
                with gr.Row():
                    s_ai_bg = gr.Button("✨ Generar Prompt Fondo IA", size="sm", scale=2)
                    s_ai_tile = gr.Button("✨ Generar Prompt Tiles IA", size="sm", scale=2)
                s_bg_prompt = gr.Textbox(label="Prompt de fondo", lines=2, interactive=True)
                with gr.Row():
                    s_tw = gr.Number(label="Tile W px", value=32, minimum=8, scale=1)
                    s_th = gr.Number(label="Tile H px", value=32, minimum=8, scale=1)
                    s_var = gr.Number(label="Variantes", value=4, minimum=1, scale=1)
                s_tile_prompt = gr.Textbox(label="Prompt tiles", lines=2, interactive=True)
                scen_groups.append((sg, s_id, s_name, s_desc, s_pal, s_ai_bg, s_ai_tile, s_bg_prompt, s_tw, s_th, s_var, s_tile_prompt))

        with gr.Row():
            add_scen_btns = [
                gr.Button(f"+ Escenario {i+1}", size="sm", visible=(i > 0))
                for i in range(N_SCENS)
            ]

    return scen_groups, scen_vis, add_scen_btns


def build_hud_section() -> dict:
    """Construye '6️⃣ HUD' y devuelve sus widgets."""
    with gr.Accordion("6️⃣  HUD / UI Elements", open=True):
        f_hud_check = gr.CheckboxGroup(
            label="Selecciona los elementos que necesitas",
            choices=HUD_LABELS,
            value=HUD_DEFAULT_CHECKED,
        )
        ai_hud_btn = gr.Button("✨ Generar Prompts IA para seleccionados", size="sm")
        f_hud_custom = gr.Textbox(
            label="Elementos personalizados (JSON, opcional)",
            lines=3,
            placeholder='[{"id":"reloj","name":"Reloj","type":"icon","group":"hud","prompt":"","width":32,"height":32,"position":"top-center","states":"normal"}]',
        )
        hud_preview = gr.Textbox(label="Prompts generados", lines=6, interactive=True)

    return {
        "f_hud_check": f_hud_check,
        "ai_hud_btn": ai_hud_btn,
        "f_hud_custom": f_hud_custom,
        "hud_preview": hud_preview,
    }


def build_export_section() -> dict:
    """Construye '7️⃣ Calidad + Exportar' y devuelve sus widgets."""
    with gr.Accordion("7️⃣  Calidad + Exportar", open=True):
        with gr.Row():
            qa_tmpl_btn = gr.Button("📋 Plantilla por tipo de proyecto", size="sm", scale=2)
            qa_ai_btn = gr.Button("✨ Generar con IA", size="sm", scale=2)
        with gr.Row():
            f_accept = gr.Textbox(label="✅ Criterios de aceptación (uno por línea)", lines=5, placeholder="Paleta coherente\nTransparente en sprites...")
            f_reject = gr.Textbox(label="❌ Criterios de rechazo (uno por línea)", lines=5, placeholder="Colores fuera de paleta\nFondo blanco en sprites...")
        f_extra_notes = gr.Textbox(label="Notas adicionales", lines=3)

        gr.Markdown("---")
        count_md = gr.Markdown("*Rellena el contrato para ver la estimación de assets.*")

        with gr.Row():
            preview_btn = gr.Button("👁 Vista previa MD", variant="secondary", scale=2)
            estimate_btn = gr.Button("📊 Estimar assets", variant="secondary", scale=2)
            save_btn = gr.Button("💾 Guardar", variant="secondary", scale=1)
        with gr.Row():
            export_btn = gr.Button("📄 Exportar .md + .csv", variant="secondary", scale=2)
            full_pkg_btn = gr.Button("📦 Paquete completo", variant="primary", scale=2)
            ai_tpl_export = gr.Button("🤖 Plantilla IA (.json)", variant="secondary", scale=2)

        preview_out = gr.Markdown("")
        with gr.Row():
            out_md = gr.File(label="📄 Contrato .md", visible=False)
            out_csv = gr.File(label="📊 Batch básico .csv", visible=False)
            out_full_csv = gr.File(label="📦 Batch completo .csv", visible=False)
            out_manifest = gr.File(label="📋 Archivo adicional", visible=False)
        status_out = gr.Textbox(label="Estado", interactive=False, lines=2)

    return {
        "qa_tmpl_btn": qa_tmpl_btn,
        "qa_ai_btn": qa_ai_btn,
        "f_accept": f_accept,
        "f_reject": f_reject,
        "f_extra_notes": f_extra_notes,
        "count_md": count_md,
        "preview_btn": preview_btn,
        "estimate_btn": estimate_btn,
        "save_btn": save_btn,
        "export_btn": export_btn,
        "full_pkg_btn": full_pkg_btn,
        "ai_tpl_export": ai_tpl_export,
        "preview_out": preview_out,
        "out_md": out_md,
        "out_csv": out_csv,
        "out_full_csv": out_full_csv,
        "out_manifest": out_manifest,
        "status_out": status_out,
    }

