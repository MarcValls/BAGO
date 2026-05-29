"""dev_twin.constants — Constantes y configuración del tema."""
from pathlib import Path
import sys

BAGO_ROOT = Path(__file__).resolve().parents[3]
IS_WIN = sys.platform == "win32"

THEME = {
    "bg": "#1e1e1e",
    "fg": "#d4d4d4",
    "text_bg": "#0e0e0e",
    "input_bg": "#252526",
    "btn_bg": "#3c3c3c",
    "btn_active": "#505050",
    "accent_ai": "#c586c0",
    "accent_fw": "#4ec9b0",
    "prompt": "#569cd6",
    "error": "#f48771",
    "dim": "#808080",
    "success": "#b5cea8",
    "user_msg": "#9cdcfe",
    "assistant_msg": "#ce9178",
    "unimodel_on": "#2d6a4f",
}
