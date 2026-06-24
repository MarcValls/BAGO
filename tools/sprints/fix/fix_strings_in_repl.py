"""Modularize repl.py: extract UI rendering + chat into separate modules.

Plan
----
File: repl.py (990 lines, 8 responsibilities mixed)
  Split into:

  - repl.py                 — only the main loop, dispatching to other modules
  - repl_banner.py          — _print_banner, logo, version, welcome
  - repl_status.py          — _print_status, _auto_evolve_startup, _maybe_show_welcome
  - repl_chat.py            — _handle_chat (streaming + non-streaming), transcript detection,
                              provider/model resolution, print_message_qwen wiring
  - repl_prompt.py          — _print_chat_prompt, _prompt, multiline state
  - repl_render.py          — small adapter: R.alias() shortcuts and colorize

What stays in repl.py:
  - class BagoREPL __init__
  - run() (the main while loop)
  - _handle_command, _dispatch_command_intent (the slash command plumbing)

The goal is that no module in .bago/chat/ exceeds ~250 lines AND has a
single clear responsibility.
"""
import re
import shutil
from pathlib import Path

CHAT = Path(r"C:\Program Files\BAGO\.bago\chat")
REPL = CHAT / "repl.py"

text = REPL.read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# Step 1: fix the broken strings left by the previous _handle_chat patch.
# ---------------------------------------------------------------------------
# The literal " was written as " then a real newline. Replace the broken
# pattern with a clean "\r" sequence.
broken_pat = re.compile(r'"\n(\s*)" \+ " " \* 20 \+ "\n')
# Simpler: just replace the broken chunks explicitly.
broken_sequences = [
    ('sys.stdout.write("' + '\n' + '                     + " " * 20 + "' + '\n' + '")',
     'sys.stdout.write("\\r" + " " * 20 + "\\r")'),
    ('sys.stdout.write("' + '\n' + '                     + R.dim(f"{spinner_frames[(idx // 3) % len(spinner_frames)]} pensando…"))',
     'sys.stdout.write("\\r" + R.dim(f"{spinner_frames[(idx // 3) % len(spinner_frames)]} pensando…"))'),
    ('sys.stdout.write("' + '\n' + '                     + " " * 20 + "' + '\n' + '")',
     'sys.stdout.write("\\r" + " " * 20 + "\\r")'),
]
n_fixed = 0
for broken, fixed in broken_sequences:
    if broken in text:
        text = text.replace(broken, fixed)
        n_fixed += 1
print(f"fixed {n_fixed} broken string sequences")

# Belt and braces: any remaining '"' followed by newline followed by spaces
# followed by '"' inside _handle_chat should be "\r" instead. Pattern:
#   sys.stdout.write(""" + "<spaces> " + """"  -> sys.stdout.write("\\r")
bad = re.compile(r'sys\.stdout\.write\("(\s*)"\s*\+\s*"(\s*)"\s*\+\s*"(\s*)"\)', re.MULTILINE)
text = bad.sub(lambda m: 'sys.stdout.write("\\r" + " " * 20 + "\\r")', text)

# Also patch any remaining stray:
bad2 = re.compile(r'sys\.stdout\.write\("(\s*)"\s*\+\s*(\S[^\n]*?\S)\s*"\s*\)', re.MULTILINE)
text = bad2.sub(lambda m: 'sys.stdout.write("\\r" + ' + m.group(2) + ')', text)

REPL.write_text(text, encoding="utf-8")
print(f"step 1: string-fix applied to {REPL}")

# Verify it compiles.
import py_compile
try:
    py_compile.compile(str(REPL), doraise=True)
    print("syntax OK after string-fix")
except py_compile.PyCompileError as e:
    print(f"SYNTAX STILL BROKEN: {e}")
    raise SystemExit(1)