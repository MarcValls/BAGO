"""test_dry_boot_work.py — verify boot from work copy at AppData\\Local\\BAGO."""
import os, sys, io
from unittest.mock import MagicMock

# IMPORTANT: cwd must be the work copy so _resolve_bago_version reads its
# release_version.txt
os.chdir(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO")
sys.path.insert(0, r".bago\chat")

# Mock core deps
sys.modules["session_manager"] = MagicMock()
sys.modules["switch_engine"] = MagicMock()

for k in list(sys.modules.keys()):
    if k in ("renderer", "version", "commands", "intent_engine", "system_prompt", "repl"):
        del sys.modules[k]

import repl as REPL_MOD
import renderer as R

print(f"cwd: {os.getcwd()}")
print(f"_BAGO_VERSION = {R._BAGO_VERSION!r}")
print(f"release_version.txt = {open('release_version.txt').read().strip()!r}")
print()

fake_session = MagicMock()
fake_session.status.return_value = {
    "provider": "ollama-local",
    "model": "llama3.2:3b",
    "total_tokens": 0,
    "health": {"ok": True, "detail": "ok"},
}

repl_cls = None
for name in dir(REPL_MOD):
    obj = getattr(REPL_MOD, name)
    if isinstance(obj, type) and "REPL" in name:
        repl_cls = obj
        break

if repl_cls:
    repl = repl_cls.__new__(repl_cls)
    repl.mgr = fake_session
    repl.base_path = "C:\\Users\\AMTEC_Terminal_1º\\AppData\\Local\\BAGO"

    out = io.StringIO()
    sys.stdout = out
    try:
        repl._print_banner()
        repl._print_status()
    finally:
        sys.stdout = sys.__stdout__
    print("=" * 70)
    print("DRY BOOT from WORK copy")
    print("=" * 70)
    print(out.getvalue())
