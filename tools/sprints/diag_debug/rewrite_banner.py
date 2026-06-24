"""Reescribe _print_banner y banner() para que el arranque sea limpio y
coherente, sin parches acumulativos.
"""
from pathlib import Path

REPL = Path(r"C:\Program Files\BAGO\.bago\chat\repl.py")
RENDERER = Path(r"C:\Program Files\BAGO\.bago\chat\renderer.py")

# ---------------------------------------------------------------------------
# REESCRIBIR _print_banner en repl.py
# ---------------------------------------------------------------------------
repl_text = REPL.read_text(encoding="utf-8")

old_banner = '''    def _print_banner(self) -> None:
        provider = ""
        model = ""
        cwd = ""
        try:
            mgr = getattr(self, "mgr", None)
            if mgr is not None:
                # Try a sequence of places provider/model might live.
                for source in (
                    mgr,
                    getattr(mgr, "session", None),
                    getattr(mgr, "_adapter", None),
                ):
                    if source is None:
                        continue
                    provider = provider or getattr(source, "provider", "") or ""
                    model = model or getattr(source, "model", "") or ""
                # Fallback to config defaults.
                cfg = getattr(mgr, "config", None)
                if cfg:
                    provider = provider or getattr(cfg, "default_provider", "") or ""
                    model = model or getattr(cfg, "default_model", "") or ""
            cwd = str(getattr(self, "base_path", "") or "~")
        except Exception:
            pass
        try:
            from renderer import qwen_status_block
            import renderer as _rend_mod
            _rend_mod._QWEN_STATUS_BLOCK = qwen_status_block(provider=provider, model=model, cwd=cwd)
        except Exception:
            pass
        print(R.banner())
        print()
        # Welcome box Qwen-style (mismo lenguaje visual que los mensajes).
        try:
            R.print_message_qwen(
                "system",
                f"Bienvenido a BAGO {BAGO_VERSION}. Escribe / para comandos.\\n"
                "El contexto de sesi\u00f3n sobrevive al cambio de provider."
            )
        except Exception:
            print(R.info(f"Bienvenido a BAGO {BAGO_VERSION}. Escribe / para comandos."))
            print(R.dim("El contexto de sesi\u00f3n sobrevive al cambio de provider."))
        print()'''

new_banner = '''    def _print_banner(self) -> None:
        """Boot banner.

        Layout (one section at a time, no nested frames, no peer blocks):

            [ B-A-G-O block letters, monospace, accent color ]
            [ version line, dim ]
            [ \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500 ]
              Bienvenido a BAGO 4.7.0  \u2014  escribe / para comandos.
              El contexto de sesi\u00f3n sobrevive al cambio de provider.
        """
        import shutil as _sh
        import renderer as _rend_mod

        # 1. Logo + version
        logo_text = _rend_mod.bago_logo_text()
        version_line = f"v{BAGO_VERSION} \u2014 Session-First AI Chat"

        cols = _sh.get_terminal_size((100, 20)).columns
        logo_w = _rend_mod._visible_width(logo_text.split("\\n")[0])  # width of widest line
        target_w = max(logo_w, len(version_line), 56)
        target_w = min(target_w, max(60, cols - 2))

        print()
        for line in logo_text.split("\\n"):
            centered = line.center(target_w)
            print(R.accent(centered))
        print(R.dim(version_line.center(target_w)))
        # separator
        sep_w = min(target_w, 60)
        print(R.dim("\u2500" * sep_w))
        # Welcome
        print(R.dim("  Bienvenido a BAGO. Escribe / para comandos."))
        print(R.dim("  El contexto de sesi\u00f3n sobrevive al cambio de provider."))
        print()'''

if old_banner not in repl_text:
    print("REPL: old banner block not found")
    raise SystemExit(1)
repl_text = repl_text.replace(old_banner, new_banner, 1)

# Update the call site: run() should NOT call print_workspace_inventory
# directly; we'll move that to the new single-line inventory box.
old_run_block = '''            self._auto_evolve_startup()
            self._interactive_startup()
            self._print_status()
            self._maybe_show_welcome()
            try:
                print_workspace_inventory(self.base_path)
            except Exception as e:
                print(R.warn(f"Failed to print workspace inventory: {e}"))
            self.running = True'''
new_run_block = '''            self._auto_evolve_startup()
            self._interactive_startup()
            self._maybe_show_welcome()
            try:
                print_workspace_inventory(self.base_path)
            except Exception as e:
                print(R.warn(f"Inventory no disponible: {e}"))
            self._print_status()
            self.running = True'''
if old_run_block in repl_text:
    repl_text = repl_text.replace(old_run_block, new_run_block, 1)

# Also drop the per-turn _print_status calls in run() except for chat normal
# and slash paths. Keep them only where they add value.
# Easier: remove all internal _print_status calls except the final one before
# shutting down. We achieve this by replacing the pattern.
import re as _re
repl_text = _re.sub(r"\s+self\._print_status\(\)\n", "\n", repl_text)
# Re-add the chat normal status print before the chat handler:
old_chat_normal = '''                # Chat normal
                R.print_message_qwen("user", stripped)
                self._handle_chat(stripped)
                self._print_status()'''
new_chat_normal = '''                # Chat normal
                R.print_message_qwen("user", stripped, state="sent")
                self._handle_chat(stripped)'''
if old_chat_normal in repl_text:
    repl_text = repl_text.replace(old_chat_normal, new_chat_normal, 1)

REPL.write_text(repl_text, encoding="utf-8")
print(f"rewrote {REPL}")

# ---------------------------------------------------------------------------
# AÑADIR bago_logo_text() en renderer.py: devuelve el logo en texto plano,
# sin color, sin recuadro. Cada línea ya está en su propia línea.
# ---------------------------------------------------------------------------
rd_text = RENDERER.read_text(encoding="utf-8")

old_marker = "def banner() -> str:"
new_func = '''def bago_logo_text() -> str:
    """B-A-G-O block letters as plain text (no color, no box).

    5 rows x 24 cols. Caller is responsible for colorizing and centering.
    """
    B = [
        "████  ",
        "█   █ ",
        "█   █ ",
        "████  ",
        "█   █ ",
    ]
    A = [
        " ██  ",
        "█  █ ",
        "████ ",
        "█  █ ",
        "█  █ ",
    ]
    G = [
        " ███ ",
        "█    ",
        "█ ██ ",
        "█  █ ",
        " ██  ",
    ]
    O = [
        " ██  ",
        "█  █ ",
        "█  █ ",
        "█  █ ",
        " ██  ",
    ]
    return "\\n".join(" ".join([B[r], A[r], G[r], O[r]]) for r in range(5))


def banner() -> str:'''

if "def bago_logo_text" in rd_text:
    print("bago_logo_text already exists; skipping")
else:
    if old_marker not in rd_text:
        print("RENDERER: banner() marker not found")
        raise SystemExit(1)
    rd_text = rd_text.replace(old_marker, new_func, 1)
    RENDERER.write_text(rd_text, encoding="utf-8")
    print(f"added bago_logo_text to {RENDERER}")