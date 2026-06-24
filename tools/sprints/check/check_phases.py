import sys
from pathlib import Path

sys.path.insert(0, r"C:\Program Files\BAGO\.bago\chat")
import importlib
from repl_autoload import PHASES, _import

chat_dir = Path(r"C:\Program Files\BAGO\.bago\chat")

for mod_name in ["repl_hook_post_input_aliases", "repl_hook_post_input_transcript",
                  "repl_hook_on_session_end"]:
    suffix = mod_name[len("repl_hook_"):]
    if "_" in suffix:
        phase, _ = suffix.split("_", 1)
    else:
        phase = suffix
    in_phases = phase in PHASES
    mod = _import(mod_name)
    run_callable = callable(getattr(mod, "run", None)) if mod else False
    on_attr = getattr(mod, "ON", "(unset)") if mod else "(import failed)"
    print(f"  {mod_name}: phase={phase!r} in_PHASES={in_phases} on={on_attr} run={run_callable}")