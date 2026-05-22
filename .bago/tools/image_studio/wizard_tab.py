from __future__ import annotations
"""wizard_tab.py — Orquestador del Wizard de Contrato de Arte para Image Studio."""

import json
from pathlib import Path

import gradio as gr

from .contract import (
    CONTRACT_TEMPLATES,
    HUD_DEFAULTS,
    PALETTE_SUGGESTIONS,
    build_contract_md,
    build_style_suffix,
    estimate_asset_count,
    export_contract_files,
    export_project_package,
    export_template_json,
    get_style_defaults,
    list_contracts,
    load_contract,
    save_contract,
)
from .ai_assist import (
    generate_character_prompt,
    generate_full_contract,
    generate_hud_prompt,
    generate_quality_rules,
    generate_scenario_bg_prompt,
    generate_tileset_prompt,
    provider_label,
    suggest_animations,
)
from ._wizard_contract import (
    N_CHARS,
    N_SCENS,
    _assemble_contract,
    _load_contract_to_fields,
    _palette_updates,
    _write_download_file,
)
from ._wizard_widgets import (
    build_chars_section,
    build_export_section,
    build_hud_section,
    build_palette_section,
    build_project_section,
    build_quickstart_section,
    build_scens_section,
    build_style_section,
)


def build_wizard_tab() -> None:
    """Construye la pestaña del wizard dentro del contexto gr.Blocks activo."""
    gr.Markdown("## 📋 Contrato de Arte")

    quickstart = build_quickstart_section()
    project = build_project_section()
    style = build_style_section()
    _pal_fields, pal_flat, f_palette_preset = build_palette_section()
    char_groups, char_vis, add_char_btns = build_chars_section()
    scen_groups, scen_vis, add_scen_btns = build_scens_section()
    hud = build_hud_section()
    export = build_export_section()

    tpl_radio = quickstart["tpl_radio"]
    qs_desc = quickstart["qs_desc"]
    fill_ai_btn = quickstart["fill_ai_btn"]
    apply_tpl_btn = quickstart["apply_tpl_btn"]
    dl_tpl_btn = quickstart["dl_tpl_btn"]
    saved_dd = quickstart["saved_dd"]
    load_saved_btn = quickstart["load_saved_btn"]
    import_file = quickstart["import_file"]
    import_btn = quickstart["import_btn"]
    check_ai_btn = quickstart["check_ai_btn"]
    ai_badge = quickstart["ai_badge"]
    qs_status = quickstart["qs_status"]
    dl_tpl_file = quickstart["dl_tpl_file"]

    f_proj_name = project["f_proj_name"]
    f_proj_type = project["f_proj_type"]
    f_version = project["f_version"]
    f_description = project["f_description"]

    f_style = style["f_style"]
    f_tones = style["f_tones"]
    f_suf = style["f_suf"]
    f_quality_ref = style["f_quality_ref"]
    f_principles = style["f_principles"]

    f_hud_check = hud["f_hud_check"]
    ai_hud_btn = hud["ai_hud_btn"]
    f_hud_custom = hud["f_hud_custom"]
    hud_preview = hud["hud_preview"]

    qa_tmpl_btn = export["qa_tmpl_btn"]
    qa_ai_btn = export["qa_ai_btn"]
    f_accept = export["f_accept"]
    f_reject = export["f_reject"]
    f_extra_notes = export["f_extra_notes"]
    count_md = export["count_md"]
    preview_btn = export["preview_btn"]
    estimate_btn = export["estimate_btn"]
    save_btn = export["save_btn"]
    export_btn = export["export_btn"]
    full_pkg_btn = export["full_pkg_btn"]
    ai_tpl_export = export["ai_tpl_export"]
    preview_out = export["preview_out"]
    out_md = export["out_md"]
    out_csv = export["out_csv"]
    out_full_csv = export["out_full_csv"]
    out_manifest = export["out_manifest"]
    status_out = export["status_out"]

    char_collect_inputs = []
    for i in range(N_CHARS):
        _, c_name, c_role, c_desc, _, _, c_prompt, c_anims, c_cw, c_ch, c_cols, c_rows = char_groups[i]
        char_collect_inputs += [c_name, c_role, c_desc, c_prompt, c_anims, c_cw, c_ch, c_cols, c_rows]
    char_vis_inputs = list(char_vis)

    scen_collect_inputs = []
    for i in range(N_SCENS):
        _, s_id, s_name, s_desc, s_pal, _, _, s_bg_prompt, s_tw, s_th, s_var, s_tile_prompt = scen_groups[i]
        scen_collect_inputs += [s_id, s_name, s_desc, s_pal, s_bg_prompt, s_tile_prompt, s_tw, s_th, s_var]
    scen_vis_inputs = list(scen_vis)

    all_inputs = (
        [f_proj_name, f_proj_type, f_version, f_description, f_style, f_tones, f_suf, f_quality_ref, f_principles]
        + pal_flat
        + char_collect_inputs + char_vis_inputs
        + scen_collect_inputs + scen_vis_inputs
        + [f_hud_check, f_hud_custom, f_accept, f_reject, f_extra_notes]
    )
    fill_all_outputs = (
        all_inputs
        + [char_groups[i][0] for i in range(N_CHARS)]
        + [scen_groups[i][0] for i in range(N_SCENS)]
    )

    check_ai_btn.click(fn=lambda: f"*{provider_label()}*", outputs=ai_badge)

    def _template_defaults_data(tpl_key: str) -> tuple[dict, str]:
        tpl = CONTRACT_TEMPLATES.get(tpl_key, CONTRACT_TEMPLATES.get("blank", {}))
        defs = tpl.get("defaults", {})
        char_defs = defs.get("char_defaults", [])
        scen_count = defs.get("scen_count", 1)
        palette = PALETTE_SUGGESTIONS.get(defs.get("palette_preset", "Videojuego 2D"), [])
        style_name = defs.get("art_style", "Pixel Art 32×32")
        tones = defs.get("tones", [])
        data = {
            "project_type": defs.get("project_type", "Videojuego 2D"),
            "style_name": style_name,
            "visual_tone": ", ".join(tones),
            "style_prompt_suffix": build_style_suffix(style_name, tones),
            "quality_ref": defs.get("quality_ref", ""),
            "principles": defs.get("principles", ""),
            "accept_rules": defs.get("accept_rules", ""),
            "reject_rules": defs.get("reject_rules", ""),
            "palette": palette,
            "characters": [
                {
                    "name": f"Personaje {i+1}",
                    "role": cd["role"],
                    "description": "",
                    "prompt": "",
                    "animations": [{"name": a} if isinstance(a, str) else a for a in cd.get("anims", ["idle"])],
                    "sprite_sheet": {"cell_w": cd["cw"], "cell_h": cd["ch"], "cols": cd["cols"], "rows": cd["rows"]},
                }
                for i, cd in enumerate(char_defs)
            ],
            "scenarios": [
                {
                    "id": f"zona_{i+1}",
                    "name": f"Escenario {i+1}",
                    "description": "",
                    "palette_notes": "",
                    "bg_prompt": "",
                    "tileset": {"tile_w": defs.get("tile_w", 32), "tile_h": defs.get("tile_h", 32), "variants": 2, "prompt": ""},
                }
                for i in range(scen_count)
            ],
            "ui_elements": [
                {
                    "id": hid,
                    "name": hid.replace("_", " ").title(),
                    "type": "icon",
                    "group": "hud",
                    "width": 32,
                    "height": 32,
                    "states": "normal",
                    "prompt": "",
                }
                for hid in defs.get("hud_ids", [])
            ],
        }
        return data, tpl.get("label", tpl_key)

    def _apply_template(tpl_key):
        data, label = _template_defaults_data(tpl_key)
        return _load_contract_to_fields(data) + [f"✅ Plantilla '{label}' aplicada."]

    apply_tpl_btn.click(_apply_template, inputs=[tpl_radio], outputs=fill_all_outputs + [qs_status])

    def _fill_with_ai(tpl_key, desc, style_name):
        if not desc or not str(desc).strip():
            return [gr.update()] * len(fill_all_outputs) + ["⚠️ Escribe una descripción primero."]
        tpl_data, label = _template_defaults_data(tpl_key)
        try:
            tpl = CONTRACT_TEMPLATES.get(tpl_key, CONTRACT_TEMPLATES.get("blank", {}))
            defs = tpl.get("defaults", {})
            ai_data = generate_full_contract(str(desc).strip(), tpl_key, style_name or defs.get("art_style", "Pixel Art 32×32"))
            if ai_data.get("palette"):
                tpl_data["palette"] = ai_data["palette"]
            tpl_data["project_name"] = ai_data.get("project_name", "")
            tpl_data["description"] = ai_data.get("description", desc)
            tpl_data["quality_ref"] = ai_data.get("quality_ref", tpl_data.get("quality_ref", ""))
            tpl_data["principles"] = ai_data.get("principles", tpl_data.get("principles", ""))
            tpl_data["accept_rules"] = ai_data.get("accept_rules", tpl_data.get("accept_rules", ""))
            tpl_data["reject_rules"] = ai_data.get("reject_rules", tpl_data.get("reject_rules", ""))

            char_defs = defs.get("char_defaults", [{"role": "Protagonista", "anims": ["idle"], "cw": 32, "ch": 32, "cols": 8, "rows": 8}])
            ai_chars = ai_data.get("characters", [])
            characters = []
            for i, cd in enumerate(char_defs):
                ac = ai_chars[i] if i < len(ai_chars) else {}
                characters.append({
                    "name": ac.get("name", f"Personaje {i+1}"),
                    "role": ac.get("role", cd.get("role", "Protagonista")),
                    "description": ac.get("description", ""),
                    "prompt": ac.get("prompt", ""),
                    "animations": [{"name": a} if isinstance(a, str) else a for a in cd.get("anims", ["idle"])],
                    "sprite_sheet": {
                        "cell_w": cd.get("cw", 32), "cell_h": cd.get("ch", 32),
                        "cols": cd.get("cols", 8), "rows": cd.get("rows", 8),
                    },
                })
            tpl_data["characters"] = characters

            scen_count = defs.get("scen_count", len(tpl_data.get("scenarios", [])) or 2)
            ai_scens = ai_data.get("scenarios", [])
            scenarios = []
            for i in range(scen_count):
                sc = ai_scens[i] if i < len(ai_scens) else {}
                ts_src = sc.get("tileset", {}) if isinstance(sc, dict) else {}
                scenarios.append({
                    "id": sc.get("id", f"zona_{i+1}"),
                    "name": sc.get("name", f"Escenario {i+1}"),
                    "description": sc.get("description", ""),
                    "palette_notes": sc.get("palette_notes", ""),
                    "bg_prompt": sc.get("bg_prompt", ""),
                    "tileset": {
                        "tile_w": defs.get("tile_w", 32),
                        "tile_h": defs.get("tile_h", 32),
                        "variants": 2,
                        "prompt": ts_src.get("prompt", ""),
                    },
                })
            tpl_data["scenarios"] = scenarios
            status = f"✅ Contrato generado por IA — {len(characters)} personajes, {len(scenarios)} escenarios."
        except Exception as e:
            tpl_data["description"] = desc
            status = f"⚠️ IA no disponible, plantilla '{label}' aplicada. ({e})"
        return _load_contract_to_fields(tpl_data) + [status]

    fill_ai_btn.click(_fill_with_ai, inputs=[tpl_radio, qs_desc, f_style], outputs=fill_all_outputs + [qs_status])

    def _load_saved(name):
        if not name or name == "— nuevo —":
            return [gr.update()] * len(fill_all_outputs) + ["⚠️ Selecciona un contrato."]
        data = load_contract(name)
        if not data:
            return [gr.update()] * len(fill_all_outputs) + [f"❌ No se encontró: {name}"]
        return _load_contract_to_fields(data) + [f"✅ Contrato '{name}' cargado."]

    load_saved_btn.click(_load_saved, inputs=[saved_dd], outputs=fill_all_outputs + [qs_status])

    def _import_json(file):
        if file is None:
            return [gr.update()] * len(fill_all_outputs) + ["⚠️ No se subió ningún archivo."]
        try:
            raw = Path(file.name).read_text("utf-8")
            data = json.loads(raw)
            data = {k: v for k, v in data.items() if not str(k).startswith("_")}
            return _load_contract_to_fields(data) + ["✅ Contrato importado correctamente."]
        except Exception as e:
            return [gr.update()] * len(fill_all_outputs) + [f"❌ Error al importar: {e}"]

    import_btn.click(_import_json, inputs=[import_file], outputs=fill_all_outputs + [qs_status])

    def _dl_template(tpl_key):
        try:
            json_str = export_template_json(tpl_key or "blank")
            file_path = _write_download_file(f"{tpl_key or 'blank'}_template.json", json_str)
            return gr.update(value=file_path, visible=True), "✅ Plantilla lista — descarga y pégala en cualquier IA."
        except Exception as e:
            return gr.update(visible=False), f"❌ Error: {e}"

    dl_tpl_btn.click(_dl_template, inputs=[tpl_radio], outputs=[dl_tpl_file, qs_status])

    def _on_style_tone(style_name, tones):
        suf = build_style_suffix(style_name, tones or [])
        defs = get_style_defaults(style_name)
        cw, ch_val = defs["cell_w"], defs["cell_h"]
        updates = [gr.update(value=suf)]
        for _ in range(N_CHARS):
            updates += [gr.update(value=cw), gr.update(value=ch_val)]
        return updates

    all_cw_ch = []
    for i in range(N_CHARS):
        all_cw_ch += [char_groups[i][8], char_groups[i][9]]

    f_style.change(_on_style_tone, [f_style, f_tones], [f_suf] + all_cw_ch)
    f_tones.change(_on_style_tone, [f_style, f_tones], [f_suf] + all_cw_ch)
    f_palette_preset.change(fn=_palette_updates, inputs=f_palette_preset, outputs=pal_flat)

    for i in range(1, N_CHARS):
        def _show_char(i=i):
            return gr.update(visible=True), True
        add_char_btns[i].click(fn=_show_char, outputs=[char_groups[i][0], char_vis[i]])

    for i in range(N_CHARS):
        _, c_name, c_role, c_desc, c_ai_btn, c_anim_btn, c_prompt, c_anims, *_rest = char_groups[i]

        def _gen_char_prompt(name, role, desc, suf, i=i):
            if not name or not str(name).strip():
                return gr.update(value="⚠️ Escribe el nombre primero.")
            return gr.update(value=generate_character_prompt(name, role, desc or "", suf or ""))

        c_ai_btn.click(_gen_char_prompt, [c_name, c_role, c_desc, f_suf], c_prompt)

        def _suggest_anims(role, i=i):
            return gr.update(value=[a["name"] for a in suggest_animations(role or "")])

        c_anim_btn.click(_suggest_anims, [c_role], c_anims)

    for i in range(1, N_SCENS):
        def _show_scen(i=i):
            return gr.update(visible=True), True
        add_scen_btns[i].click(fn=_show_scen, outputs=[scen_groups[i][0], scen_vis[i]])

    for i in range(N_SCENS):
        _, _s_id, s_name, s_desc, s_pal, s_ai_bg, s_ai_tile, s_bg_prompt, s_tw, s_th, _s_var, s_tile_prompt = scen_groups[i]

        def _gen_bg(name, desc, pal, suf, i=i):
            if not name or not str(name).strip():
                return gr.update(value="⚠️ Escribe el nombre primero.")
            return gr.update(value=generate_scenario_bg_prompt(name, desc or "", pal or "", suf or ""))

        s_ai_bg.click(_gen_bg, [s_name, s_desc, s_pal, f_suf], s_bg_prompt)

        def _gen_tile(name, desc, tw, th, suf, i=i):
            if not name or not str(name).strip():
                return gr.update(value="⚠️ Escribe el nombre primero.")
            return gr.update(value=generate_tileset_prompt(name, desc or "", int(tw or 32), int(th or 32), suf or ""))

        s_ai_tile.click(_gen_tile, [s_name, s_desc, s_tw, s_th, f_suf], s_tile_prompt)

    def _gen_hud_prompts(selected_labels, suf):
        if not selected_labels:
            return gr.update(value="Selecciona elementos primero.")
        selected_ids = {lbl.split(" — ")[0] for lbl in selected_labels}
        lines = []
        for el in HUD_DEFAULTS:
            if el["id"] in selected_ids:
                prompt = generate_hud_prompt(
                    el["name"],
                    el.get("type", "icon"),
                    el.get("position", ""),
                    el.get("states", "normal"),
                    suf or "",
                )
                lines.append(f"# {el['id']}\n{prompt}")
        return gr.update(value="\n\n".join(lines))

    ai_hud_btn.click(_gen_hud_prompts, [f_hud_check, f_suf], hud_preview)

    def _qa_template(ptype, style_name):
        from .ai_assist import _quality_templates
        accept, reject = _quality_templates(ptype or "Videojuego 2D", style_name or "")
        return gr.update(value=accept), gr.update(value=reject)

    qa_tmpl_btn.click(_qa_template, [f_proj_type, f_style], [f_accept, f_reject])

    def _qa_ai(ptype, style_name, description):
        accept, reject = generate_quality_rules(ptype or "", style_name or "", description or "")
        return gr.update(value=accept), gr.update(value=reject)

    qa_ai_btn.click(_qa_ai, [f_proj_type, f_style, f_description], [f_accept, f_reject])

    def _preview(*args):
        try:
            data = _assemble_contract(*args)
            return gr.update(value=build_contract_md(data)), gr.update(value="")
        except Exception as e:
            return gr.update(value=""), gr.update(value=f"Error: {e}")

    preview_btn.click(_preview, all_inputs, [preview_out, status_out])

    def _do_estimate(*args):
        try:
            data = _assemble_contract(*args)
            counts = estimate_asset_count(data)
            n = counts["total"]
            msg = (
                f"📊 **Estimación: ~{n} assets**  \n"
                f"🧑 sprites: **{counts['sprites']}** · "
                f"🖼 fondos: **{counts['fondos']}** · "
                f"🧱 tiles: **{counts['tiles']}** · "
                f"🎮 HUD: **{counts['hud']}** · "
                f"📺 menús: **{counts['menus']}** · "
                f"✨ VFX: **{counts['vfx']}**"
            )
            return gr.update(value=msg), gr.update(value="")
        except Exception as e:
            return gr.update(), gr.update(value=f"Error: {e}")

    estimate_btn.click(_do_estimate, all_inputs, [count_md, status_out])

    def _export(*args):
        try:
            data = _assemble_contract(*args)
            if not data.get("project_name"):
                return gr.update(visible=False), gr.update(visible=False), gr.update(value="⚠️ Escribe el nombre del proyecto primero.")
            md_path, csv_path = export_contract_files(data)
            return (
                gr.update(value=str(md_path), visible=True),
                gr.update(value=str(csv_path), visible=True),
                gr.update(value=f"✅ Exportado: {md_path.name} · {csv_path.name}"),
            )
        except Exception as e:
            return gr.update(visible=False), gr.update(visible=False), gr.update(value=f"❌ Error: {e}")

    export_btn.click(_export, all_inputs, [out_md, out_csv, status_out])

    def _export_full(*args):
        try:
            data = _assemble_contract(*args)
            if not data.get("project_name"):
                return (
                    gr.update(visible=False), gr.update(visible=False),
                    gr.update(visible=False), gr.update(visible=False),
                    gr.update(value="⚠️ Escribe el nombre del proyecto primero."),
                )
            files = export_project_package(data)
            counts = estimate_asset_count(data)
            return (
                gr.update(value=str(files["contract_md"]), visible=True),
                gr.update(value=str(files["batch_csv"]), visible=True),
                gr.update(value=str(files["batch_completo"]), visible=True),
                gr.update(value=str(files["manifest"]), visible=True),
                gr.update(value=(
                    f"✅ Paquete completo exportado — {counts['total']} assets estimados\n"
                    f"  📄 {files['contract_md'].name}\n"
                    f"  📋 {files['manifest'].name}\n"
                    f"  📦 {files['batch_completo'].name}"
                )),
            )
        except Exception as e:
            return (
                gr.update(visible=False), gr.update(visible=False),
                gr.update(visible=False), gr.update(visible=False),
                gr.update(value=f"❌ Error: {e}"),
            )

    full_pkg_btn.click(_export_full, all_inputs, [out_md, out_csv, out_full_csv, out_manifest, status_out])

    def _save_and_refresh(*args):
        try:
            data = _assemble_contract(*args)
            if not data.get("project_name"):
                return gr.update(value="⚠️ Escribe el nombre primero."), gr.update()
            path = save_contract(data)
            new_choices = ["— nuevo —"] + list_contracts()
            return gr.update(value=f"💾 Guardado: {path.name}"), gr.update(choices=new_choices, value=path.stem)
        except Exception as e:
            return gr.update(value=f"❌ Error: {e}"), gr.update()

    save_btn.click(_save_and_refresh, all_inputs, [status_out, saved_dd])

    def _export_ai_template(tpl_key):
        try:
            json_str = export_template_json(tpl_key or "blank")
            file_path = _write_download_file(f"{tpl_key or 'blank'}_template.json", json_str)
            return gr.update(value=file_path, visible=True), "✅ Plantilla IA lista para descargar."
        except Exception as e:
            return gr.update(visible=False), f"❌ Error: {e}"

    ai_tpl_export.click(_export_ai_template, inputs=[tpl_radio], outputs=[out_manifest, status_out])
