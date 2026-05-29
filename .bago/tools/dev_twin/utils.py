"""dev_twin.utils — Helpers de UI y ejecución de comandos."""
import subprocess
import tkinter as tk

from .constants import BAGO_ROOT, IS_WIN


def _append_text(widget: tk.Text, text: str, tag: str = ""):
    widget.configure(state=tk.NORMAL)
    if tag:
        widget.insert(tk.END, text, tag)
    else:
        widget.insert(tk.END, text)
    widget.see(tk.END)
    widget.configure(state=tk.DISABLED)


def _run_in_pane(text_widget: tk.Text, cmd: list[str], cwd=None):
    """Ejecuta un comando y redirige stdout/stderr al text widget."""
    from .constants import BAGO_ROOT
    _append_text(text_widget, f"$ {' '.join(cmd)}\n", "prompt")

    popen_kw = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "stdin": subprocess.PIPE,
        "cwd": str(cwd or BAGO_ROOT),
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if IS_WIN:
        popen_kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

    try:
        proc = subprocess.Popen(cmd, **popen_kw)
    except Exception as exc:
        _append_text(text_widget, f"[ERROR] {exc}\n", "error")
        return None

    def _reader():
        try:
            if proc.stdout:
                for line in proc.stdout:
                    text_widget.after(0, lambda l=line: _append_text(text_widget, l))
        except Exception:
            pass
        finally:
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                proc.terminate()
                proc.wait(timeout=2)
            code = proc.returncode
            text_widget.after(
                0,
                lambda: _append_text(
                    text_widget, f"\n[exit code {code}]\n\n", "dim" if code == 0 else "error"
                ),
            )

    t = __import__("threading").Thread(target=_reader, daemon=True)
    t.start()
    return proc
