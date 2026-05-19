"""bago.tumba — Modo Tumba: almacenamiento ciego de secretos/datos sensibles.

El LLM NUNCA ve el contenido. Solo el encabezado (nombre de la clave).
Los valores se insertan en mensajes normales via {{clave}}.

Formato de entrada en modo tumba:
    Nombre clave: valor secreto aquí

Uso en mensajes normales (sustitución automática):
    Configura el bot con la {{Api Telegram}}
    La contraseña es {{Password DB}}, conéctate.
"""

import json
import re
from pathlib import Path

from .constants import USER_BAGO

_TUMBA_FILE = USER_BAGO / "state" / "tumba.json"

# ── Patrón de sustitución: {{nombre}} ─────────────────────────────────────────
_SUBST_RE = re.compile(r"\{\{([^}]+)\}\}")

# ── Patrón de entrada en modo tumba: "Nombre: valor" ─────────────────────────
# El separador es la primera ":" en la línea
_ENTRY_RE = re.compile(r"^([^:]+?)\s*:\s*([\s\S]+)$", re.DOTALL)


# ── I/O del archivo ───────────────────────────────────────────────────────────

def _load() -> dict:
    """Carga el archivo tumba. Devuelve dict vacío si no existe."""
    try:
        return json.loads(_TUMBA_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(data: dict) -> None:
    """Guarda el archivo tumba."""
    _TUMBA_FILE.parent.mkdir(parents=True, exist_ok=True)
    _TUMBA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── API pública ───────────────────────────────────────────────────────────────

def tumba_add(raw_line: str) -> "tuple[bool, str, str]":
    """Procesa una línea en modo tumba.

    Formato esperado: "Nombre clave: valor"
    Retorna (ok, name, message_para_usuario).
    El valor NUNCA se incluye en message_para_usuario.
    """
    m = _ENTRY_RE.match(raw_line.strip())
    if not m:
        return False, "", (
            "[red]Formato inválido.[/red] Usa: [bold]Nombre clave: valor[/bold]\n"
            "  Ejemplo:  Api Telegram: 1234567:ABCxyz...\n"
            "  Para salir del modo tumba: [bold]/tumba[/bold]"
        )
    name  = m.group(1).strip()
    value = m.group(2).strip()
    if not name or not value:
        return False, "", "[red]Nombre o valor vacío.[/red]"

    data = _load()
    overwrite = name in data
    data[name] = value
    _save(data)

    verb = "[yellow]actualizado[/yellow]" if overwrite else "[green]guardado[/green]"
    return True, name, (
        f"  🪦 Tumba: [[bold]{name}[/bold]] {verb}  "
        f"[dim](usa {{[bold]{{{name}}}}}}} en tus mensajes para insertar el valor)[/dim]"
    )


def tumba_delete(name: str) -> str:
    """Elimina una entrada por nombre. Devuelve mensaje."""
    data = _load()
    if name not in data:
        keys = list(data.keys())
        nearby = [k for k in keys if name.lower() in k.lower()]
        hint = f"  ¿Quisiste decir: {', '.join(nearby)}?" if nearby else ""
        return f"[red]No existe '[bold]{name}[/bold]' en la tumba.[/red]{hint}"
    del data[name]
    _save(data)
    return f"  🪦 Tumba: [[bold]{name}[/bold]] [red]eliminado[/red]"


def tumba_list() -> "list[str]":
    """Devuelve lista de nombres (sin valores) guardados en la tumba."""
    return list(_load().keys())


def tumba_clear() -> int:
    """Elimina todas las entradas. Devuelve cuántas había."""
    data = _load()
    count = len(data)
    _save({})
    return count


def tumba_substitute(text: str) -> "tuple[str, list[str]]":
    """Sustituye {{nombre}} por el valor guardado en la tumba.

    Devuelve (texto_sustituido, lista_de_nombres_sustituidos).
    Las claves no encontradas se dejan tal cual.
    """
    data = _load()
    replaced: list[str] = []

    def _replace(m):
        key = m.group(1).strip()
        if key in data:
            replaced.append(key)
            return data[key]
        return m.group(0)  # dejar {{clave}} si no existe

    result = _SUBST_RE.sub(_replace, text)
    return result, replaced


def tumba_has_placeholder(text: str) -> bool:
    """True si el texto contiene al menos un {{placeholder}}."""
    return bool(_SUBST_RE.search(text))
