from pathlib import Path

txt = Path(".bago/tools/bago/llm/strategies.py").read_text(encoding="utf-8")
lines = txt.splitlines()

# Find the line "def run_chain(session, model_sequence, prompt, silent_route=True, ..."
# and insert a pre-flight gate right after the docstring / before the first code line

def_idx = None
for i, line in enumerate(lines):
    if line.strip().startswith("def run_chain"):
        def_idx = i
        break

if def_idx is None:
    print("run_chain not found")
    exit(1)

# Find where the actual body starts (after docstring)
insert_idx = None
for i in range(def_idx + 1, len(lines)):
    if lines[i].strip().startswith('"""') and i > def_idx:
        # end of docstring
        for j in range(i + 1, len(lines)):
            if lines[j].strip():  # first non-empty line after docstring
                insert_idx = j
                break
        break

if insert_idx is None:
    # fallback: find first non-empty line after def
    for i in range(def_idx + 1, len(lines)):
        if lines[i].strip() and not lines[i].strip().startswith('"""'):
            insert_idx = i
            break

if insert_idx is None:
    print("Could not find insertion point")
    exit(1)

gate_code = [
    "    # ── Pre-flight gate: abort if any model in the chain is unavailable ────────",
    "    unavailable = []",
    "    for t in model_sequence:",
    '        n, _, _ = session._find_model(t)',
    '        if not n:',
    '            unavailable.append(t)',
    "    if unavailable:",
    '        pe(f"[bold red]CHAIN ABORTADO[/bold red]: {len(unavailable)} modelo(s) no disponible(s).")',
    '        pe("  Cadena solicitada: " + " -> ".join(model_sequence))',
    '        pe("  Faltan: " + ", ".join(unavailable))',
    '        pe("  Usa /models para ver disponibles o /switch para cambiar.")',
    "        return  # abort; nothing is mutated (history stays intact)",
    "",
]

lines = lines[:insert_idx] + gate_code + lines[insert_idx:]
Path(".bago/tools/bago/llm/strategies.py").write_text("\n".join(lines), encoding="utf-8")
print("PATCHED strategies.py")
