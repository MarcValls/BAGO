import sys
from pathlib import Path

sys.path.insert(0, r"C:\Program Files\BAGO\.bago\tools")
BAGO_ROOT = Path(r"C:\Program Files\BAGO")

# Backup before testing.
import shutil
lessons = BAGO_ROOT / ".bago" / "knowledge" / "learned_lessons.md"
backup = lessons.with_suffix(".md.bak.test")
shutil.copy2(lessons, backup)
print(f"backup -> {backup}")

from append_lesson import append_lesson

block = """## LL-NNN — Test lesson from dry-run

> **Fecha:** 2026-06-22
> **Trigger:** session dry-run test

### Lección

Esta lección se generó desde un test automático para verificar que append_lesson funciona end-to-end.
"""

result = append_lesson(BAGO_ROOT, block)
print(result)

# Read the result to verify it landed.
text = lessons.read_text(encoding="utf-8")
print("--- last 5 lines ---")
print("\n".join(text.splitlines()[-5:]))

# Restore.
shutil.copy2(backup, lessons)
backup.unlink()
print(f"restored from {backup}")