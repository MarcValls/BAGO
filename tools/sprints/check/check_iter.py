import sys
from pathlib import Path

sys.path.insert(0, r"C:\Program Files\BAGO\.bago\chat")
from repl_autoload import _iter_extension_modules

chat_dir = Path(r"C:\Program Files\BAGO\.bago\chat")
names = list(_iter_extension_modules(chat_dir))
out = "\n".join(names) or "(empty)"
print(out)
with open(r"C:\Program Files\BAGO\iter_check.txt", "w", encoding="utf-8") as f:
    f.write(out)