"""dev_twin.app — Ventana principal TwinDevWindow.

El panel izquierdo incrusta BAGO Chat directamente como biblioteca Python,
sin ejecutar bago_chat.py como subproceso externo.
"""
import contextlib
import io
import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from .constants import BAGO_ROOT, IS_WIN, THEME
from .panels import build_ai_panel, build_framework_panel
from .utils import _append_text, _run_in_pane


class _WidgetWriter:
    """File-like object que redirige escrituras a un widget tkinter de forma thread-safe."""

    def __init__(self, widget, root):
        self.widget = widget
        self.root = root
        self._buffer = ""
        self._lock = threading.Lock()

    def write(self, text):
        if not text:
            return
        with self._lock:
            self._buffer += text
            # Flush líneas completas para no saturar el event loop de tk
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                self.root.after(0, lambda l=line: _append_text(self.widget, l + "\n"))
        # Si el texto no termina en \n, scheduleamos flush parcial tras un breve delay
        self.root.after(100, self._flush_partial)

    def _flush_partial(self):
        with self._lock:
            if self._buffer:
                buf = self._buffer
                self._buffer = ""
        if buf:
            _append_text(self.widget, buf)

    def flush(self):
        with self._lock:
            if self._buffer:
                buf = self._buffer
                self._buffer = ""
            else:
                buf = ""
        if buf:
            self.root.after(0, lambda: _append_text(self.widget, buf))

    def isatty(self):
        return False


class TwinDevWindow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("BAGO Dev Twin — IA | BAGO")
        self.root.geometry("1200x700")
        self.root.minsize(800, 500)

        self.style = ttk.Style()
        self.style.theme_use("clam")
        self._dark_theme()

        self.paned = tk.PanedWindow(root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashwidth=4)
        self.paned.pack(fill=tk.BOTH, expand=True)

        self.left = tk.Frame(self.paned, bg=THEME["bg"])
        self.paned.add(self.left, minsize=400)
        build_ai_panel(self.left, self)

        self.right = tk.Frame(self.paned, bg=THEME["bg"])
        self.paned.add(self.right, minsize=400)
        build_framework_panel(self.right, self)

        self.status = tk.Label(
            root,
            text=f"BAGO_ROOT: {BAGO_ROOT}",
            bd=1,
            relief=tk.SUNKEN,
            anchor=tk.W,
            bg=THEME["input_bg"],
            fg="#cccccc",
            font=("Consolas", 9),
        )
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

        self.root.bind("<F5>", lambda e: self.run_fw_cmd(["bago", "validate"]))
        self.root.bind("<F6>", lambda e: self.run_fw_cmd(["bago", "status"]))
        self.root.bind("<F7>", lambda e: self.run_fw_cmd(["bago", "health"]))

        self.bago_session = None          # Instancia de BagoSession
        self._chat_worker = None          # Hilo que ejecuta chat_bridge

    def _dark_theme(self):
        self.style.configure("TButton", background=THEME["btn_bg"], foreground="#ffffff", font=("Consolas", 9))
        self.style.map("TButton", background=[("active", THEME["btn_active"])])
        self.style.configure("TFrame", background=THEME["bg"])
        self.style.configure("TLabel", background=THEME["bg"], foreground="#cccccc", font=("Consolas", 10))

    # ── Framework panel ────────────────────────────────────────────────────────

    def run_fw_cmd(self, cmd: list[str]):
        self.fw_proc = _run_in_pane(self.fw_text, cmd, cwd=BAGO_ROOT)

    def on_fw_entry(self):
        text = self.fw_entry.get().strip()
        self.fw_entry.delete(0, tk.END)
        if not text:
            return
        self.run_fw_cmd(text.split())

    # ── AI / BAGO Chat panel (incrustado) ──────────────────────────────────────

    def _start_bago_chat(self):
        if self.bago_session is not None:
            _append_text(self.ai_text, "[BAGO Chat ya está activo]\n", tag="dim")
            return

        _append_text(self.ai_text, "[Iniciando BAGO Chat...]\n", tag="dim")

        def _init():
            try:
                from bago.chat.boot import resolve_session
                from bago.menus.config import _load_config

                cfg = _load_config()
                args = SimpleNamespace(
                    provider="", model="", task="", local=False,
                    single_model=cfg.get("single_model", False),
                )
                session = resolve_session(args)
                # Aplicar configuracion persistente
                session.autoroute = cfg.get("autoroute", True)
                session.single_model = cfg.get("single_model", False)
                session.autonomous = cfg.get("autonomous", False)
                session.orch_mode = cfg.get("orch_mode", "standard")
                self.bago_session = session
                self.root.after(0, lambda: _append_text(
                    self.ai_text,
                    f"[BAGO Chat listo] {session.model_name}/{session.provider}\n",
                    tag="success",
                ))
            except Exception as exc:
                self.root.after(0, lambda: _append_text(
                    self.ai_text, f"[Error iniciando BAGO Chat] {exc}\n", tag="error",
                ))

        threading.Thread(target=_init, daemon=True).start()

    def _stop_bago_chat(self):
        if self.bago_session is None:
            _append_text(self.ai_text, "[BAGO Chat no está activo]\n", tag="dim")
            return
        self.bago_session = None
        _append_text(self.ai_text, "[BAGO Chat detenido]\n", tag="dim")

    def on_ai_entry(self):
        text = self.ai_entry.get().strip()
        self.ai_entry.delete(0, tk.END)
        if not text:
            return

        if self.bago_session is None:
            # Si no hay sesión, ejecutar como comando suelto en el panel
            self.run_ai_cmd(text.split())
            return

        # Mostrar mensaje del usuario inmediatamente
        _append_text(self.ai_text, f"\u003e {text}\n", tag="user_msg")

        # Ejecutar chat_bridge en hilo para no bloquear la UI
        def _chat():
            writer = _WidgetWriter(self.ai_text, self.root)
            # Redirigir stdout/stderr al widget durante la llamada
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = writer
            sys.stderr = writer
            try:
                from bago.api.bridge import chat_bridge
                result = chat_bridge(self.bago_session, text, history_input=text)
                if result:
                    self.root.after(0, lambda: _append_text(self.ai_text, f"{result}\n", tag="assistant_msg"))
            except Exception as exc:
                self.root.after(0, lambda: _append_text(
                    self.ai_text, f"[Error] {exc}\n", tag="error",
                ))
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr

        self._chat_worker = threading.Thread(target=_chat, daemon=True)
        self._chat_worker.start()

    def run_ai_cmd(self, cmd: list[str]):
        self.ai_proc = _run_in_pane(self.ai_text, cmd, cwd=BAGO_ROOT)

    # ── BAGO Launch panel (consola propia) ─────────────────────────────────────

    def _start_bago_launch(self):
        if getattr(self, "_launch_proc", None) and self._launch_proc.poll() is None:
            _append_text(self.fw_text, "[bago launch ya está abierto]\n", tag="dim")
            return
        _append_text(self.fw_text, "[Abriendo bago launch en consola propia...]\n", tag="dim")
        try:
            if IS_WIN:
                bago_cmd = BAGO_ROOT / "bago.cmd"
                if bago_cmd.exists():
                    self._launch_proc = subprocess.Popen(
                        [str(bago_cmd), "launch"],
                        cwd=str(BAGO_ROOT),
                        creationflags=subprocess.CREATE_NEW_CONSOLE,
                    )
                else:
                    messagebox.showinfo("BAGO", "bago.cmd no encontrado.")
                    return
            else:
                messagebox.showinfo("BAGO", "Abre una terminal y ejecuta: bago launch")
                return
            _append_text(self.fw_text, f"[bago launch abierto — PID {self._launch_proc.pid}]\n", tag="success")
        except Exception as exc:
            _append_text(self.fw_text, f"[error abriendo bago launch] {exc}\n", tag="error")

    def _stop_bago_launch(self):
        proc = getattr(self, "_launch_proc", None)
        if not proc:
            _append_text(self.fw_text, "[bago launch no está abierto]\n", tag="dim")
            return
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        except Exception as exc:
            _append_text(self.fw_text, f"[error cerrando] {exc}\n", tag="error")
        self._launch_proc = None
        _append_text(self.fw_text, "[bago launch cerrado]\n", tag="dim")


def main():
    root = tk.Tk()
    app = TwinDevWindow(root)
    root.mainloop()
