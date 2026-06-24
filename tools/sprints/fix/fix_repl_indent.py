"""Fix the indentation bug in repl.py that swallowed BagoREPL methods into _SafeFileHistory.

Bug shape:
- Line 361: class BagoREPL(BagoReplMenuMixin): (column 0)
- Line 571: class _SafeFileHistory(FileHistory): (column 0)
- The `def store_string` of _SafeFileHistory at line 573 has its body at
  8 spaces and extends ~250 lines. The next `def` at column 4 (line 581,
  _read_main_input) was therefore parsed as ANOTHER method of
  _SafeFileHistory, swallowing all of BagoREPL's real methods (including
  `run` at line 822) into the wrong class.

Fix:
- Backup to repl.py.bak
- Find the boundary of _SafeFileHistory's real body (the 8-space lines
  that belong to store_string's body) vs the displaced methods at column 4.
- Trim _SafeFileHistory to just `class _SafeFileHistory(FileHistory):` +
  docstring + `store_string` + a proper body close.
- Reinsert the displaced methods into BagoREPL, between the last BagoREPL
  method (_use_prompt_toolkit) and the class _SafeFileHistory line.
- Verify BagoREPL.run is callable.
- On failure, restore the backup automatically.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPL = Path(r"C:\Program Files\BAGO\.bago\chat\repl.py")
BAK = REPL.with_suffix(".py.bak")


def main() -> int:
    if not REPL.exists():
        print(f"FAIL: {REPL} missing")
        return 1

    shutil.copy2(REPL, BAK)
    print(f"backup -> {BAK}")

    text = REPL.read_text(encoding="utf-8")
    lines = text.split("\n")

    # 1. Locate class boundaries (column-0 `class` lines).
    class_lines = [i for i, line in enumerate(lines) if line.startswith("class ")]
    bago_idx = class_lines[0]
    safe_idx = class_lines[1] if len(class_lines) > 1 else None

    print(f"BagoREPL starts at line {bago_idx + 1}")
    print(f"_SafeFileHistory starts at line {safe_idx + 1 if safe_idx else 'EOF'}")

    # 2. The block between safe_idx (inclusive) and the next column-0
    # `def` or end-of-file is the region we need to split.
    # In that block, anything at column 0/4/8 must be classified:
    #   - column 0: class/import statements (keep)
    #   - column 4 "    def ...": a class-level method definition
    #   - column 4 blank or other 4-space: continuation / docstring / etc.
    # The fix: the FIRST `    def store_string` belongs to _SafeFileHistory.
    # Everything after that, until the file end (or next class at col 0),
    # is wrongly attached. We need to:
    #   - Keep: class line, docstring, `    def store_string`, its body (8+ spaces)
    #   - Move: every subsequent `    def ...` and its body back into BagoREPL.

    # Scan from safe_idx forward.
    block = lines[safe_idx:]
    out = []
    # Always keep the class header line + its docstring line(s).
    i = 0
    out.append(block[i])  # class _SafeFileHistory(FileHistory):
    i += 1
    # Optional docstring (line starting with 4 spaces then `"""`).
    while i < len(block) and re.match(r'^    (""".*""")?\s*$', block[i]) and '"""' in block[i]:
        out.append(block[i])
        i += 1

    # Now keep the first `def store_string` and its body.
    store_started = False
    while i < len(block):
        line = block[i]
        if not store_started:
            if line.startswith("    def store_string"):
                out.append(line)
                store_started = True
                i += 1
                continue
            # Skip anything unexpected between class header and store_string
            i += 1
            continue
        # store_started is True. Keep lines that are part of store_string's body
        # (indent >= 8 OR blank line). Stop when we see another column-4 `def`.
        if line.strip() == "":
            out.append(line)
            i += 1
            continue
        if line.startswith("    def "):
            # End of store_string body. Stop keeping.
            break
        # Anything more indented (>=8 spaces) belongs to store_string body.
        out.append(line)
        i += 1
    safe_tail = out  # the trimmed _SafeFileHistory class.

    # Everything from i onward in block is wrongly attached code.
    # It starts with `    def _read_main_input(...)` and continues until
    # the next column-0 statement (top-level def/if/etc.) or end of block.
    displaced = []
    while i < len(block):
        line = block[i]
        if line.startswith("def ") or line.startswith("if __name__"):
            # Top-level code (e.g., the trailing `if __name__ == "__main__":`
            # and `BagoREPL().run()`). Stop collecting displaced methods.
            break
        displaced.append(line)
        i += 1

    # The remainder of block (from i onward) is top-level code that comes
    # AFTER both classes (e.g., _run_tests, the __main__ guard).
    top_tail = block[i:]

    # 3. Reassemble:
    #    [lines 0..safe_idx) + displaced + safe_tail + top_tail
    new_lines = lines[:safe_idx] + displaced + safe_tail + top_tail

    # 4. Defensive: dedent the displaced methods by 0 (they were already at
    #    column 4 within BagoREPL — that was correct). The bug was the
    #    PARENT class, not the indent level. So no dedent needed.
    #    But: check that the FIRST displaced line is `    def ...` to confirm.
    if not displaced or not displaced[0].lstrip().startswith("def "):
        print(f"FAIL: displaced block doesn't start with `def`: {displaced[:3] if displaced else '(empty)'}")
        shutil.copy2(BAK, REPL)
        return 3

    new_text = "\n".join(new_lines)
    REPL.write_text(new_text, encoding="utf-8")
    print(f"wrote {REPL} ({len(new_text)} bytes, {len(new_lines)} lines)")

    # 5. Verify by importing in a fresh subprocess.
    probe = (
        "import sys; "
        "sys.path.insert(0, r'C:\\Program Files\\BAGO\\.bago\\chat'); "
        "import repl; "
        "print('run:', hasattr(repl.BagoREPL, 'run')); "
        "print('store_string in _SafeFileHistory:', 'store_string' in vars(repl._SafeFileHistory)); "
        "print('read_main_input in BagoREPL:', '_read_main_input' in vars(repl.BagoREPL)); "
    )
    result = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, timeout=30)
    print("--- verify ---")
    print(result.stdout)
    if result.stderr:
        print("STDERR:")
        print(result.stderr)

    if "run: True" in result.stdout:
        print("OK: BagoREPL.run() is restored.")
        return 0

    print("FAIL: BagoREPL.run() still missing. Restoring backup.")
    shutil.copy2(BAK, REPL)
    return 2


if __name__ == "__main__":
    sys.exit(main())