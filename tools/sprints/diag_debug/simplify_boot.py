"""Simplify the BAGO REPL boot sequence so it matches Qwen's "just start typing".

Changes:
1. _auto_evolve_startup: off by default at boot, opt-in via /evolve.
2. print_workspace_inventory: removed from boot, available via /inventory.
3. _interactive_startup: skipped at boot (only on /setup).
4. _maybe_show_welcome: skipped at boot.
5. /model alias added that switches only the model of the active provider.
6. /inventory and /evolve as new slash commands.
"""
from pathlib import Path

P = Path(r"C:\Program Files\BAGO\.bago\chat\repl.py")
text = P.read_text(encoding="utf-8")

# 1. Strip boot extras from run().
old_run = '''            self._setup_readline()
            self._print_banner()
            self._print_init_warnings()
            self._auto_evolve_startup()
            self._interactive_startup()
            self._maybe_show_welcome()
            try:
                print_workspace_inventory(self.base_path)
            except Exception as e:
                print(R.warn(f"Inventory no disponible: {e}"))
            self.running = True'''
new_run = '''            self._setup_readline()
            self._print_banner()
            self._print_init_warnings()
            # Boot is fast: skip autoevolve, interactive wizard, welcome, and
            # inventory by default. Available on demand via /evolve /setup
            # /welcome /inventory. This matches Qwen's "type and go" UX.
            self.running = True'''
if old_run in text:
    text = text.replace(old_run, new_run, 1)
    print("step 1: boot stripped OK")
else:
    print("step 1: old_run block not found")
    raise SystemExit(1)

# 2. Add /model alias in _handle_command. We hook into the existing dispatch
# by adding an early branch.
old_handle_command = '''        low = line.strip().lower()
        if low == "/":
            return self._show_menu()'''
new_handle_command = '''        low = line.strip().lower()
        # Qwen-style: /model <name> switches just the model of the active provider.
        if low.startswith("/model"):
            parts = line.strip().split(maxsplit=1)
            if len(parts) < 2:
                print(R.warn("Uso: /model <nombre>"))
                return True
            new_model = parts[1].strip()
            try:
                provider = getattr(self.mgr, "provider", None) or ""
                response = self.mgr.switch_provider(provider, new_model, False, self.mode)
                print(R.ok(f"\u2713 model -> {provider}:{new_model}"))
            except Exception as exc:
                print(R.error(f"Model switch fall\u00f3: {exc}"))
            return True
        # /inventory on demand (replaces the boot-time print).
        if low == "/inventory":
            try:
                print_workspace_inventory(self.base_path)
            except Exception as e:
                print(R.warn(f"Inventory no disponible: {e}"))
            return True
        # /evolve runs the auto-evolve on demand.
        if low == "/evolve":
            self._auto_evolve_startup()
            return True
        if low == "/":
            return self._show_menu()'''
if old_handle_command in text:
    text = text.replace(old_handle_command, new_handle_command, 1)
    print("step 2: /model + /inventory + /evolve added OK")
else:
    print("step 2: _handle_command marker not found")
    raise SystemExit(1)

P.write_text(text, encoding="utf-8")
print("done")