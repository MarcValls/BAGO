import sys, traceback, os
os.chdir(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO")
sys.path.insert(0, r".bago\chat")
sys.stderr.write(f"PATH OK cwd={os.getcwd()}\n")
sys.stderr.flush()
try:
    import renderer as R
    sys.stderr.write(f"IMPORTED _BAGO_VERSION={getattr(R, '_BAGO_VERSION', '<MISSING>')!r}\n")
    sys.stderr.flush()
    b = R.banner()
    sys.stderr.write(f"BANNER OK len={len(b)}\n")
    sys.stderr.flush()
    print("VERSION:", R._BAGO_VERSION)
    print("---BANNER---")
    print(b)
    print("---END---")
    sys.stdout.flush()
except Exception as e:
    sys.stderr.write(f"EXCEPTION: {type(e).__name__}: {e}\n")
    traceback.print_exc()
    sys.stderr.flush()
