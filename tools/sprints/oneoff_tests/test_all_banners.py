"""test_all_banners.py — verifica banner de las 3 copias tras el patch."""
import sys, os

ROOTS = [
    r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO",
    r"C:\Users\AMTEC_Terminal_1º\.bago\dev",
    r"C:\Users\AMTEC_Terminal_1º\.bago\launch",
]

for root in ROOTS:
    print(f"\n========== {root} ==========")
    os.chdir(root)
    # Clear cached modules
    for k in list(sys.modules.keys()):
        if 'version' in k or 'renderer' in k:
            del sys.modules[k]
    sys.path.insert(0, r".bago\chat")
    try:
        import renderer as R
        print("VERSION:", R._BAGO_VERSION)
        b = R.banner()
        print(f"---BANNER (len={len(b)})---")
        print(b)
        print("---END---")
    except Exception as e:
        import traceback
        print(f"EXCEPTION: {type(e).__name__}: {e}")
        traceback.print_exc()
