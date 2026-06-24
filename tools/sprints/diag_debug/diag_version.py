import sys
sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\bago_core")
import version as V
print("version module path:", V.__file__)
print("CURRENT:", V.CURRENT)
print("_read_release_version source:")
import inspect
print(inspect.getsource(V._read_release_version))
