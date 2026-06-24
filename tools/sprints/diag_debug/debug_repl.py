"""Diagnostico del bug de BagoREPL.run()."""
import sys

p = r"C:\Program Files\BAGO\.bago\chat\repl.py"
src = open(p, encoding="utf-8").read()
ls = src.split("\n")
print("total lines:", len(ls))
checkpoints = [570, 571, 572, 573, 600, 700, 800, 820, 821, 822, 830]
for i in checkpoints:
    if i < len(ls):
        print(f"L{i+1}: {ls[i]!r}")

sys.path.insert(0, r"C:\Program Files\BAGO\.bago\chat")
# Force a fresh import (no cache)
for mod in list(sys.modules):
    if "repl" in mod:
        del sys.modules[mod]
import repl
cls = repl.BagoREPL
print("\nvars(BagoREPL) keys:", list(vars(cls).keys()))
print("'run' in __dict__:", "run" in cls.__dict__)
print("__module__:", cls.__module__)
# Find where run is if anywhere
for c in cls.__mro__:
    if "run" in c.__dict__:
        print(f"  'run' found in MRO class: {c.__name__} (file: {getattr(c, '__module__', '?')})")