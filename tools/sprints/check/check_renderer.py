import sys
sys.path.insert(0, r"C:\Program Files\BAGO\.bago\chat")
import py_compile

for m in ["renderer", "renderer_text", "renderer_box", "repl", "repl_menu", "repl_chat"]:
    try:
        py_compile.compile(rf"C:\Program Files\BAGO\.bago\chat\{m}.py", doraise=True)
        print(f"  {m}: OK")
    except py_compile.PyCompileError as exc:
        print(f"  {m}: FAIL -- {exc}")

import renderer
print(f"_visible_width: {callable(renderer._visible_width)}")
print(f"_qwen_box: {callable(renderer._qwen_box)}")
print(f"bago_logo_text: {callable(renderer.bago_logo_text)}")
print(f"print_message_qwen: {callable(renderer.print_message_qwen)}")

with open(r"C:\Program Files\BAGO\renderer_check.txt", "w", encoding="utf-8") as f:
    f.write("renderer split OK")