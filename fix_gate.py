from pathlib import Path

txt = Path(".bago/tools/bago/llm/strategies.py").read_text(encoding="utf-8")
lines = txt.splitlines()

# Remove the gate that was inserted inside the docstring
# Find lines 15-26 (the gate) and remove them
new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    if line.strip().startswith("# ── Pre-flight gate:"):
        # skip the gate block until the next line that is not part of the gate
        while i < len(lines) and not lines[i].strip().startswith("Args:"):
            i += 1
        new_lines.append(lines[i])  # keep Args:
        i += 1
        continue
    new_lines.append(line)
    i += 1

# Now find the closing """ of run_chain docstring and insert after it
insert_idx = None
for i, line in enumerate(new_lines):
    if i > 10 and line.strip() == '"""' and new_lines[i-1].strip().startswith('Si None'):
        insert_idx = i + 1
        break

if insert_idx is None:
    # fallback: find first """ after run_chain
    for i, line in enumerate(new_lines):
        if i > 10 and line.strip() == '"""':
            insert_idx = i + 1
            break

if insert_idx is None:
    print("Could not find insertion point")
    exit(1)

gate_code = [
    "",
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

new_lines = new_lines[:insert_idx] + gate_code + new_lines[insert_idx:]
Path(".bago/tools/bago/llm/strategies.py").write_text("\n".join(new_lines), encoding="utf-8")
print("FIXED strategies.py")
