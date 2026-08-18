from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[2] / ".bago" / "api"

for f in sorted(API_ROOT.iterdir()):
    if f.name.startswith("handlers_") and f.is_file():
        t = f.read_text(encoding="utf-8")
        for needle in ["handle_config", "handle_shadow"]:
            if needle in t:
                print(f"  {f}: {needle}")
