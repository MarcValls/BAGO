"""audit_bago_full.py — exhaustive inventory of every BAGO installation."""
import os
import sys
from pathlib import Path

# Roots where BAGO can live
ROOTS = [
    Path(r"C:\Program Files\BAGO"),
    Path(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO"),
    Path(r"C:\Users\AMTEC_Terminal_1º\.bago"),
    Path(r"C:\Users\AMTEC_Terminal_1º\Downloads"),
    Path(r"C:\Users\AMTEC_Terminal_1º\Desktop"),
    Path(r"C:\Users\AMTEC_Terminal_1º\Documents"),
]

print("=" * 80)
print("BAGO INSTALLATIONS ON THIS MACHINE")
print("=" * 80)

def file_count(root: Path, pattern: str) -> int:
    if not root.exists():
        return 0
    return sum(1 for _ in root.rglob(pattern))


for root in ROOTS:
    if not root.exists():
        continue
    print(f"\n{root}")
    print(f"  exists: {root.exists()}")
    # Count key file types
    print(f"  .py files:    {file_count(root, '*.py')}")
    print(f"  .md files:    {file_count(root, '*.md')}")
    print(f"  .json files:  {file_count(root, '*.json')}")
    print(f"  .pyc files:   {file_count(root, '*.pyc')}")

# Find ALL directories named BAGO or bago anywhere on C:
print()
print("=" * 80)
print("ALL 'BAGO' / 'bago' DIRECTORIES FOUND ON C:\\")
print("=" * 80)

import subprocess
result = subprocess.run(
    ["powershell", "-NoProfile", "-Command",
     "Get-ChildItem -Path 'C:\\' -Recurse -Directory -ErrorAction SilentlyContinue "
     "| Where-Object { $_.Name -match '^[Bb][Aa][Gg][Oo]' } "
     "| Select-Object FullName | Out-String"],
    capture_output=True,
    timeout=120,
)
print(result.stdout.decode("utf-8", errors="replace"))

# Find all bago*.py / BAGO*.py
print()
print("=" * 80)
print("ALL 'bago*.py' / 'BAGO*.py' FILES ON C:\\")
print("=" * 80)
result = subprocess.run(
    ["powershell", "-NoProfile", "-Command",
     "Get-ChildItem -Path 'C:\\' -Recurse -Filter 'bago*.py' -ErrorAction SilentlyContinue "
     "| Select-Object FullName, Length, LastWriteTime | Format-Table -AutoSize | Out-String"],
    capture_output=True,
    timeout=120,
)
print(result.stdout.decode("utf-8", errors="replace")[:3000])
