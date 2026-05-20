from pathlib import Path

txt = Path("bago_core/launcher.py").read_text(encoding="utf-8")

old = '''_candidate_roots = [
    _bago_core_dir.parent / ".bago",     # repo mode: <root>/.bago
    _bago_core_dir / ".bago",            # package mode: .bago inside bago_core
]'''

new = '''_user_active = Path.home() / ".bago" / "active" / ".bago"
_candidate_roots = [
    _bago_core_dir.parent / ".bago",     # repo mode: <root>/.bago
    _bago_core_dir / ".bago",            # package mode: .bago inside bago_core
    _user_active,                          # global install: ~/.bago/active/.bago
]'''

txt = txt.replace(old, new)
Path("bago_core/launcher.py").write_text(txt, encoding="utf-8")
print("PATCHED launcher.py")
