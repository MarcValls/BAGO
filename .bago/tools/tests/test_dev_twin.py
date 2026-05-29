"""Pruebas unitarias para bago_dev_twin.py — sin bloquear en mainloop."""
import sys
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bago_dev_twin as bdt


def test_can_import_and_instantiate_ui():
    root = tk.Tk()
    root.withdraw()
    app = bdt.TwinDevWindow(root)
    assert app.ai_text is not None
    assert app.fw_text is not None
    assert app.ai_entry is not None
    assert app.fw_entry is not None
    root.destroy()


def test_append_text():
    root = tk.Tk()
    root.withdraw()
    txt = tk.Text(root)
    bdt._append_text(txt, "hello", "")
    assert "hello" in txt.get("1.0", tk.END)
    root.destroy()


def test_run_validate_in_text_widget():
    """Ejecuta 'bago validate' capturando stdout en un Text widget."""
    import time
    root = tk.Tk()
    root.withdraw()
    txt = tk.Text(root)
    txt.pack()

    bago_cmd = bdt.BAGO_ROOT / "bago.cmd"
    cmd = ["cmd", "/c", str(bago_cmd), "validate"]
    proc = bdt._run_in_pane(txt, cmd)
    assert proc is not None

    for _ in range(300):
        if proc.poll() is not None:
            break
        time.sleep(0.1)

    assert proc.returncode == 0, f"stdout capture failed: {txt.get('1.0', tk.END)}"
    output = txt.get("1.0", tk.END)
    assert "validate" in output.lower() or "GO" in output or "bago" in output.lower()
    root.destroy()


def test_bago_chat_panel_elements_exist():
    """Verifica que existen los controles del panel BAGO Chat tras la refactorización."""
    root = tk.Tk()
    root.withdraw()
    app = bdt.TwinDevWindow(root)
    assert hasattr(app, "bago_session")
    assert app.bago_session is None
    root.destroy()


def test_start_stop_bago_chat_no_crash():
    """Iniciar y detener bago chat sin que esté activo no debe fallar."""
    root = tk.Tk()
    root.withdraw()
    app = bdt.TwinDevWindow(root)
    app._stop_bago_chat()  # no activo: solo mensaje informativo
    assert app.bago_session is None
    root.destroy()


def test_ai_entry_when_chat_inactive():
    """Enviar texto sin chat activo debe delegar a run_ai_cmd sin bloquear."""
    root = tk.Tk()
    root.withdraw()
    app = bdt.TwinDevWindow(root)
    app.ai_entry.insert(0, "help")
    app.on_ai_entry()  # sin chat activo, ejecuta como comando suelto
    root.destroy()
