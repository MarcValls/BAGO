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

"""_wizard_contract.py — Constantes y helpers de datos para el Wizard de Contrato de Arte."""
import json
from pathlib import Path

import gradio as gr

from .contract import (
    STYLE_PRESETS, TONE_OPTIONS, PALETTE_SUGGESTIONS, CONTRACT_TEMPLATES,
    CHARACTER_ROLES, CANONICAL_ANIMATIONS, HUD_DEFAULTS, PROJECT_TYPES,
    build_style_suffix, get_style_defaults, CONTRACTS_DIR,
)

N_CHARS = 3
N_SCENS = 3
ANIM_NAMES = [a["name"] for a in CANONICAL_ANIMATIONS]
HUD_LABELS = [f"{el['id']} — {el['name']}" for el in HUD_DEFAULTS]
HUD_DEFAULT_CHECKED = HUD_LABELS[:8]
TPL_CHOICES = [(v["label"], k) for k, v in CONTRACT_TEMPLATES.items()]
DOWNLOADS_DIR = CONTRACTS_DIR / "_downloads"
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)


def _palette_updates(preset_name: str):
    colors = PALETTE_SUGGESTIONS.get(preset_name, [])
    updates = []
    for i in range(6):
        c = colors[i] if i < len(colors) else {}
        updates += [
            gr.update(value=c.get("hex", "#000000")),
            gr.update(value=c.get("role", "")),
            gr.update(value=c.get("name", "")),
            gr.update(value=c.get("use", "")),
        ]
    return updates


def _collect_palette(*args) -> list[dict]:
    palette = []
    for i in range(6):
        base = i * 4
        hexv, role, name, use = args[base], args[base + 1], args[base + 2], args[base + 3]
        if hexv and str(hexv).strip() not in ("", "#000000", "None"):
            palette.append({"hex": hexv, "role": role, "name": name, "use": use})
    return palette


def _collect_character(name, role, desc, prompt, anims, cw, ch, cols, rows, visible_state) -> dict | None:
    if not visible_state or not name or not str(name).strip():
        return None
    ss = {
        "cell_w": int(cw or 64), "cell_h": int(ch or 64),
        "cols": int(cols or 8), "rows": int(rows or 8),
        "sheet_w": int(cw or 64) * int(cols or 8),
        "sheet_h": int(ch or 64) * int(rows or 8),
        "scale": "1x", "format": "PNG transparente 32-bit",
    }
    selected_anims = [a for a in CANONICAL_ANIMATIONS if a["name"] in (anims or [])]
    return {
        "name": name,
        "role": role,
        "description": desc,
        "prompt": prompt,
        "sprite_sheet": ss,
        "animations": selected_anims,
    }


def _collect_scenario(sid, name, desc, pal, bg_prompt, tp, tw, th, var, visible_state) -> dict | None:
    if not visible_state or not name or not str(name).strip():
        return None
    return {
        "id": sid or name.lower().replace(" ", "_"),
        "name": name,
        "description": desc,
        "palette_notes": pal,
        "bg_prompt": bg_prompt,
        "tileset": {
            "tile_w": int(tw or 32),
            "tile_h": int(th or 32),
            "variants": int(var or 4),
            "prompt": tp,
        },
        "notes": "",
    }


def _collect_hud(selected_labels: list[str], hud_custom_json: str) -> list[dict]:
    elements = []
    selected_ids = {lbl.split(" — ")[0] for lbl in (selected_labels or [])}
    for el in HUD_DEFAULTS:
        if el["id"] in selected_ids:
            el_copy = dict(el)
            el_copy.setdefault("prompt", "")
            elements.append(el_copy)
    try:
        customs = json.loads(hud_custom_json or "[]")
        if isinstance(customs, list):
            elements.extend(customs)
    except Exception:
        pass
    return elements


def _assemble_contract(
    project_name, project_type, version, description,
    style_name, tones, suf, quality_ref, principles,
    *palette_args_and_rest,
) -> dict:
    n_pal = 24
    palette_args = palette_args_and_rest[:n_pal]
    rest = list(palette_args_and_rest[n_pal:])
    palette = _collect_palette(*palette_args)

    n_char_fields = 9
    characters = []
    for i in range(N_CHARS):
        base = i * n_char_fields
        vis = rest[N_CHARS * n_char_fields + i]
        ch = _collect_character(*rest[base:base + n_char_fields], vis)
        if ch:
            characters.append(ch)

    offset = N_CHARS * n_char_fields + N_CHARS
    n_scen_fields = 9
    scenarios = []
    for i in range(N_SCENS):
        base = offset + i * n_scen_fields
        vis = rest[offset + N_SCENS * n_scen_fields + i]
        sc = _collect_scenario(*rest[base:base + n_scen_fields], vis)
        if sc:
            scenarios.append(sc)

    offset2 = offset + N_SCENS * n_scen_fields + N_SCENS
    hud_selected = rest[offset2]
    hud_custom_json = rest[offset2 + 1]
    accept_rules = rest[offset2 + 2]
    reject_rules = rest[offset2 + 3]
    extra_notes = rest[offset2 + 4]

    return {
        "project_name": (project_name or "").strip(),
        "project_type": project_type or "Personalizado",
        "version": version or "1.0",
        "description": description or "",
        "style_name": style_name or "",
        "visual_tone": ", ".join(tones or []),
        "style_prompt_suffix": suf or "",
        "quality_ref": quality_ref or "",
        "principles": principles or "",
        "palette": palette,
        "characters": characters,
        "scenarios": scenarios,
        "ui_elements": _collect_hud(hud_selected, hud_custom_json),
        "accept_rules": accept_rules or "",
        "reject_rules": reject_rules or "",
        "extra_notes": extra_notes or "",
    }


def _write_download_file(filename: str, content: str) -> str:
    path = DOWNLOADS_DIR / filename
    path.write_text(content, encoding="utf-8")
    return str(path)


def _load_contract_to_fields(data: dict) -> list:
    updates = []
    tones_val = [t.strip() for t in data.get("visual_tone", "").split(",") if t.strip()]
    updates += [
        gr.update(value=data.get("project_name", "")),
        gr.update(value=data.get("project_type", "Videojuego 2D")),
        gr.update(value=data.get("version", "1.0")),
        gr.update(value=data.get("description", "")),
        gr.update(value=data.get("style_name", "Pixel Art 32×32")),
        gr.update(value=tones_val),
        gr.update(value=data.get("style_prompt_suffix", "")),
        gr.update(value=data.get("quality_ref", "")),
        gr.update(value=data.get("principles", "")),
    ]
    palette = data.get("palette", [])
    for i in range(6):
        c = palette[i] if i < len(palette) else {}
        updates += [
            gr.update(value=c.get("hex", "#000000")),
            gr.update(value=c.get("role", "")),
            gr.update(value=c.get("name", "")),
            gr.update(value=c.get("use", "")),
        ]

    chars = data.get("characters", [])
    for i in range(N_CHARS):
        if i < len(chars):
            ch = chars[i]
            anims = ch.get("animations", [])
            anim_names = [a["name"] if isinstance(a, dict) else a for a in anims]
            ss = ch.get("sprite_sheet", {})
            updates += [
                gr.update(value=ch.get("name", "")),
                gr.update(value=ch.get("role", CHARACTER_ROLES[min(i, len(CHARACTER_ROLES) - 1)])),
                gr.update(value=ch.get("description", "")),
                gr.update(value=ch.get("prompt", "")),
                gr.update(value=[a for a in anim_names if a in ANIM_NAMES]),
                gr.update(value=int(ss.get("cell_w", 32))),
                gr.update(value=int(ss.get("cell_h", 32))),
                gr.update(value=int(ss.get("cols", 8))),
                gr.update(value=int(ss.get("rows", 8))),
            ]
        else:
            role_default = CHARACTER_ROLES[i] if i < len(CHARACTER_ROLES) else ""
            updates += [
                gr.update(value=""),
                gr.update(value=role_default),
                gr.update(value=""),
                gr.update(value=""),
                gr.update(value=[]),
                gr.update(value=32),
                gr.update(value=32),
                gr.update(value=8),
                gr.update(value=8),
            ]
    for i in range(N_CHARS):
        updates.append(i < len(chars))

    scens = data.get("scenarios", [])
    for i in range(N_SCENS):
        if i < len(scens):
            sc = scens[i]
            ts = sc.get("tileset", {})
            updates += [
                gr.update(value=sc.get("id", "")),
                gr.update(value=sc.get("name", "")),
                gr.update(value=sc.get("description", "")),
                gr.update(value=sc.get("palette_notes", "")),
                gr.update(value=sc.get("bg_prompt", "")),
                gr.update(value=ts.get("prompt", "")),
                gr.update(value=int(ts.get("tile_w", 32))),
                gr.update(value=int(ts.get("tile_h", 32))),
                gr.update(value=int(ts.get("variants", 4))),
            ]
        else:
            updates += [
                gr.update(value=""), gr.update(value=""), gr.update(value=""),
                gr.update(value=""), gr.update(value=""), gr.update(value=""),
                gr.update(value=32), gr.update(value=32), gr.update(value=4),
            ]
    for i in range(N_SCENS):
        updates.append(i < len(scens))

    ui_els = data.get("ui_elements", [])
    hud_ids = {el.get("id") for el in ui_els}
    hud_sel = [lbl for lbl in HUD_LABELS if lbl.split(" — ")[0] in hud_ids]
    default_ids = {el["id"] for el in HUD_DEFAULTS}
    custom_els = [el for el in ui_els if el.get("id", "") not in default_ids]
    updates += [
        gr.update(value=hud_sel),
        gr.update(value=json.dumps(custom_els, ensure_ascii=False) if custom_els else ""),
        gr.update(value=data.get("accept_rules", "")),
        gr.update(value=data.get("reject_rules", "")),
        gr.update(value=data.get("extra_notes", "")),
    ]

    for i in range(N_CHARS):
        visible = i < len(chars) or (i == 0 and not chars)
        updates.append(gr.update(visible=visible))
    for i in range(N_SCENS):
        visible = i < len(scens) or (i == 0 and not scens)
        updates.append(gr.update(visible=visible))
    return updates
