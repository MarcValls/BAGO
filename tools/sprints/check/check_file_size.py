import sys
from pathlib import Path

sys.path.insert(0, r"C:\Program Files\BAGO\.bago\tools")
from file_size_guard import scan_repo, format_report

BAGO_ROOT = Path(r"C:\Program Files\BAGO")
findings = scan_repo(BAGO_ROOT)
text = format_report(findings)
print(text)
with open(r"C:\Program Files\BAGO\file_size_check.txt", "w", encoding="utf-8") as f:
    f.write(text)