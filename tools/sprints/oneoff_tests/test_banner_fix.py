"""Smoke test for the banner fix on 2026-06-24."""
import sys
sys.path.insert(0, r"C:\Program Files\BAGO\.bago\chat")

from repl_banner import print_banner

class FakeRepl:
    base_path = r"C:\test\workspace"

# 1. print_banner must not raise
print_banner(FakeRepl())
print("=" * 60)

# 2. R.banner() must return a string (the wrapper guarantees it)
import renderer as R
result = R.banner()
assert isinstance(result, str), f"banner() returned {type(result)}"
assert len(result) > 0, "banner() returned empty string"
assert "BAGO" in result or "bago" in result.lower(), "banner missing BAGO reference"
print("All banner assertions passed.")
print("=" * 60)
print("RESULT LENGTH:", len(result))
print("FIRST LINE:", result.split(chr(10))[0])
