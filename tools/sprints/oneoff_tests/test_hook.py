"""test_hook_loads.py — verify repl_hook_on_boot loads and reads version."""
import sys
sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\.bago\chat")
for k in list(sys.modules.keys()):
    if k in ("repl_hook_on_boot", "renderer", "version"):
        del sys.modules[k]
import repl_hook_on_boot as h
import renderer as R
print("Version from renderer:", R._BAGO_VERSION)
print("Hook module loaded OK")
