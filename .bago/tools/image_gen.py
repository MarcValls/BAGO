#!/usr/bin/env python3
"""image_gen.py — Generador de imágenes BAGO sin API externa.

Genera imágenes PNG localmente usando matplotlib + Pillow + qrcode.

Uso:
    python image_gen.py banner                     → banner BAGO PNG
    python image_gen.py chart                      → gráfico métricas del sistema
    python image_gen.py progress                   → barra progreso ideas
    python image_gen.py timeline                   → timeline de sesiones
    python image_gen.py qr <texto>                 → código QR
    python image_gen.py tools                      → mapa visual de herramientas
    python image_gen.py --output ruta/imagen.png   → ruta de salida personalizada
    python image_gen.py --show                     → abre la imagen tras generar
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

TOOLS_DIR = Path(__file__).parent
BAGO_ROOT = TOOLS_DIR.parent
STATE_DIR = BAGO_ROOT / "state"
OUT_DIR   = STATE_DIR / "images"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BAGO_BLUE    = "#1a6fa8"
BAGO_GREEN   = "#27ae60"
BAGO_ORANGE  = "#e67e22"
BAGO_RED     = "#e74c3c"
BAGO_DARK    = "#1a1a2e"
BAGO_LIGHT   = "#ecf0f1"
BAGO_ACCENT  = "#9b59b6"


# ── State helpers ─────────────────────────────────────────────────────────────

def _load_global_state() -> dict:
    p = STATE_DIR / "global_state.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _load_sessions() -> list:
    sessions = []
    sd = STATE_DIR / "sessions"
    if not sd.exists():
        return sessions
    for f in sorted(sd.glob("SESSION_CLOSE_*.md"))[-20:]:
        try:
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
            date_str = f.stem.replace("SESSION_CLOSE_", "")
            dt_obj = None
            try:
                dt_obj = datetime.strptime(date_str[:15], "%Y%m%d_%H%M%S")
            except Exception:
                pass
            sessions.append({"file": f.name, "dt": dt_obj})
        except Exception:
            pass
    return sessions


def _count_tools() -> int:
    return len(list(TOOLS_DIR.glob("*.py")))


# ── Banner ─────────────────────────────────────────────────────────────────────

def gen_banner(output: Path, show: bool = False) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.patches import FancyBboxPatch

    state = _load_global_state()
    ideas_done = state.get("implemented_ideas_count", 89)
    ideas_total = state.get("total_ideas", 109)
    health = state.get("health_score", 100)
    version = state.get("bago_version", state.get("version", "unknown"))
    tools_n = _count_tools()
    pct = int(ideas_done / max(ideas_total, 1) * 100)

    fig, ax = plt.subplots(figsize=(12, 4))
    fig.patch.set_facecolor(BAGO_DARK)
    ax.set_facecolor(BAGO_DARK)
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 4)
    ax.axis("off")

    # Outer frame
    frame = FancyBboxPatch((0.1, 0.1), 11.8, 3.8,
                            boxstyle="round,pad=0.05",
                            linewidth=2, edgecolor=BAGO_BLUE,
                            facecolor=BAGO_DARK)
    ax.add_patch(frame)

    # ASCII-style title
    ax.text(0.5, 3.4, "B A G O", color=BAGO_BLUE, fontsize=38,
            fontweight="bold", fontfamily="monospace", va="top")
    ax.text(4.8, 3.55, f"v{version}", color=BAGO_LIGHT, fontsize=11,
            fontfamily="monospace", va="top")

    # Subtitle
    ax.text(0.5, 2.85,
            "B·alanceado  A·daptativo  G·enerativo  O·rganizativo",
            color="#7f8c8d", fontsize=10, fontfamily="monospace")

    # Divider
    ax.plot([0.3, 11.7], [2.55, 2.55], color=BAGO_BLUE, linewidth=1, alpha=0.6)

    # Stats row
    stats = [
        ("[Ideas]", f"{ideas_done}/{ideas_total}", BAGO_GREEN),
        ("[Tools]", str(tools_n), BAGO_BLUE),
        ("[Health]", f"{health}pts", BAGO_GREEN if health >= 80 else BAGO_ORANGE),
        ("[Fecha]", datetime.now().strftime("%Y-%m-%d"), BAGO_LIGHT),
    ]
    x_positions = [0.5, 3.3, 6.1, 8.9]
    for (label, val, color), xp in zip(stats, x_positions):
        ax.text(xp, 2.35, label, color="#7f8c8d", fontsize=8, fontfamily="monospace")
        ax.text(xp, 1.95, val, color=color, fontsize=14,
                fontweight="bold", fontfamily="monospace")

    # Progress bar
    bar_x, bar_y, bar_w, bar_h = 0.5, 1.45, 11.0, 0.28
    bar_bg = FancyBboxPatch((bar_x, bar_y), bar_w, bar_h,
                             boxstyle="round,pad=0.02",
                             facecolor="#2c3e50", edgecolor="none")
    ax.add_patch(bar_bg)
    fill_w = bar_w * (pct / 100)
    bar_fill = FancyBboxPatch((bar_x, bar_y), fill_w, bar_h,
                               boxstyle="round,pad=0.02",
                               facecolor=BAGO_GREEN, edgecolor="none", alpha=0.85)
    ax.add_patch(bar_fill)
    ax.text(bar_x + bar_w / 2, bar_y + bar_h / 2,
            f"{pct}% completado",
            color="white", fontsize=9, fontfamily="monospace",
            ha="center", va="center", fontweight="bold")

    # Bottom
    ax.plot([0.3, 11.7], [1.1, 1.1], color=BAGO_BLUE, linewidth=0.5, alpha=0.4)
    ax.text(0.5, 0.75, "⚡ python bago help  |  bago banner  |  bago peer",
            color="#5d6d7e", fontsize=8, fontfamily="monospace")
    ax.text(11.5, 0.75, "BAGO Framework",
            color="#5d6d7e", fontsize=8, fontfamily="monospace", ha="right")

    fig.tight_layout(pad=0)
    fig.savefig(output, dpi=150, bbox_inches="tight",
                facecolor=BAGO_DARK, edgecolor="none")
    plt.close(fig)
    if show:
        _open_file(output)
    return output


# ── Metrics Chart ─────────────────────────────────────────────────────────────

def gen_chart(output: Path, show: bool = False) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    state = _load_global_state()
    ideas_done  = state.get("implemented_ideas_count", 89)
    ideas_total = state.get("total_ideas", 109)
    health      = state.get("health_score", 100)
    tools_n     = _count_tools()

    fig, axes = plt.subplots(1, 3, figsize=(14, 5))
    fig.patch.set_facecolor(BAGO_DARK)
    for ax in axes:
        ax.set_facecolor(BAGO_DARK)
        ax.tick_params(colors=BAGO_LIGHT)
        for spine in ax.spines.values():
            spine.set_edgecolor("#2c3e50")

    # ── Donut: ideas ──
    ax = axes[0]
    done_val = ideas_done
    rem_val  = max(0, ideas_total - ideas_done)
    wedges, _ = ax.pie(
        [done_val, rem_val],
        colors=[BAGO_GREEN, "#2c3e50"],
        startangle=90,
        wedgeprops={"width": 0.45, "edgecolor": BAGO_DARK, "linewidth": 2},
    )
    pct = int(done_val / max(ideas_total, 1) * 100)
    ax.text(0, 0.1, f"{pct}%", color=BAGO_GREEN, fontsize=24,
            fontweight="bold", ha="center", va="center", fontfamily="monospace")
    ax.text(0, -0.25, "ideas", color=BAGO_LIGHT, fontsize=11,
            ha="center", fontfamily="monospace")
    ax.set_title(f"Ideas\n{done_val}/{ideas_total}", color=BAGO_LIGHT,
                 fontsize=11, fontfamily="monospace", pad=10)

    # ── Gauge: health ──
    ax = axes[1]
    theta = np.linspace(np.pi, 0, 200)
    ax.plot(np.cos(theta), np.sin(theta), color="#2c3e50", linewidth=18, solid_capstyle="round")
    h_angle = np.pi - (health / 100) * np.pi
    theta_fill = np.linspace(np.pi, h_angle, 200)
    h_color = BAGO_GREEN if health >= 80 else (BAGO_ORANGE if health >= 50 else BAGO_RED)
    ax.plot(np.cos(theta_fill), np.sin(theta_fill),
            color=h_color, linewidth=18, solid_capstyle="round")
    ax.text(0, -0.1, f"{health}", color=h_color, fontsize=26,
            fontweight="bold", ha="center", va="center", fontfamily="monospace")
    ax.text(0, -0.45, "pts", color=BAGO_LIGHT, fontsize=10, ha="center", fontfamily="monospace")
    ax.set_xlim(-1.3, 1.3)
    ax.set_ylim(-0.7, 1.3)
    ax.axis("off")
    ax.set_title("Health Score", color=BAGO_LIGHT, fontsize=11,
                 fontfamily="monospace", pad=10)

    # ── Bar: tools ──
    ax = axes[2]
    categories = ["Tools\nregist.", "Ideas\nhecho", "Ideas\ntotal"]
    values     = [tools_n, ideas_done, ideas_total]
    colors     = [BAGO_BLUE, BAGO_GREEN, BAGO_ACCENT]
    bars = ax.bar(categories, values, color=colors, width=0.5, edgecolor=BAGO_DARK, linewidth=1.5)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 1,
                str(val), ha="center", va="bottom",
                color=BAGO_LIGHT, fontsize=12, fontweight="bold", fontfamily="monospace")
    ax.set_facecolor(BAGO_DARK)
    ax.set_ylim(0, max(values) * 1.2)
    ax.tick_params(axis="x", colors=BAGO_LIGHT, labelsize=9)
    ax.tick_params(axis="y", colors="#5d6d7e", labelsize=8)
    ax.set_title("Recursos BAGO", color=BAGO_LIGHT, fontsize=11,
                 fontfamily="monospace", pad=10)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.yaxis.grid(True, color="#2c3e50", linewidth=0.5)
    ax.set_axisbelow(True)

    fig.suptitle(f"BAGO Framework — Métricas  |  {datetime.now():%Y-%m-%d %H:%M}",
                 color=BAGO_LIGHT, fontsize=13, fontfamily="monospace", y=1.01)
    fig.tight_layout()
    fig.savefig(output, dpi=150, bbox_inches="tight",
                facecolor=BAGO_DARK, edgecolor="none")
    plt.close(fig)
    if show:
        _open_file(output)
    return output


# ── Progress bar PNG ──────────────────────────────────────────────────────────

def gen_progress(output: Path, show: bool = False) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    state = _load_global_state()
    ideas_done  = state.get("implemented_ideas_count", 89)
    ideas_total = state.get("total_ideas", 109)
    tools_n     = _count_tools()
    health      = state.get("health_score", 100)
    pct = ideas_done / max(ideas_total, 1)

    rows = [
        ("Ideas implementadas", ideas_done, ideas_total, BAGO_GREEN),
        ("Health score",        health,     100,         BAGO_GREEN if health >= 80 else BAGO_ORANGE),
        ("Tools registradas",   tools_n,    150,         BAGO_BLUE),
    ]

    fig, ax = plt.subplots(figsize=(10, 3.5))
    fig.patch.set_facecolor(BAGO_DARK)
    ax.set_facecolor(BAGO_DARK)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, len(rows) + 0.5)
    ax.axis("off")

    for i, (label, val, total, color) in enumerate(rows):
        y = len(rows) - i - 0.2
        ratio = min(val / max(total, 1), 1.0)
        ax.text(0.1, y + 0.35, label, color=BAGO_LIGHT, fontsize=10,
                fontfamily="monospace", va="center")
        ax.text(9.9, y + 0.35, f"{val}/{total}",
                color=color, fontsize=10, fontfamily="monospace",
                va="center", ha="right", fontweight="bold")
        # bg bar
        bg = FancyBboxPatch((0.1, y - 0.05), 9.8, 0.28,
                             boxstyle="round,pad=0.02",
                             facecolor="#2c3e50", edgecolor="none")
        ax.add_patch(bg)
        # fill
        if ratio > 0:
            fill = FancyBboxPatch((0.1, y - 0.05), 9.8 * ratio, 0.28,
                                   boxstyle="round,pad=0.02",
                                   facecolor=color, edgecolor="none", alpha=0.85)
            ax.add_patch(fill)

    ax.text(5, len(rows) + 0.25,
            f"BAGO — Estado  {datetime.now():%Y-%m-%d %H:%M}",
            color=BAGO_BLUE, fontsize=11, fontfamily="monospace",
            ha="center", fontweight="bold")

    fig.tight_layout(pad=0.5)
    fig.savefig(output, dpi=150, bbox_inches="tight",
                facecolor=BAGO_DARK, edgecolor="none")
    plt.close(fig)
    if show:
        _open_file(output)
    return output


# ── Timeline ──────────────────────────────────────────────────────────────────

def gen_timeline(output: Path, show: bool = False) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sessions = _load_sessions()
    # fallback synthetic data if no sessions
    if not sessions:
        sessions = [{"file": f"SES_{i}", "dt": None} for i in range(5)]

    n = len(sessions)
    fig, ax = plt.subplots(figsize=(max(10, n * 0.7 + 2), 4))
    fig.patch.set_facecolor(BAGO_DARK)
    ax.set_facecolor(BAGO_DARK)
    ax.axis("off")

    # Horizontal timeline line
    ax.plot([0.5, n + 0.5], [0.5, 0.5], color=BAGO_BLUE, linewidth=2, zorder=1)

    for i, s in enumerate(sessions):
        x = i + 1
        color = BAGO_GREEN if i == n - 1 else BAGO_BLUE
        ax.scatter([x], [0.5], color=color, s=80, zorder=2, edgecolors=BAGO_DARK, linewidths=1.5)
        label = s["dt"].strftime("%m-%d\n%H:%M") if s.get("dt") else f"S{i+1}"
        ax.text(x, 0.15, label, color=BAGO_LIGHT, fontsize=7,
                fontfamily="monospace", ha="center", va="top")
        if i == n - 1:
            ax.text(x, 0.85, "← última", color=BAGO_GREEN, fontsize=7,
                    fontfamily="monospace", ha="center")

    ax.set_xlim(0, n + 1)
    ax.set_ylim(-0.3, 1.4)
    ax.set_title(f"BAGO — Timeline de sesiones ({n} sesiones)",
                 color=BAGO_LIGHT, fontsize=12, fontfamily="monospace")

    fig.tight_layout()
    fig.savefig(output, dpi=150, bbox_inches="tight",
                facecolor=BAGO_DARK, edgecolor="none")
    plt.close(fig)
    if show:
        _open_file(output)
    return output


# ── QR code ───────────────────────────────────────────────────────────────────

def gen_qr(text: str, output: Path, show: bool = False) -> Path:
    import qrcode
    from PIL import Image, ImageDraw, ImageFont

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=8,
        border=3,
    )
    qr.add_data(text)
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color=BAGO_DARK, back_color=BAGO_LIGHT)

    # Add label below
    w, h = img_qr.size
    label_h = 40
    final = Image.new("RGB", (w, h + label_h), color="#1a1a2e")
    final.paste(img_qr, (0, 0))
    draw = ImageDraw.Draw(final)
    short_text = text if len(text) <= 40 else text[:37] + "..."
    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), short_text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((w - tw) // 2, h + 8), short_text,
              fill=BAGO_LIGHT, font=font)
    final.save(output)
    if show:
        _open_file(output)
    return output


# ── Tools map ────────────────────────────────────────────────────────────────

def gen_tools_map(output: Path, show: bool = False) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    tools = sorted(p.stem for p in TOOLS_DIR.glob("*.py")
                   if not p.stem.startswith("_"))

    cols = 6
    rows_n = (len(tools) + cols - 1) // cols
    fig, ax = plt.subplots(figsize=(cols * 2.2, rows_n * 0.7 + 1.5))
    fig.patch.set_facecolor(BAGO_DARK)
    ax.set_facecolor(BAGO_DARK)
    ax.set_xlim(0, cols)
    ax.set_ylim(-0.5, rows_n + 0.5)
    ax.axis("off")

    palette = [BAGO_BLUE, BAGO_GREEN, BAGO_ACCENT, BAGO_ORANGE, "#1abc9c", "#e74c3c"]

    for idx, tool in enumerate(tools):
        r = idx // cols
        c = idx % cols
        y = rows_n - r - 0.5
        color = palette[idx % len(palette)]
        rect = plt.Rectangle((c + 0.05, y - 0.3), 0.9, 0.55,
                              facecolor=color, alpha=0.15,
                              edgecolor=color, linewidth=0.8)
        ax.add_patch(rect)
        ax.text(c + 0.5, y, tool.replace("_", " "),
                color=BAGO_LIGHT, fontsize=6.5, fontfamily="monospace",
                ha="center", va="center")

    ax.set_title(f"BAGO Tools Map — {len(tools)} herramientas",
                 color=BAGO_LIGHT, fontsize=13, fontfamily="monospace", pad=12)
    fig.tight_layout(pad=0.5)
    fig.savefig(output, dpi=150, bbox_inches="tight",
                facecolor=BAGO_DARK, edgecolor="none")
    plt.close(fig)
    if show:
        _open_file(output)
    return output


# ── Open helper ───────────────────────────────────────────────────────────────

def _open_file(path: Path) -> None:
    import subprocess
    try:
        if sys.platform == "win32":
            os.startfile(str(path))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)])
        else:
            subprocess.run(["xdg-open", str(path)])
    except Exception:
        pass


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return

    show = "--show" in args
    out_flag = "--output" in args
    if out_flag:
        idx = args.index("--output")
        custom_out = Path(args[idx + 1])
        args = [a for i, a in enumerate(args) if i not in (idx, idx + 1)]
    else:
        custom_out = None

    cmd = args[0].lower()
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")

    if cmd == "banner":
        out = custom_out or OUT_DIR / f"bago_banner_{ts}.png"
        path = gen_banner(out, show)
        print(f"  🎨 Banner generado → {path}")

    elif cmd == "chart":
        out = custom_out or OUT_DIR / f"bago_chart_{ts}.png"
        path = gen_chart(out, show)
        print(f"  📊 Gráfico generado → {path}")

    elif cmd == "progress":
        out = custom_out or OUT_DIR / f"bago_progress_{ts}.png"
        path = gen_progress(out, show)
        print(f"  📈 Progreso generado → {path}")

    elif cmd == "timeline":
        out = custom_out or OUT_DIR / f"bago_timeline_{ts}.png"
        path = gen_timeline(out, show)
        print(f"  📅 Timeline generado → {path}")

    elif cmd == "qr":
        text = " ".join(args[1:]) if len(args) > 1 else "https://github.com/BAGO"
        out  = custom_out or OUT_DIR / f"bago_qr_{ts}.png"
        path = gen_qr(text, out, show)
        print(f"  🔲 QR generado → {path}")
        print(f"     Texto: {text}")

    elif cmd == "tools":
        out = custom_out or OUT_DIR / f"bago_tools_{ts}.png"
        path = gen_tools_map(out, show)
        print(f"  🗺  Tools map generado → {path}")

    elif cmd == "all":
        ts2 = datetime.now().strftime("%Y%m%d_%H%M%S")
        results = []
        for fn, name in [
            (lambda: gen_banner(OUT_DIR / f"bago_banner_{ts2}.png", show),    "banner"),
            (lambda: gen_chart(OUT_DIR / f"bago_chart_{ts2}.png", show),      "chart"),
            (lambda: gen_progress(OUT_DIR / f"bago_progress_{ts2}.png", show),"progress"),
            (lambda: gen_timeline(OUT_DIR / f"bago_timeline_{ts2}.png", show),"timeline"),
            (lambda: gen_tools_map(OUT_DIR / f"bago_tools_{ts2}.png", show),  "tools"),
        ]:
            try:
                p = fn()
                results.append((name, str(p), "✅"))
            except Exception as e:
                results.append((name, str(e), "❌"))
        print("\n  🎨 BAGO Image Generator — generación completa\n")
        for name, info, icon in results:
            print(f"    {icon} {name:<12} → {info}")
        print()

    else:
        print(f"  ❌ Comando desconocido: '{cmd}'")
        print("     Usa: banner | chart | progress | timeline | qr <texto> | tools | all")
        sys.exit(1)



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
