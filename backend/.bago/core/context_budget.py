"""context_budget.py — ContextBudget tracker y BudgetReport.

Calcula cuántos tokens ocupa el contexto antes de enviarlo al LLM,
compara con el límite del modelo, y produce un reporte con nivel de alerta.

Niveles de alerta:
    - GREEN:  < 70% del budget
    - YELLOW: 70-85%
    - ORANGE: 85-95%
    - RED:    > 95% (truncamiento inminente)

Estimación heurística: ~4 chars/token para texto inglés/código,
~2.5 chars/token para español (más tokens por caracteres acentuados).
Usamos un promedio conservador de 3.5 chars/token.

Truncamiento por capas:
    1. System prompt base + agent + goal (siempre se conserva)
    2. RAG fragments (primeros en cortarse)
    3. Few-shot examples
    4. Historial antiguo (mensajes más viejos primero)
    5. Mensaje actual (nunca se corta)
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AlertLevel(Enum):
    GREEN = "green"
    YELLOW = "yellow"
    ORANGE = "orange"
    RED = "red"

    def __str__(self) -> str:
        return self.value


# Conservador: 3.5 chars/token promedio mezcla ES/EN/código
_CHARS_PER_TOKEN = 3.5

# Reservar tokens para la respuesta del modelo
_OUTPUT_RESERVE_DEFAULT = 2048

# Umbrales de alerta (fracción del budget de entrada)
_THRESH_YELLOW = 0.70
_THRESH_ORANGE = 0.85
_THRESH_RED = 0.95


def estimate_tokens(text: str) -> int:
    """Estimación heurística de tokens para un string."""
    if not text:
        return 0
    return max(len(text) // int(_CHARS_PER_TOKEN), 1)


def estimate_messages_tokens(messages: list[dict[str, Any]]) -> int:
    """Estima tokens totales de una lista de mensajes en formato provider."""
    total = 0
    for msg in messages:
        # Cada mensaje tiene overhead de roles/tool_calls (~4 tokens)
        total += 4
        content = msg.get("content", "")
        if isinstance(content, str):
            total += estimate_tokens(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    total += estimate_tokens(str(part.get("text", "")))
        # tool_calls
        tc = msg.get("tool_calls")
        if tc:
            for call in tc:
                func = call.get("function", {})
                total += estimate_tokens(json_serialize(func))
    return total


def json_serialize(obj: Any) -> str:
    import json
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        return str(obj)


@dataclass
class BudgetReport:
    """Reporte del cálculo de budget antes de enviar al LLM."""
    model_context_tokens: int
    output_reserve: int
    input_budget: int
    system_tokens: int
    messages_tokens: int
    tools_tokens: int
    estimated_input_tokens: int
    available_tokens: int
    usage_fraction: float
    alert_level: AlertLevel
    messages_count: int
    truncated: bool = False
    truncated_messages_count: int = 0
    layers_dropped: list[str] = field(default_factory=list)

    @property
    def is_critical(self) -> bool:
        return self.alert_level in (AlertLevel.ORANGE, AlertLevel.RED)

    @property
    def is_truncation_imminent(self) -> bool:
        return self.alert_level == AlertLevel.RED

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_context_tokens": self.model_context_tokens,
            "output_reserve": self.output_reserve,
            "input_budget": self.input_budget,
            "system_tokens": self.system_tokens,
            "messages_tokens": self.messages_tokens,
            "tools_tokens": self.tools_tokens,
            "estimated_input_tokens": self.estimated_input_tokens,
            "available_tokens": self.available_tokens,
            "usage_fraction": round(self.usage_fraction, 4),
            "alert_level": str(self.alert_level),
            "messages_count": self.messages_count,
            "truncated": self.truncated,
            "truncated_messages_count": self.truncated_messages_count,
            "layers_dropped": self.layers_dropped,
        }

    def banner(self, color: bool = True) -> str:
        """Banner visual grande para el REPL cuando hay alerta."""
        if self.alert_level == AlertLevel.GREEN:
            return ""
        pct = int(self.usage_fraction * 100)
        bar_filled = pct // 5
        bar_empty = 20 - bar_filled
        bar = "█" * bar_filled + "░" * bar_empty

        if self.alert_level == AlertLevel.RED:
            icon = "🟥"
            label = "TRUNCAMIENTO INMINENTE"
            ansi = "\033[91m" if color else ""
        elif self.alert_level == AlertLevel.ORANGE:
            icon = "🟧"
            label = "CONTEXTO CRÍTICO"
            ansi = "\033[38;5;208m" if color else ""
        else:
            icon = "🟨"
            label = "CONTEXTO ALTO"
            ansi = "\033[93m" if color else ""

        reset = "\033[0m" if color else ""
        lines = [
            "",
            f"{ansi}╔══════════════════════════════════════════════════════════════╗{reset}",
            f"{ansi}║  {icon}  {label:<52s}{reset}",
            f"{ansi}║                                                              {reset}",
            f"{ansi}║  Budget: [{bar}] {pct:>3d}%                                       {reset}",
            f"{ansi}║  Modelo: {self.model_context_tokens:>6d} ctx · entrada: {self.estimated_input_tokens:>6d} tok     {reset}",
            f"{ansi}║  Mensajes: {self.messages_count:>4d} · system: {self.system_tokens:>5d} tok · tools: {self.tools_tokens:>4d} tok   {reset}",
        ]

        if self.truncated:
            lines.append(
                f"{ansi}║  ⚠ Truncado: {self.truncated_messages_count} mensajes descartados                       {reset}"
            )
            if self.layers_dropped:
                dropped = ", ".join(self.layers_dropped)
                lines.append(
                    f"{ansi}║  Capas cortadas: {dropped:<47s}{reset}"
                )

        if self.alert_level == AlertLevel.RED:
            lines.append(
                f"{ansi}║  El modelo puede perder contexto o fallar. Considera:        {reset}"
            )
            lines.append(
                f"{ansi}║  /switch a modelo con mayor ventana · /compact para comprimir{reset}"
            )

        lines.append(f"{ansi}╚══════════════════════════════════════════════════════════════╝{reset}")
        lines.append("")
        return "\n".join(lines)


def compute_budget(
    system_prompt: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    model_context_tokens: int,
    output_reserve: int = _OUTPUT_RESERVE_DEFAULT,
) -> BudgetReport:
    """Calcula el budget antes de enviar al LLM.

    No modifica nada — solo reporta. El truncamiento lo hace truncate_context().
    """
    input_budget = max(model_context_tokens - output_reserve, 512)

    system_tokens = estimate_tokens(system_prompt)
    messages_tokens = estimate_messages_tokens(messages)
    tools_tokens = estimate_tokens(json_serialize(tools)) if tools else 0

    estimated_input = system_tokens + messages_tokens + tools_tokens
    available = input_budget - estimated_input
    usage_frac = estimated_input / input_budget if input_budget > 0 else 1.0

    if usage_frac >= _THRESH_RED:
        alert = AlertLevel.RED
    elif usage_frac >= _THRESH_ORANGE:
        alert = AlertLevel.ORANGE
    elif usage_frac >= _THRESH_YELLOW:
        alert = AlertLevel.YELLOW
    else:
        alert = AlertLevel.GREEN

    return BudgetReport(
        model_context_tokens=model_context_tokens,
        output_reserve=output_reserve,
        input_budget=input_budget,
        system_tokens=system_tokens,
        messages_tokens=messages_tokens,
        tools_tokens=tools_tokens,
        estimated_input_tokens=estimated_input,
        available_tokens=max(available, 0),
        usage_fraction=min(usage_frac, 1.0),
        alert_level=alert,
        messages_count=len(messages),
    )


def truncate_context(
    system_prompt: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    model_context_tokens: int,
    output_reserve: int = _OUTPUT_RESERVE_DEFAULT,
    *,
    preserve_last_n: int = 6,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]] | None, BudgetReport]:
    """Trunca el contexto por capas para caber en el budget.

    Orden de truncamiento:
      1. Descarta tools (si los hay)
      2. Descarta mensajes antiguos del historial (preserva últimos N)

    Returns:
        (messages_truncated, tools_truncated_or_None, report)
    """
    original_count = len(messages)
    layers_dropped: list[str] = []

    # Intentar sin truncar primero
    report = compute_budget(
        system_prompt, messages, tools, model_context_tokens, output_reserve
    )

    if not report.is_critical:
        return messages, tools, report

    input_budget = max(model_context_tokens - output_reserve, 512)

    # Capa 1: quitar tools si excede
    if tools and report.estimated_input_tokens > input_budget:
        tools = None
        layers_dropped.append("tools")
        report = compute_budget(
            system_prompt, messages, tools, model_context_tokens, output_reserve
        )

    # Capa 2: truncar historial antiguo
    if report.is_critical and len(messages) > preserve_last_n:
        # Preservar: system (si está como primer mensaje) + últimos N
        # En formato provider, system va aparte (no en messages), así que
        # solo preservamos los últimos N mensajes.
        truncated = messages[-preserve_last_n:]
        dropped_count = original_count - len(truncated)
        if dropped_count > 0:
            layers_dropped.append(f"history(-{dropped_count})")
            messages = truncated
            report = compute_budget(
                system_prompt, messages, tools, model_context_tokens, output_reserve
            )

    # Recalcular report final con flag truncated
    report.truncated = len(layers_dropped) > 0
    report.truncated_messages_count = original_count - len(messages)
    report.layers_dropped = layers_dropped

    return messages, tools, report


def _run_tests() -> int:
    """Tests inline — sin dependencias externas."""
    # Test 1: estimate_tokens básico
    assert estimate_tokens("") == 0
    assert estimate_tokens("hello world") >= 2
    print("  ✓ estimate_tokens")

    # Test 2: GREEN budget
    msgs = [{"role": "user", "content": "hola"}]
    r = compute_budget("system", msgs, None, model_context_tokens=32768)
    assert r.alert_level == AlertLevel.GREEN
    assert r.usage_fraction < 0.01
    assert r.is_critical is False
    assert r.is_truncation_imminent is False
    assert r.banner() == ""
    print("  ✓ GREEN budget")

    # Test 3: RED budget (historial enorme)
    big_msgs = [{"role": "user", "content": "x" * 200}, {"role": "assistant", "content": "y" * 200}] * 500
    r = compute_budget("system", big_msgs, None, model_context_tokens=32768)
    assert r.alert_level == AlertLevel.RED
    assert r.is_truncation_imminent
    assert r.is_critical
    banner = r.banner()
    assert "TRUNCAMIENTO" in banner
    assert "🟥" in banner
    assert "\033[" in banner
    plain = r.banner(color=False)
    assert "\033[" not in plain
    print("  ✓ RED budget + banner")

    # Test 4: truncate_context en acción
    big_msgs2 = [{"role": "user", "content": "x" * 200}, {"role": "assistant", "content": "y" * 200}] * 500
    tools = [{"type": "function", "function": {"name": "test", "parameters": {}}}]
    trunc_msgs, trunc_tools, report = truncate_context(
        "system", big_msgs2, tools, model_context_tokens=32768, preserve_last_n=6
    )
    assert report.truncated
    assert len(trunc_msgs) <= 6
    assert trunc_tools is None
    assert "tools" in report.layers_dropped
    assert "history" in ",".join(report.layers_dropped)
    print(f"  ✓ truncate_context: {len(big_msgs2)} → {len(trunc_msgs)} msgs, tools=None")

    # Test 5: BudgetReport.to_dict serializable
    d = r.to_dict()
    assert "alert_level" in d
    assert d["alert_level"] == "red"
    assert "usage_fraction" in d
    print("  ✓ to_dict")

    # Test 6: ORANGE level
    mid_msgs = [{"role": "user", "content": "a" * 4000}, {"role": "assistant", "content": "b" * 4000}] * 20
    r = compute_budget("s" * 2000, mid_msgs, None, model_context_tokens=32768)
    assert r.alert_level in (AlertLevel.YELLOW, AlertLevel.ORANGE, AlertLevel.RED)
    print(f"  ✓ mid-range budget: {r.alert_level} ({r.usage_fraction:.1%})")

    print("context_budget.py --test: ALL PASS")
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
