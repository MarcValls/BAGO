import sys
from pathlib import Path

sys.path.insert(0, r"C:\Program Files\BAGO\.bago\chat")
from repl_autoload import discover_hooks, PHASES

chat_dir = Path(r"C:\Program Files\BAGO\.bago\chat")
hooks = discover_hooks(chat_dir)
print("PHASES:", PHASES)
print("discovered hooks:")
total = 0
for p, fns in hooks.items():
    if fns:
        print(f"  {p}: {len(fns)} handler(s)")
        total += len(fns)
        for fn in fns:
            print(f"    {fn.__module__}.{fn.__name__}")
print(f"total: {total} hooks")

# Force-import each hook module and check `run` attribute.
import importlib
for mod_name in ["repl_hook_post_input_aliases", "repl_hook_post_input_transcript",
                  "repl_hook_on_session_end"]:
    try:
        mod = importlib.import_module(mod_name)
        run = getattr(mod, "run", None)
        print(f"  {mod_name}: ON={getattr(mod, 'ON', '(unset)')} run={callable(run)}")
    except Exception as exc:
        print(f"  {mod_name}: FAIL -- {exc}")
with open(r"C:\Program Files\BAGO\hook_debug.txt", "w", encoding="utf-8") as f:
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        pass
    f.write("ok")