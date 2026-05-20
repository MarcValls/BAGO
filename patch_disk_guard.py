from pathlib import Path

txt = Path(".bago/tools/build_pack.py").read_text(encoding="utf-8")
lines = txt.splitlines()

# Constants to add after existing constants
const_idx = None
for i, line in enumerate(lines):
    if line.startswith("EXCLUDE_SUFFIXES:"):
        # find end of this block
        for j in range(i, len(lines)):
            if lines[j].strip() == "]":
                const_idx = j + 1
                break
        break

if const_idx is None:
    print("const_idx not found")
    exit(1)

new_consts = [
    "",
    "# ── Safety guards (PR-06: anti recursive-zip / disk-fill) ────────────────────",
    "MAX_ZIP_SIZE_MB = 100   # abort if output exceeds this (MB)",
    "WARN_EXISTING_MB = 50   # warn if existing files in out_dir exceed this (MB)",
    "",
    "def _scan_for_oversized(out_dir: Path) -> list[Path]:",
    '    """Return existing files in out_dir larger than WARN_EXISTING_MB."""',
    "    found = []",
    "    if not out_dir.exists():",
    "        return found",
    "    for f in out_dir.iterdir():",
    "        if f.is_file() and f.stat().st_size > WARN_EXISTING_MB * 1_048_576:",
    "            found.append(f)",
    "    return found",
    "",
]

lines = lines[:const_idx] + new_consts + lines[const_idx:]

# Find build() function — insert pre-flight checks at the top
build_idx = None
for i, line in enumerate(lines):
    if line.strip().startswith("def build("):
        build_idx = i
        break

if build_idx is None:
    print("build() not found")
    exit(1)

# Find the line after "zip_path  = out_dir / ..." and "sha_path  = out_dir / ..."
insert_after = None
for i in range(build_idx, len(lines)):
    if "sha_path  =" in lines[i]:
        insert_after = i + 1
        break

if insert_after is None:
    print("insert_after not found")
    exit(1)

preflight_block = [
    "",
    "    # ── Pre-flight: detect existing oversized files (recursive zip bomb) ──────",
    "    oversized = _scan_for_oversized(out_dir)",
    "    if oversized:",
    '        print(f"  [bold red]🚨 GUARDIA ACTIVADA[/bold red]", file=sys.stderr)',
    '        print(f"  Detectados {len(oversized)} archivo(s) gigantesco(s) en {out_dir}:", file=sys.stderr)',
    "        for f in oversized:",
    '            gb = f.stat().st_size / 1_073_741_824',
    '            print(f"    • {f.name}  ({gb:.1f} GB)", file=sys.stderr)',
    '        print("  Esto suele indicar un ZIP recursivo (el ZIP se incluye a si mismo).", file=sys.stderr)',
    '        print("  Borra el archivo corrupto manualmente y reconstruye.", file=sys.stderr)',
    "        sys.exit(1)",
    "",
    "    # ── Guard: ensure output ZIP path itself will not be included ───────────────",
    "    abs_root = BAGO_ROOT.resolve()",
    "    abs_out  = out_dir.resolve()",
    "    abs_zip  = zip_path.resolve()",
    "    if abs_zip.is_relative_to(abs_root):",
    "        # Must be excluded; verify dynamic_excludes will catch it",
    "        rel_zip = abs_zip.relative_to(abs_root)",
    "        if not _should_exclude(rel_zip.parent) and str(rel_zip.parent) not in [\"dist\", \".bago/dist\", \".bago\\\\dist\"]:",
    '            print(f"  [bold red]🚨 ABORTADO[/bold red]: output ZIP path {zip_path} lives inside source tree", file=sys.stderr)',
    '            print("     and its parent is NOT in EXCLUDE_PREFIXES.", file=sys.stderr)',
    "            sys.exit(1)",
    "",
]

lines = lines[:insert_after] + preflight_block + lines[insert_after:]

# Find the line "size_mb = zip_path.stat().st_size / 1_048_576" and add post-build guard
post_idx = None
for i, line in enumerate(lines):
    if "size_mb = zip_path.stat().st_size" in line:
        post_idx = i + 1  # insert after this line
        break

if post_idx is None:
    print("post_idx not found")
    exit(1)

post_guard = [
    "",
    "    # ── Post-build guard: verify ZIP is not absurdly large ────────────────────",
    "    if size_mb > MAX_ZIP_SIZE_MB:",
    '        print(f"  [bold red]🚨 ZIP DEMASIADO GRANDE[/bold red]: {size_mb:.1f} MB > {MAX_ZIP_SIZE_MB} MB", file=sys.stderr)',
    '        print("  Posible causa: inclusion recursiva (ZIP dentro de ZIP).", file=sys.stderr)',
    '        print(f"  Eliminando ZIP corrupto: {zip_path}", file=sys.stderr)',
    "        zip_path.unlink(missing_ok=True)",
    "        sha_path.unlink(missing_ok=True)",
    "        sys.exit(1)",
    "",
]

lines = lines[:post_idx] + post_guard + lines[post_idx:]

Path(".bago/tools/build_pack.py").write_text("\n".join(lines), encoding="utf-8")
print("PATCHED build_pack.py with disk-fill guards")
