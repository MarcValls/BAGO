import sys
sys.path.insert(0, r"C:\Program Files\BAGO\.bago\chat")
out = []
for name, fn in [
    ("repl_banner", "print_banner"),
    ("repl_status", "print_status"),
    ("repl_prompt", "print_chat_prompt"),
    ("repl_prompt", "prompt"),
    ("repl_prompt", "handle_pasted_block"),
    ("repl_navigation", "setup_readline"),
    ("repl_navigation", "navigate"),
    ("repl_history", "FileHistory"),
    ("repl_chat", "handle_chat"),
]:
    try:
        m = __import__(name)
        attr = getattr(m, fn, None)
        out.append(f"  {name}.{fn}: {callable(attr) or type(attr).__name__}")
    except Exception as exc:
        out.append(f"  {name}: FAIL -- {exc}")
print("\n".join(out))
with open(r"C:\Program Files\BAGO\diag_modules.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))