"""End-to-end check: repl loads, autoloader discovers all extensions."""
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Program Files\BAGO\.bago\chat")
out = []

# 1) import the autoloader + repl.
from repl_autoload import discover_commands, discover_hooks
import repl  # noqa

# 2) Discover what's available.
chat_dir = Path(r"C:\Program Files\BAGO\.bago\chat")
cmds = discover_commands(chat_dir)
hooks = discover_hooks(chat_dir)

out.append(f"slash commands discovered: {len(cmds)}")
for cmd in sorted(cmds):
    out.append(f"  {cmd}")

out.append("")
out.append(f"lifecycle hooks discovered: {sum(len(v) for v in hooks.values())}")
for phase, fns in hooks.items():
    if fns:
        out.append(f"  {phase}: {len(fns)} handler(s)")
        for fn in fns:
            out.append(f"    - {fn.__module__}.{fn.__name__}")

out.append("")
out.append(f"repl.run: {hasattr(repl.BagoREPL, 'run')}")

# 3) Try to instantiate (without an LLM session).
try:
    repl_inst = repl.BagoREPL(
        provider="ollama-local",
        model="llama3.2:3b",
        system_prompt="test",
        base_path=r"C:\Program Files\BAGO",
        state_root=None,
    )
    out.append(f"instantiation: OK (auto_commands={len(repl_inst._auto_commands)}, hooks={sum(len(v) for v in repl_inst._auto_hooks.values())})")
    repl_inst.mgr.close()
except Exception as exc:
    out.append(f"instantiation: FAIL -- {exc}")

text = "\n".join(out)
print(text)
with open(r"C:\Program Files\BAGO\autoload_full_check.txt", "w", encoding="utf-8") as f:
    f.write(text)