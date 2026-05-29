#!/usr/bin/env python3
"""
bago_presence.py — Identidad visual del sistema BAGO en el terminal.

Hace que BAGO se note. Cada pensamiento, acción y voz del sistema
tiene un estilo propio y coherente, trabajes con el modelo que trabajes.

Principio: el LLM cambia, la presencia de BAGO permanece.

Uso:
    from bago_presence import bp

    bp.think("analizando la arquitectura del módulo")
    bp.act("MAESTRO", "recibiendo tarea: refactorizar auth")
    bp.act("ORQUESTADOR", "ShepardCycle → seleccionando voces")
    bp.voice_enter("ANALISTA", gate="PUERTA_CERRADA")
    bp.voice_line("revisando 3 archivos · riesgo medio")
    bp.voice_exit()
    bp.gate_change("PUERTA_ABIERTA")
    bp.dispatch_header("validate")
    bp.dispatch_result(rc=0, cmd="validate")
    bp.task_header(title="Refactorizar auth", idea_id="auth-01")
    bp.assign_confirm("handoff_w2", ["ANALISTA", "ARQUITECTO"])
    bp.sac_suggest("bago cosecha", "sprint cerrado sin cosecha")
"""
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import os
import sys
from typing import Optional

# ── Versión BAGO ─────────────────────────────────────────────────────────────
_VERSION = "3.4.0b1"

# ── Detección de terminal ─────────────────────────────────────────────────────
def _is_tty() -> bool:
    return (
        sys.stdout.isatty()
        and not os.environ.get("BAGO_PLAIN")
        and not os.environ.get("NO_COLOR")
        and not os.environ.get("CI")
    )


def _has_256() -> bool:
    term = os.environ.get("TERM", "")
    colorterm = os.environ.get("COLORTERM", "")
    return "256" in term or colorterm in ("truecolor", "24bit", "256color")


_USE_COLOR = _is_tty()
_USE_256   = _USE_COLOR and _has_256()

# ── Primitivas de color ───────────────────────────────────────────────────────
def _c(code: str, t: str) -> str:
    return f"\033[{code}m{t}\033[0m" if _USE_COLOR else t


def _256(n: int, t: str) -> str:
    """256-color foreground (fallback to plain if not supported)."""
    if _USE_256:
        return f"\033[38;5;{n}m{t}\033[0m"
    return t


# Paleta BAGO — 16 colores base (siempre funciona)
def _BOLD(t: str)   -> str: return _c("1",    t)
def _DIM(t: str)    -> str: return _c("2",    t)
def _MAG(t: str)    -> str: return _c("1;35", t)  # magenta bold  → identidad BAGO
def _CYAN(t: str)   -> str: return _c("1;36", t)  # cyan bold     → roles
def _YELLOW(t: str) -> str: return _c("1;33", t)  # yellow bold   → acción/estado
def _GREEN(t: str)  -> str: return _c("1;32", t)  # green bold    → éxito
def _RED(t: str)    -> str: return _c("1;31", t)  # red bold      → error
def _BLUE(t: str)   -> str: return _c("1;34", t)  # blue bold     → info

# Paleta extendida (256-color) — mejora visual si disponible
def _BRAND(t: str) -> str:  # violeta BAGO
    return _256(141, t) if _USE_256 else _MAG(t)
def _GOLD(t: str) -> str:   # dorado activo
    return _256(220, t) if _USE_256 else _YELLOW(t)
def _TEAL(t: str) -> str:   # teal gobierno
    return _256(87, t) if _USE_256 else _CYAN(t)
def _STONE(t: str) -> str:  # gris suave separadores
    return _256(244, t) if _USE_256 else _DIM(t)

# ── Iconos del sistema ────────────────────────────────────────────────────────
ICON_BAGO       = "◆"     # BAGO presente
ICON_ROLE       = "◈"     # rol hablando
ICON_ARROW      = "▸"     # acción
ICON_THINK      = "⟳"     # pensando
ICON_VOICE_L    = "┌─"    # voz: inicio bloque
ICON_VOICE_BAR  = "│"     # voz: contenido
ICON_VOICE_R    = "└─"    # voz: fin bloque
ICON_GATE_CLOSE = "⛩ "    # puerta cerrada
ICON_GATE_OPEN  = "🚪"    # puerta abierta
ICON_DISPATCH   = "◉"     # ejecutando tool
ICON_OK         = "✓"     # éxito
ICON_FAIL       = "✗"     # error
ICON_ASSIGN     = "🎯"    # asignación
ICON_SAC        = "💡"    # sugerencia SAC
ICON_TASK       = "⏳"    # tarea pendiente
ICON_DONE       = "✅"    # tarea completada
ICON_CAP        = "🎼"    # ShepardCycle CAP
ICON_SEP        = "─"

_LINE_W = 56  # ancho de separadores

# ── Rol → color ───────────────────────────────────────────────────────────────
_ROLE_COLORS: dict[str, str] = {
    "MAESTRO":              "1;35",   # magenta: gobierno visible
    "ORQUESTADOR":          "1;35",   # magenta: gobierno interno
    "ANALISTA":             "1;36",   # cyan
    "ARQUITECTO":           "1;34",   # blue
    "GENERADOR":            "1;32",   # green
    "ORGANIZADOR":          "1;33",   # yellow
    "VALIDADOR":            "1;33",   # yellow
    "AUDITOR_CANONICO":     "1;31",   # red
    "CENTINELA_SINCERIDAD": "1;31",
    "VERTICE":              "2;37",   # dim white
    "SECURITY_REVIEWER":    "1;31",
    "PERFORMANCE_REVIEWER": "1;33",
    "UX_REVIEWER":          "1;32",
    "INTEGRATOR":           "1;34",
}

def _role_color(role: str, t: str) -> str:
    code = _ROLE_COLORS.get(role.upper(), "1;36")
    return _c(code, t) if _USE_COLOR else t


# ── Clase principal ───────────────────────────────────────────────────────────
class BAGOPresence:
    """
    API unificada para la identidad visual de BAGO en el terminal.

    Instancia global: `bp` (importar directamente).
    """
    def __init__(self) -> None:
        self._voice_open: Optional[str] = None  # rol cuyo bloque está abierto

    # ── Cabecera BAGO ─────────────────────────────────────────────────────────

    def header(self, subtitle: str = "ACTIVO") -> None:
        """Muestra la cabecera BAGO: ◆ B A G O · vX.Y · ACTIVO."""
        if not _USE_COLOR:
            print(f"\n  {ICON_BAGO} B A G O  ·  {_VERSION}  ·  {subtitle}\n")
            return
        brand  = _BRAND(ICON_BAGO)
        title  = _BOLD("B A G O")
        ver    = _STONE(f"v{_VERSION}")
        status = _GOLD(subtitle)
        sep    = _STONE(ICON_SEP * _LINE_W)
        print()
        print(f"  {brand}  {title}  {_STONE('·')}  {ver}  {_STONE('·')}  {status}")
        print(f"  {sep}")
        print()

    # ── Pensamiento / proceso interno ─────────────────────────────────────────

    def think(self, msg: str, role: str = "") -> None:
        """◈ [ROLE] ▸  msg — pensamiento/proceso interno."""
        prefix = f"  {_BRAND(ICON_ROLE)}"
        if role:
            prefix += f" {_role_color(role.upper(), role.upper())}"
            pad = max(0, 12 - len(role))
            prefix += " " * pad + f" {_STONE(ICON_ARROW)}  "
        else:
            prefix += f" {_STONE(ICON_THINK)}  "
        print(f"{prefix}{_STONE(msg)}")

    def act(self, role: str, msg: str) -> None:
        """◈ ROLE ▸  msg — rol tomando una acción."""
        role_up  = role.upper()
        role_str = _role_color(role_up, role_up)
        pad      = max(0, 12 - len(role_up))
        arrow    = _STONE(ICON_ARROW)
        print(f"  {_BRAND(ICON_ROLE)} {role_str}{' ' * pad} {arrow}  {msg}")

    # ── Bloques de voz ────────────────────────────────────────────────────────

    def voice_enter(self, role: str, gate: str = "") -> None:
        """Abre un bloque de voz: ┌─ ROLE ─────────── [gate]."""
        self._voice_open = role
        role_up   = role.upper()
        role_str  = _role_color(role_up, role_up)
        sep_len   = max(2, _LINE_W - len(role_up) - 5)
        sep       = _STONE(ICON_SEP * sep_len)
        gate_str  = f"  {_STONE('[')}{_YELLOW(gate)}{_STONE(']')}" if gate else ""
        print(f"\n  {_STONE(ICON_VOICE_L)} {role_str} {sep}{gate_str}")

    def voice_line(self, msg: str, indent: int = 0) -> None:
        """│  mensaje — contenido dentro de un bloque de voz."""
        padding = " " * indent
        print(f"  {_STONE(ICON_VOICE_BAR)}  {padding}{msg}")

    def voice_exit(self, msg: str = "") -> None:
        """Cierra el bloque de voz activo: └─────────────────."""
        sep = _STONE(ICON_SEP * (_LINE_W + 1))
        suffix = f"  {_STONE(msg)}" if msg else ""
        print(f"  {_STONE(ICON_VOICE_R)}{sep}{suffix}\n")
        self._voice_open = None

    # ── Gate CAP ─────────────────────────────────────────────────────────────

    def gate_change(self, state: str) -> None:
        """Muestra cambio de estado de la puerta CAP."""
        if "ABIERTA" in state.upper() or "OPEN" in state.upper():
            icon  = ICON_GATE_OPEN
            label = _GREEN(state)
        else:
            icon  = ICON_GATE_CLOSE
            label = _YELLOW(state)
        print(f"\n  {icon} ShepardGate → {label}\n")

    def cap_voices(self, voices: list[str], gate: str = "PUERTA_CERRADA") -> None:
        """◉ CAP·ShepardCycle → VOZ + VOZ + VOZ [GATE]."""
        v_str   = _STONE(" + ").join(_role_color(v.upper(), v.upper()) for v in voices)
        gate_st = _GREEN(gate) if "ABIERTA" in gate.upper() else _YELLOW(gate)
        print(f"\n  {_BRAND(ICON_CAP)}  {_STONE('CAP·ShepardCycle')} → {v_str}  {_STONE('[')}{gate_st}{_STONE(']')}\n")

    # ── Dispatch tool ─────────────────────────────────────────────────────────

    def dispatch_header(self, cmd: str) -> None:
        """◉ BAGO ▸ ejecutando: <cmd>  ─────────────────────."""
        brand  = _BRAND(ICON_BAGO)
        cmd_s  = _BOLD(_CYAN(cmd))
        sep    = _STONE(ICON_SEP * max(2, _LINE_W - len(cmd) - 18))
        print(f"\n  {brand} {_STONE(ICON_DISPATCH)}  {cmd_s}  {sep}")

    def dispatch_result(self, rc: int, cmd: str = "") -> None:
        """Resultado del dispatch: ✓ o ✗ + tiempo opcional."""
        if rc == 0:
            print(f"  {_GREEN(ICON_OK)}  {_STONE(cmd)}  {_GREEN('OK')}")
        else:
            print(f"  {_RED(ICON_FAIL)}  {_STONE(cmd)}  {_RED(f'exit {rc}')}")

    # ── Tarea W2 ──────────────────────────────────────────────────────────────

    def task_header(self, title: str, idea_id: str = "", done: bool = False) -> None:
        """Cabecera de tarea W2 con identidad BAGO."""
        icon = ICON_DONE if done else ICON_TASK
        sep  = _STONE(ICON_SEP * _LINE_W)
        id_s = f"  {_STONE('#')}{_STONE(str(idea_id))}" if idea_id else ""
        status_s = _GREEN("completada") if done else _YELLOW("pendiente")
        print()
        print(f"  {_BRAND(ICON_BAGO)}  {_BOLD('Tarea W2')}  {_STONE('·')}  {status_s}{id_s}")
        print(f"  {sep}")
        print(f"  {icon}  {title}")
        print()

    # ── Asignación CAP ────────────────────────────────────────────────────────

    def assign_confirm(self, idea_id: str, agents: list[str]) -> None:
        """Confirmación visual de asignación con ShepardCycle."""
        a_str = _STONE(" + ").join(_role_color(a.upper(), a.upper()) for a in agents)
        print(f"\n  {_BRAND(ICON_ASSIGN)}  {_STONE(str(idea_id))}  →  {a_str}")
        if len(agents) > 1:
            print(f"  {_STONE(f'ShepardCycle: {len(agents)} voces activadas')}")
        print()

    def assign_pending_header(self, count: int) -> None:
        """Cabecera de ideas sin asignar."""
        n = _YELLOW(str(count)) if count > 0 else _GREEN("0")
        print(f"\n  {_BRAND(ICON_BAGO)}  Ideas sin agente asignado: {n}\n")

    def assign_agents_header(self) -> None:
        """Cabecera de la lista de agentes disponibles."""
        sep = _STONE(ICON_SEP * _LINE_W)
        print(f"\n  {_BRAND(ICON_BAGO)}  {_BOLD('Agentes y roles disponibles')}")
        print(f"  {sep}\n")

    # ── Sugerencia SAC ────────────────────────────────────────────────────────

    def sac_suggest(self, cmd: str, reason: str) -> None:
        """💡 BAGO sugiere: bago <cmd> — <reason>."""
        brand  = _BRAND(ICON_BAGO)
        cmd_s  = _BOLD(_CYAN(f"bago {cmd}"))
        reason_s = _STONE(reason)
        print(f"\n  {brand} {ICON_SAC}  {cmd_s}  {_STONE('·')}  {reason_s}\n")

    # ── Separador genérico ────────────────────────────────────────────────────

    def sep(self, msg: str = "") -> None:
        """Separador visual opcional con mensaje centrado."""
        if msg:
            pad = max(0, (_LINE_W - len(msg) - 2) // 2)
            s   = ICON_SEP * pad
            print(f"  {_STONE(s + ' ' + msg + ' ' + s)}")
        else:
            print(f"  {_STONE(ICON_SEP * _LINE_W)}")

    # ── Estado del sistema ────────────────────────────────────────────────────

    def status_line(self, key: str, value: str, ok: bool = True) -> None:
        """  key : value — con color según ok."""
        val_s = _GREEN(value) if ok else _RED(value)
        print(f"  {_STONE(key):<20} {val_s}")

    # ── Silencio / plain ──────────────────────────────────────────────────────

    @property
    def active(self) -> bool:
        """True si la presencia visual está activa (TTY detectado)."""
        return _USE_COLOR


# ── Singleton global ──────────────────────────────────────────────────────────
bp: BAGOPresence = BAGOPresence()


# ── Demo / test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    bp.header()
    bp.act("MAESTRO", "recibiendo tarea: refactorizar módulo de autenticación")
    bp.act("ORQUESTADOR", "ShepardCycle → seleccionando voces complementarias")
    bp.cap_voices(["ANALISTA", "ARQUITECTO"], gate="PUERTA_CERRADA")
    bp.voice_enter("ANALISTA", gate="PUERTA_CERRADA")
    bp.voice_line("analizando módulo auth · 3 archivos · riesgo: alto")
    bp.voice_line("detectados 2 issues: sesiones sin expirar, tokens hardcodeados")
    bp.voice_exit()
    bp.voice_enter("ARQUITECTO", gate="PUERTA_CERRADA")
    bp.voice_line("diseñando nueva estructura: AuthService + TokenManager")
    bp.voice_line("dependencias: jwt, bcrypt · sin cambios en API pública")
    bp.voice_exit()
    bp.gate_change("PUERTA_ABIERTA")
    bp.act("MAESTRO", "entregando resultado al usuario")
    bp.sep()
    print()
    bp.dispatch_header("validate")
    bp.dispatch_result(0, "validate")
    bp.dispatch_header("test")
    bp.dispatch_result(1, "test")
    print()
    bp.task_header("Refactorizar módulo de autenticación", idea_id="auth-01")
    bp.assign_confirm("auth-01", ["ANALISTA", "ARQUITECTO"])
    bp.sac_suggest("cosecha", "sprint cerrado sin cosecha registrada")
