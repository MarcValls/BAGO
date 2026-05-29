"""dev_twin.bridge — Gestión del puente unimodel persistente."""
import os
import subprocess
import threading
import tkinter as tk

from .constants import BAGO_ROOT, IS_WIN, THEME
from .utils import _append_text


def _hist_path():
    return os.path.expandvars(r"%LOCALAPPDATA%\BAGO\unimodel_history.json")


def _bridge_script():
    return BAGO_ROOT / ".bago" / "tools" / "bago_unimodel_bridge.py"


class UnimodelBridgeManager:
    """Encapsula el ciclo de vida del puente de chat unimodel."""

    def __init__(self, text_widget: tk.Text, provider_var, model_entry):
        self.text_widget = text_widget
        self.provider_var = provider_var
        self.model_entry = model_entry
        self.proc = None
        self.active = False

    def start(self):
        prov = self.provider_var.get()
        model = self.model_entry.get().strip()
        hist = _hist_path()
        script = _bridge_script()

        if not script.exists():
            _append_text(self.text_widget, f"[ERROR] Bridge no encontrado: {script}\n", "error")
            return

        cmd = [
            __import__("sys").executable,
            str(script),
            "--provider", prov,
            "--history-file", hist,
        ]
        if model:
            cmd.extend(["--model", model])

        _append_text(self.text_widget, f"\n[system] Iniciando modo unimodel ({prov}/{model or 'default'})...\n", "dim")

        popen_kw = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "stdin": subprocess.PIPE,
            "cwd": str(BAGO_ROOT),
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
        }
        if IS_WIN:
            popen_kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

        try:
            self.proc = subprocess.Popen(cmd, **popen_kw)
        except Exception as exc:
            _append_text(self.text_widget, f"[ERROR] {exc}\n", "error")
            return

        self.active = True
        self._start_reader()

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.stdin.write("EXIT\n")
                self.proc.stdin.flush()
            except Exception:
                pass
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.terminate()
                self.proc.wait(timeout=2)
        self.active = False
        _append_text(self.text_widget, "\n[system] Modo unimodel detenido.\n", "dim")

    def send(self, text: str):
        if self.proc and self.proc.poll() is None:
            _append_text(self.text_widget, f"\n\u003e {text}\n", "user_msg")
            try:
                self.proc.stdin.write(text + "\n")
                self.proc.stdin.flush()
            except Exception as exc:
                _append_text(self.text_widget, f"[ERROR] No se pudo enviar al puente: {exc}\n", "error")

    def switch(self, prov: str, model: str):
        if self.active and self.proc and self.proc.poll() is None:
            switch_cmd = f"SWITCH:{prov}:{model}" if model else f"SWITCH:{prov}:"
            try:
                self.proc.stdin.write(switch_cmd + "\n")
                self.proc.stdin.flush()
                _append_text(self.text_widget, f"\n[system] Cambiando a {prov}/{model or 'default'}...\n", "dim")
            except Exception as exc:
                _append_text(self.text_widget, f"[ERROR] No se pudo cambiar modelo: {exc}\n", "error")

    def _start_reader(self):
        def _reader():
            try:
                if self.proc.stdout:
                    for line in self.proc.stdout:
                        line_stripped = line.rstrip("\n\r")
                        tag = "dim" if line_stripped.startswith("[bridge]") else "assistant_msg"
                        self.text_widget.after(0, lambda l=line_stripped, t=tag: _append_text(self.text_widget, l + "\n", t))
            except Exception:
                pass
            finally:
                try:
                    self.proc.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    self.proc.terminate()
                    self.proc.wait(timeout=2)
                self.text_widget.after(0, self._on_exited)

        t = threading.Thread(target=_reader, daemon=True)
        t.start()

    def _on_exited(self):
        self.active = False
        _append_text(self.text_widget, "\n[system] El puente de IA se ha cerrado.\n", "dim")
