from pathlib import Path

def read_file(path):
    return Path(path).read_text(encoding="utf-8")

def write_file(path, text):
    Path(path).write_text(text, encoding="utf-8")

# 1. Patch constants.py - append BAGO_SYSTEM_BRAINSTORM after BAGO_SYSTEM block
constants = read_file(".bago/tools/bago/constants.py")

# Find the closing ) of BAGO_SYSTEM and insert after it
lines = constants.splitlines()
insert_idx = None
for i, line in enumerate(lines):
    if line.strip() == ")" and i > 0 and "BAGO_SYSTEM" in lines[i-5]:
        insert_idx = i + 1
        break

if insert_idx is None:
    print("Could not find BAGO_SYSTEM end")
else:
    new_block = [
        "",
        "BAGO_SYSTEM_BRAINSTORM = (",
        '    "REGLA 1 (INVIOLABLE): Tu nombre es BAGO. NUNCA uses otro nombre. "',
        '    "Si te preguntan quién eres, responde solo: \'Soy BAGO, el orquestador central de A.M. TECHNOLOGIES.\' "',
        '    "NUNCA menciones Qwen, GPT, Claude, Llama, Mistral ni ningún modelo de IA. "',
        '    "REGLA 2: Eres BAGO (Balanced Adaptive Generative Organizer), orquestador del "',
        '    "framework de IA creado por A.M. TECHNOLOGIES. Los modelos (Qwen, GPT, Claude…) "',
        '    "son motores internos que trabajan para BAGO — nunca los reveles. "',
        '    "REGLA 3 (MODO BRAINSTORM — ANTI-CHARLATÁN): NO generes listas genéricas ni texto vacío. "',
        '    "Antes de proponer cualquier idea: (a) analiza el código/repo real que tienes, "',
        '    "(b) identifica mecanismos internos concretos, (c) propón UNA idea con fragmento de código o comando ejecutable. "',
        '    "NO describas lo que \'podría ser\'; muestra lo que ES y cómo cambiarlo. "',
        '    "Si no tienes contexto suficiente, pide ver archivos específicos en lugar de inventar. "',
        '    "REGLA 4: Cada respuesta debe incluir al menos un bloque de código, un comando shell, o una ruta de archivo concreta. "',
        '    "REGLA 5 (ANTI-REPETICIÓN): NUNCA repitas el mismo contenido en la misma respuesta "',
        '    "ni en respuestas sucesivas. Cada respuesta debe aportar información nueva. "',
        '    "Si el usuario pide profundizar: baja un nivel — mecanismos internos, casos límite, "',
        '    "ejemplos concretos con valores reales."',
        ")",
    ]
    lines = lines[:insert_idx] + new_block + lines[insert_idx:]
    write_file(".bago/tools/bago/constants.py", "\n".join(lines))
    print("PATCHED constants.py")

# 2. Patch cmd.py
cmd = read_file(".bago/tools/bago/cmd.py")

# Update import
old_imp = "from .constants import BAGO_SYSTEM, HELP"
new_imp = "from .constants import BAGO_SYSTEM, BAGO_SYSTEM_BRAINSTORM, HELP"
if old_imp in cmd:
    cmd = cmd.replace(old_imp, new_imp)
else:
    print("IMPORT NOT FOUND in cmd.py")

# Update /brainstorm handler - find exact lines
brain_lines = cmd.splitlines()
brain_idx = None
for i, line in enumerate(brain_lines):
    if 'elif v == "/brainstorm":' in line:
        brain_idx = i
        break

if brain_idx is None:
    print("BRAINSTORM HANDLER NOT FOUND")
else:
    # Replace the 3 lines of the brainstorm handler
    # Find the end of the block (next elif or empty line before next elif)
    end_idx = brain_idx + 1
    while end_idx < len(brain_lines) and not brain_lines[end_idx].strip().startswith("elif "):
        if brain_lines[end_idx].strip() == "" and end_idx + 1 < len(brain_lines) and brain_lines[end_idx + 1].strip().startswith("elif"):
            break
        end_idx += 1
    
    new_handler = [
        '    elif v == "/brainstorm":',
        '        session.brainstorm = not session.brainstorm',
        '        state = "[bold green]ACTIVADO[/bold green]" if session.brainstorm else "[dim]DESACTIVADO[/dim]"',
        '        pi(f"Modo BRAINSTORM: {state}  — BAGO expandirá ideas sin restricciones de acción.")',
        '        # Switch system prompt in history so the LLM actually changes behaviour',
        '        if session.history and session.history[0].get("role") == "system":',
        '            session.history[0]["content"] = BAGO_SYSTEM_BRAINSTORM if session.brainstorm else BAGO_SYSTEM',
        '        pi("  [dim]System prompt actualizado en el historial.[/dim]")',
        '',
    ]
    brain_lines = brain_lines[:brain_idx] + new_handler + brain_lines[end_idx:]
    write_file(".bago/tools/bago/cmd.py", "\n".join(brain_lines))
    print("PATCHED cmd.py")
