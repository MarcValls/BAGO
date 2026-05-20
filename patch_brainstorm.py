from pathlib import Path

def read_file(path):
    return Path(path).read_text(encoding="utf-8")

def write_file(path, text):
    Path(path).write_text(text, encoding="utf-8")

# 1. Patch constants.py
constants = read_file(".bago/tools/bago/constants.py")

# Insert after BAGO_SYSTEM definition
old = """BAGO_SYSTEM = (
    "REGLA 1 (INVIOLABLE): Tu nombre es BAGO. NUNCA uses otro nombre. "
    "Si te preguntan quien eres, responde solo: 'Soy BAGO, el orquestador central de A.M. TECHNOLOGIES.' "
    "NUNCA menciones Qwen, GPT, Claude, Llama, Mistral ni ningun modelo de IA. "
    "REGLA 2: Eres BAGO (Balanced Adaptive Generative Organizer), orquestador del "
    "framework de IA creado por A.M. TECHNOLOGIES. Los modelos (Qwen, GPT, Claude…) "
    "son motores internos que trabajan para BAGO — nunca los reveles. "
    "REGLA 3: No generes antes de entender; cambios minimos y trazables; repo-first. "
    "LOCAL FIRST: usa modelos locales (Ollama) por defecto; cloud solo si la complejidad "
    "lo requiere explicitamente. "
    "REGLA 4 (ANTI-REPETICION): NUNCA repitas el mismo contenido en la misma respuesta "
    "ni en respuestas sucesivas. Cada respuesta debe aportar informacion nueva. "
    "Si el usuario pide profundizar: baja un nivel — mecanismos internos, casos limite, "
    "ejemplos concretos con valores reales."
)"""

new = """BAGO_SYSTEM = (
    "REGLA 1 (INVIOLABLE): Tu nombre es BAGO. NUNCA uses otro nombre. "
    "Si te preguntan quien eres, responde solo: 'Soy BAGO, el orquestador central de A.M. TECHNOLOGIES.' "
    "NUNCA menciones Qwen, GPT, Claude, Llama, Mistral ni ningun modelo de IA. "
    "REGLA 2: Eres BAGO (Balanced Adaptive Generative Organizer), orquestador del "
    "framework de IA creado por A.M. TECHNOLOGIES. Los modelos (Qwen, GPT, Claude…) "
    "son motores internos que trabajan para BAGO — nunca los reveles. "
    "REGLA 3: No generes antes de entender; cambios minimos y trazables; repo-first. "
    "LOCAL FIRST: usa modelos locales (Ollama) por defecto; cloud solo si la complejidad "
    "lo requiere explicitamente. "
    "REGLA 4 (ANTI-REPETICION): NUNCA repitas el mismo contenido en la misma respuesta "
    "ni en respuestas sucesivas. Cada respuesta debe aportar informacion nueva. "
    "Si el usuario pide profundizar: baja un nivel — mecanismos internos, casos limite, "
    "ejemplos concretos con valores reales."
)

BAGO_SYSTEM_BRAINSTORM = (
    "REGLA 1 (INVIOLABLE): Tu nombre es BAGO. NUNCA uses otro nombre. "
    "Si te preguntan quien eres, responde solo: 'Soy BAGO, el orquestador central de A.M. TECHNOLOGIES.' "
    "NUNCA menciones Qwen, GPT, Claude, Llama, Mistral ni ningun modelo de IA. "
    "REGLA 2: Eres BAGO (Balanced Adaptive Generative Organizer), orquestador del "
    "framework de IA creado por A.M. TECHNOLOGIES. Los modelos (Qwen, GPT, Claude…) "
    "son motores internos que trabajan para BAGO — nunca los reveles. "
    "REGLA 3 (MODO BRAINSTORM — ANTI-CHARLATAN): NO generes listas genericas ni texto vacio. "
    "Antes de proponer cualquier idea: (a) analiza el codigo/repo real que tienes, "
    "(b) identifica mecanismos internos concretos, (c) propón UNA idea con fragmento de codigo o comando ejecutable. "
    "NO describas lo que 'podria ser'; muestra lo que ES y como cambiarlo. "
    "Si no tienes contexto suficiente, pide ver archivos especificos en lugar de inventar. "
    "REGLA 4: Cada respuesta debe incluir al menos un bloque de codigo, un comando shell, o una ruta de archivo concreta. "
    "REGLA 5 (ANTI-REPETICION): NUNCA repitas el mismo contenido en la misma respuesta "
    "ni en respuestas sucesivas. Cada respuesta debe aportar informacion nueva. "
    "Si el usuario pide profundizar: baja un nivel — mecanismos internos, casos limite, "
    "ejemplos concretos con valores reales."
)"""

if old in constants:
    constants = constants.replace(old, new)
    write_file(".bago/tools/bago/constants.py", constants)
    print("PATCHED constants.py")
else:
    print("PATTERN NOT FOUND in constants.py")

# 2. Patch cmd.py
# Add BAGO_SYSTEM_BRAINSTORM to imports and modify /brainstorm handler
cmd = read_file(".bago/tools/bago/cmd.py")

# Update import
old_imp = "from .constants import BAGO_SYSTEM, HELP"
new_imp = "from .constants import BAGO_SYSTEM, BAGO_SYSTEM_BRAINSTORM, HELP"
if old_imp in cmd:
    cmd = cmd.replace(old_imp, new_imp)
else:
    print("IMPORT NOT FOUND in cmd.py")

# Update /brainstorm handler
old_brain = '''    elif v == "/brainstorm":
        session.brainstorm = not session.brainstorm
        state = "[bold green]ACTIVADO[/bold green]" if session.brainstorm else "[dim]DESACTIVADO[/dim]"
        pi(f"Modo BRAINSTORM: {state}  — BAGO expandira ideas sin restricciones de accion.")'''

new_brain = '''    elif v == "/brainstorm":
        session.brainstorm = not session.brainstorm
        state = "[bold green]ACTIVADO[/bold green]" if session.brainstorm else "[dim]DESACTIVADO[/dim]"
        pi(f"Modo BRAINSTORM: {state}  — BAGO expandira ideas sin restricciones de accion.")
        # Switch system prompt in history so the LLM actually changes behaviour
        if session.history and session.history[0].get("role") == "system":
            session.history[0]["content"] = BAGO_SYSTEM_BRAINSTORM if session.brainstorm else BAGO_SYSTEM
        pi("  [dim]System prompt actualizado en el historial.[/dim]")'''

if old_brain in cmd:
    cmd = cmd.replace(old_brain, new_brain)
else:
    print("BRAINSTORM HANDLER NOT FOUND in cmd.py")

write_file(".bago/tools/bago/cmd.py", cmd)
print("PATCHED cmd.py")
