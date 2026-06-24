"""test_inventory.py — measure how long inventory takes."""
import sys, time
from pathlib import Path

sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\.bago\tools")
sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\bago_core")

print("Starting inventory...", flush=True)
t0 = time.time()
from bago_inventory import gather_inventory, format_startup_text
data = gather_inventory(Path(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO"))
print(f"Done in {time.time()-t0:.1f}s", flush=True)
print("format_startup_text:", flush=True)
print(format_startup_text(data, limit=4), flush=True)
