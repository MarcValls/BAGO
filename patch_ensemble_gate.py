from pathlib import Path

txt = Path(".bago/tools/bago/llm/strategies.py").read_text(encoding="utf-8")
lines = txt.splitlines()

# Find line with '"""' after run_ensemble (line 83)
insert_idx = None
for i, line in enumerate(lines):
    if i > 75 and line.strip() == '"""':
        insert_idx = i + 1
        break

if insert_idx is None:
    print("insertion point not found")
    exit(1)

gate_code = [
    "",
    "    # ── Pre-flight gate: abort if all models in ensemble are unavailable ───────",
    "    unavailable = []",
    "    for t in model_list:",
    '        n, _, _ = session._find_model(t)',
    '        if not n:',
    '            unavailable.append(t)',
    "    if len(unavailable) == len(model_list):",
    '        pe(f"[bold red]ENSEMBLE ABORTADO[/bold red]: ningun modelo disponible.")',
    '        pe("  Solicitados: " + ", ".join(model_list))',
    '        pe("  Usa /models para ver disponibles o /switch para cambiar.")',
    "        return",
    "",
]

lines = lines[:insert_idx] + gate_code + lines[insert_idx:]
Path(".bago/tools/bago/llm/strategies.py").write_text("\n".join(lines), encoding="utf-8")
print("PATCHED ensemble gate")
