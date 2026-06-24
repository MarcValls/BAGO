"""Verify the autoloader discovers all repl_cmd_*.py modules."""
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Program Files\BAGO\.bago\chat")
from repl_autoload import discover_commands

chat_dir = Path(r"C:\Program Files\BAGO\.bago\chat")
cmds = discover_commands(chat_dir)
out = [f"discovered {len(cmds)} commands:"]
for cmd in sorted(cmds):
    out.append(f"  {cmd}")
print("\n".join(out))
with open(r"C:\Program Files\BAGO\autoload_check.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))