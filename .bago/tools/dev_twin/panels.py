"""dev_twin.panels — Constructores de paneles IA y Framework."""
import sys
import tkinter as tk
from tkinter import scrolledtext, ttk

from .constants import BAGO_ROOT, THEME
from .utils import _append_text, _run_in_pane


def build_ai_panel(parent: tk.Frame, app):
    """Construye el panel izquierdo: BAGO Chat CLI embebido."""
    tk.Label(
        parent,
        text="💬  BAGO Chat — Modo conversacional",
        bg=THEME["bg"],
        fg=THEME["accent_ai"],
        font=("Consolas", 12, "bold"),
    ).pack(pady=(8, 4))

    btn_frame = tk.Frame(parent, bg=THEME["bg"])
    btn_frame.pack(fill=tk.X, padx=8, pady=4)

    cmds = [
        ("▶  Iniciar chat", lambda: app._start_bago_chat()),
        ("⏹  Detener", lambda: app._stop_bago_chat()),
    ]
    for txt, cmd in cmds:
        tk.Button(
            btn_frame,
            text=txt,
            command=cmd,
            bg=THEME["btn_bg"],
            fg="#ffffff",
            activebackground=THEME["btn_active"],
            font=("Consolas", 8),
            relief=tk.FLAT,
            padx=6,
            pady=3,
        ).pack(side=tk.LEFT, padx=2)

    app.ai_text = scrolledtext.ScrolledText(
        parent,
        wrap=tk.WORD,
        bg=THEME["text_bg"],
        fg=THEME["fg"],
        insertbackground="#ffffff",
        font=("Consolas", 10),
        state=tk.DISABLED,
        padx=6,
        pady=6,
    )
    app.ai_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
    for tag, color in (
        ("prompt", THEME["prompt"]),
        ("error", THEME["error"]),
        ("dim", THEME["dim"]),
        ("success", THEME["success"]),
        ("user_msg", THEME["user_msg"]),
        ("assistant_msg", THEME["assistant_msg"]),
    ):
        app.ai_text.tag_configure(tag, foreground=color)

    input_frame = tk.Frame(parent, bg=THEME["bg"])
    input_frame.pack(fill=tk.X, padx=8, pady=(0, 8))
    tk.Label(input_frame, text="\u003e", bg=THEME["bg"], fg="#cccccc", font=("Consolas", 10)).pack(side=tk.LEFT)
    app.ai_entry = tk.Entry(
        input_frame,
        bg=THEME["input_bg"],
        fg=THEME["fg"],
        insertbackground="#ffffff",
        font=("Consolas", 10),
        relief=tk.FLAT,
    )
    app.ai_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
    app.ai_entry.bind("\u003cReturn\u003e", lambda e: app.on_ai_entry())
    tk.Button(
        input_frame,
        text="Enviar",
        command=app.on_ai_entry,
        bg=THEME["btn_bg"],
        fg="#ffffff",
        activebackground=THEME["btn_active"],
        font=("Consolas", 8),
        relief=tk.FLAT,
        padx=8,
    ).pack(side=tk.LEFT)


def build_framework_panel(parent: tk.Frame, app):
    """Construye el panel derecho: BAGO Launch embebido en consola propia."""
    tk.Label(
        parent,
        text="🚀  BAGO Launch — Orquestador interactivo",
        bg=THEME["bg"],
        fg=THEME["accent_fw"],
        font=("Consolas", 12, "bold"),
    ).pack(pady=(8, 4))

    btn_frame = tk.Frame(parent, bg=THEME["bg"])
    btn_frame.pack(fill=tk.X, padx=8, pady=4)

    cmds = [
        ("▶  Abrir bago launch", lambda: app._start_bago_launch()),
        ("⏹  Cerrar", lambda: app._stop_bago_launch()),
    ]
    for txt, cmd in cmds:
        tk.Button(
            btn_frame,
            text=txt,
            command=cmd,
            bg=THEME["btn_bg"],
            fg="#ffffff",
            activebackground=THEME["btn_active"],
            font=("Consolas", 8),
            relief=tk.FLAT,
            padx=6,
            pady=3,
        ).pack(side=tk.LEFT, padx=2)

    # Mantener atajos rápidos de framework debajo
    shortcut_frame = tk.Frame(parent, bg=THEME["bg"])
    shortcut_frame.pack(fill=tk.X, padx=8, pady=(0, 4))
    for txt, cmd in (
        ("F5 validate", lambda: app.run_fw_cmd(["bago", "validate"])),
        ("F6 status", lambda: app.run_fw_cmd(["bago", "status"])),
        ("F7 health", lambda: app.run_fw_cmd(["bago", "health"])),
    ):
        tk.Button(
            shortcut_frame,
            text=txt,
            command=cmd,
            bg=THEME["input_bg"],
            fg="#cccccc",
            activebackground=THEME["btn_active"],
            font=("Consolas", 7),
            relief=tk.FLAT,
            padx=4,
            pady=2,
        ).pack(side=tk.LEFT, padx=2)

    app.fw_text = scrolledtext.ScrolledText(
        parent,
        wrap=tk.WORD,
        bg=THEME["text_bg"],
        fg=THEME["fg"],
        insertbackground="#ffffff",
        font=("Consolas", 10),
        state=tk.DISABLED,
        padx=6,
        pady=6,
    )
    app.fw_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
    for tag, color in (
        ("prompt", THEME["prompt"]),
        ("error", THEME["error"]),
        ("dim", THEME["dim"]),
        ("success", THEME["success"]),
    ):
        app.fw_text.tag_configure(tag, foreground=color)

    input_frame = tk.Frame(parent, bg=THEME["bg"])
    input_frame.pack(fill=tk.X, padx=8, pady=(0, 8))
    tk.Label(input_frame, text="$", bg=THEME["bg"], fg="#cccccc", font=("Consolas", 10)).pack(side=tk.LEFT)
    app.fw_entry = tk.Entry(
        input_frame,
        bg=THEME["input_bg"],
        fg=THEME["fg"],
        insertbackground="#ffffff",
        font=("Consolas", 10),
        relief=tk.FLAT,
    )
    app.fw_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
    app.fw_entry.bind("\u003cReturn\u003e", lambda e: app.on_fw_entry())
    tk.Button(
        input_frame,
        text="Ejecutar",
        command=app.on_fw_entry,
        bg=THEME["btn_bg"],
        fg="#ffffff",
        activebackground=THEME["btn_active"],
        font=("Consolas", 8),
        relief=tk.FLAT,
        padx=8,
    ).pack(side=tk.LEFT)
