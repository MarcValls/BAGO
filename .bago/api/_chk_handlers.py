import os
for f in sorted(os.listdir(r"C:\Program Files\BAGO\.bago\api")):
    if f.startswith("handlers_"):
        t = open(os.path.join(r"C:\Program Files\BAGO\.bago\api", f)).read()
        for needle in ["handle_config", "handle_shadow"]:
            if needle in t:
                print(f"  {f}: {needle}")
