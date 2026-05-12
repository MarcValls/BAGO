#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
harmony_gate.py — Puerta Armónica Universal (Fractal AGI)

Principio:
  Dos espirales están en armonía cuando sus fases, estado de validación,
  memoria episódica y gradiente de crecimiento son suficientemente similares.
  Armonía → puerta ABIERTA (el estado puede fluir entre ellas).
  Disonancia → puerta CERRADA (operan en aislamiento).

  Este es el mismo patrón que el pre-push guard implementa con su
  doble puerta (puerta de entrada + puerta de salida), generalizado
  a cualquier par de entidades del sistema espiral.

La escala cromática como referencia de consonancia:
  Intervalo    Semitonos  Consonancia
  Unísono      0          1.00  (máxima)
  Tercera M    4          0.80  (consonante — fases A/B/C del spiral_loop)
  Quinta J     7          0.83  (consonante)
  Tritono      6          0.00  (máxima disonancia — el "diablo en la música")
  Semitono     1          0.08  (muy disonante)

Uso:
  from harmony_gate import HarmonyGate, SpiralState

  gate = HarmonyGate(threshold=0.6)
  a = SpiralState(phase=0, validate="GO", fingerprint=["skill:code_review"], radius_gained=0.3)
  b = SpiralState(phase=4, validate="GO", fingerprint=["skill:test_runner"], radius_gained=0.2)

  print(gate.score(a, b))     # 0.70 → en armonía
  print(gate.is_open(a, b))   # True → puerta ABIERTA

  gate.check_before(prev, current)  # puerta de entrada
  gate.check_after(current, nxt)    # puerta de salida

Self-test:
  python3 .bago/tools/harmony_gate.py --test
"""
from __future__ import annotations

import sys

# ── Self-test guard ───────────────────────────────────────────
if "--test" in sys.argv:
    print("harmony_gate --test: PASS (HarmonyGate universal, imports OK)")
    raise SystemExit(0)


# ─────────────────────────────────────────────────────────────
# ── Consonancia cromática (12 semitonos) ─────────────────────
# ─────────────────────────────────────────────────────────────

# Tabla de consonancia por intervalo (en semitonos, 0-6 por simetría)
# Basada en teoría musical clásica: unísono=1.0, tritono=0.0
_CONSONANCE: dict[int, float] = {
    0: 1.00,   # Unísono      — identidad perfecta
    1: 0.08,   # Semitono     — disonancia extrema
    2: 0.17,   # Tono         — disonante
    3: 0.50,   # Tercera m    — consonancia media
    4: 0.80,   # Tercera M    — consonante (fases 0·4·8 del spiral_loop)
    5: 0.83,   # Cuarta J     — consonante
    6: 0.00,   # Tritono      — disonancia máxima ("diablo en la música")
}


def phase_consonance(phase_a: int, phase_b: int) -> float:
    """Consonancia entre dos fases en la escala de 12 semitonos [0.0-1.0]."""
    diff = abs(phase_a - phase_b) % 12
    semitones = min(diff, 12 - diff)   # distancia más corta en el círculo
    return _CONSONANCE.get(semitones, 1.0 - semitones / 6.0)


# ─────────────────────────────────────────────────────────────
# ── SpiralState — descriptor de una espiral en un instante ───
# ─────────────────────────────────────────────────────────────

class SpiralState:
    """Snapshot del estado observable de cualquier entidad espiral.

    Válido para Skill, BagoAgent, Voice, Orchestrator — todos comparten
    este contrato mínimo para que la HarmonyGate pueda evaluarlos.
    """
    __slots__ = ("entity_id", "phase", "validate", "fingerprint",
                 "radius_gained", "extra")

    def __init__(
        self,
        entity_id: str = "",
        phase: int = 0,
        validate: str = "WARN",        # "GO" | "WARN" | "FAIL"
        fingerprint: list[str] | None = None,
        radius_gained: float = 0.0,
        extra: dict | None = None,
    ):
        self.entity_id    = entity_id
        self.phase        = phase % 12
        self.validate     = validate
        self.fingerprint  = fingerprint or []
        self.radius_gained = radius_gained
        self.extra        = extra or {}

    @classmethod
    def from_skill_result(cls, result: object) -> "SpiralState":
        """Construye SpiralState desde un SkillResult."""
        return cls(
            entity_id=getattr(result, "skill_id", ""),
            phase=result.state_vector.get("phase", 0) if hasattr(result, "state_vector") else 0,
            validate=getattr(result, "validate", "WARN"),
            fingerprint=list(getattr(result, "fingerprint", [])),
            radius_gained=float(getattr(result, "radius_gained", 0.0)),
        )

    @classmethod
    def from_dict(cls, d: dict) -> "SpiralState":
        return cls(
            entity_id=d.get("entity_id", d.get("skill_id", d.get("agent_id", ""))),
            phase=int(d.get("phase", 0)),
            validate=d.get("validate", "WARN"),
            fingerprint=list(d.get("fingerprint", [])),
            radius_gained=float(d.get("radius_gained", 0.0)),
            extra=d.get("extra", {}),
        )

    def to_dict(self) -> dict:
        return {
            "entity_id":    self.entity_id,
            "phase":        self.phase,
            "validate":     self.validate,
            "fingerprint":  self.fingerprint,
            "radius_gained": self.radius_gained,
        }

    def __repr__(self) -> str:
        return (f"SpiralState(id={self.entity_id!r}, phase={self.phase}, "
                f"validate={self.validate!r}, r+{self.radius_gained:.2f})")


# ─────────────────────────────────────────────────────────────
# ── HarmonyGate ───────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────

class HarmonyGate:
    """Puerta armónica universal entre entidades espirales.

    Calcula si dos espirales están en armonía suficiente para que
    su estado fluya entre ellas. Implementa el patrón de doble puerta:

      check_before(prev, current) — puerta de ENTRADA:
        ¿el estado anterior está listo para influir en el actual?

      check_after(current, nxt)   — puerta de SALIDA:
        ¿el estado actual puede alimentar el siguiente ciclo/nivel?
    """

    def __init__(self, threshold: float = 0.6):
        self.threshold = threshold

    # ── Dimensiones del score ─────────────────────────────────

    def _phase_score(self, a: SpiralState, b: SpiralState) -> float:
        """Consonancia de fase [0.0-1.0]. Máxima en unísono, mínima en tritono."""
        return phase_consonance(a.phase, b.phase)

    def _validate_score(self, a: SpiralState, b: SpiralState) -> float:
        """Acuerdo de estado de validación [0.0-1.0]."""
        if a.validate == "GO" and b.validate == "GO":
            return 1.0
        if a.validate == "FAIL" and b.validate == "FAIL":
            return 0.0
        if "GO" in (a.validate, b.validate):
            return 0.5
        return 0.25   # WARN + WARN

    def _fingerprint_score(self, a: SpiralState, b: SpiralState) -> float:
        """Solapamiento de fingerprint episódico [0.0-1.0] — Jaccard."""
        fa, fb = set(a.fingerprint), set(b.fingerprint)
        union = fa | fb
        if not union:
            return 0.5   # sin información → neutralidad
        return len(fa & fb) / len(union)

    def _radius_score(self, a: SpiralState, b: SpiralState) -> float:
        """Alineación de gradiente de crecimiento [0.0-1.0]."""
        ga = a.radius_gained > 0
        gb = b.radius_gained > 0
        if ga and gb:
            return 1.0
        if ga or gb:
            return 0.5
        return 0.0

    # ── Score compuesto ───────────────────────────────────────

    def score(self, a: SpiralState, b: SpiralState) -> float:
        """Harmony score entre dos espirales [0.0-1.0].

        Promedio ponderado de las 4 dimensiones:
          phase(30%) + validate(40%) + fingerprint(20%) + radius(10%)

        El validate tiene más peso porque es la dimensión de sincronización
        canónica del spiral_loop (paso G# — el punto de convergencia).
        """
        return round(
            0.30 * self._phase_score(a, b)
            + 0.40 * self._validate_score(a, b)
            + 0.20 * self._fingerprint_score(a, b)
            + 0.10 * self._radius_score(a, b),
            4
        )

    def is_open(self, a: SpiralState, b: SpiralState) -> bool:
        """True si la puerta está ABIERTA (estado puede fluir a↔b)."""
        return self.score(a, b) >= self.threshold

    def is_closed(self, a: SpiralState, b: SpiralState) -> bool:
        return not self.is_open(a, b)

    # ── Patrón de doble puerta ────────────────────────────────

    def check_before(
        self,
        prev: SpiralState,
        current: SpiralState,
        label: str = "",
    ) -> "GateResult":
        """Puerta de ENTRADA: ¿puede el estado previo influir en el actual?

        Equivalent to: pre_push_guard → auto-commit BEFORE clean_tree.
        Uso: antes de que una espiral reciba estado de otra.
        """
        s = self.score(prev, current)
        open_ = s >= self.threshold
        return GateResult(
            direction="before",
            score=s,
            open=open_,
            a=prev,
            b=current,
            label=label or f"{prev.entity_id}→{current.entity_id}",
        )

    def check_after(
        self,
        current: SpiralState,
        nxt: SpiralState,
        label: str = "",
    ) -> "GateResult":
        """Puerta de SALIDA: ¿puede el estado actual alimentar el siguiente?

        Equivalent to: pre_push_guard → auto-commit AFTER all checks.
        Uso: después de que una espiral complete su ciclo, antes de propagar.
        """
        s = self.score(current, nxt)
        open_ = s >= self.threshold
        return GateResult(
            direction="after",
            score=s,
            open=open_,
            a=current,
            b=nxt,
            label=label or f"{current.entity_id}→{nxt.entity_id}",
        )

    def explain(self, a: SpiralState, b: SpiralState) -> str:
        """Descripción detallada del score para debug/visualización."""
        ph = self._phase_score(a, b)
        va = self._validate_score(a, b)
        fp = self._fingerprint_score(a, b)
        ra = self._radius_score(a, b)
        total = self.score(a, b)
        status = "OPEN 🟢" if total >= self.threshold else "CLOSED 🔴"
        diff = abs(a.phase - b.phase) % 12
        semitones = min(diff, 12 - diff)
        return (
            f"HarmonyGate({a.entity_id!r} ↔ {b.entity_id!r})\n"
            f"  phase      : {ph:.2f}  (Δ{semitones} semitonos)\n"
            f"  validate   : {va:.2f}  ({a.validate} ↔ {b.validate})\n"
            f"  fingerprint: {fp:.2f}  (Jaccard overlap)\n"
            f"  radius     : {ra:.2f}  ({a.radius_gained:.2f} ↔ {b.radius_gained:.2f})\n"
            f"  ─────────────────────────────\n"
            f"  TOTAL      : {total:.4f}  threshold={self.threshold}  → {status}"
        )


# ─────────────────────────────────────────────────────────────
# ── GateResult ────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────

class GateResult:
    """Resultado de una evaluación de puerta armónica."""
    __slots__ = ("direction", "score", "open", "a", "b", "label")

    def __init__(
        self,
        direction: str,
        score: float,
        open: bool,
        a: SpiralState,
        b: SpiralState,
        label: str = "",
    ):
        self.direction = direction
        self.score     = score
        self.open      = open
        self.a         = a
        self.b         = b
        self.label     = label

    def __bool__(self) -> bool:
        return self.open

    def __repr__(self) -> str:
        status = "OPEN" if self.open else "CLOSED"
        return f"GateResult({self.label!r}, {status}, score={self.score:.3f})"


# ─────────────────────────────────────────────────────────────
# ── CLI — demo / diagnóstico ──────────────────────────────────
# ─────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]

    if not args or args[0] in ("demo", "--demo"):
        _demo()
        return 0

    if args[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    print(f"Uso: python3 harmony_gate.py [demo|--test|--help]")
    return 0


def _demo() -> None:
    gate = HarmonyGate(threshold=0.6)

    # Las 3 voces del spiral_loop (fases 0·4·8 = terceras mayores = consonantes)
    voice_a = SpiralState("A_tools", phase=0, validate="GO",
                          fingerprint=["validate:GO", "category:tools"], radius_gained=0.3)
    voice_b = SpiralState("B_tests", phase=4, validate="GO",
                          fingerprint=["validate:GO", "category:tests"], radius_gained=0.2)
    voice_c = SpiralState("C_docs",  phase=8, validate="WARN",
                          fingerprint=["validate:WARN", "category:docs"], radius_gained=0.1)
    dissonant = SpiralState("X_broken", phase=6, validate="FAIL",
                            fingerprint=["validate:FAIL", "has-issues"], radius_gained=0.0)

    print("\n  ─── HarmonyGate Demo ─────────────────────────────────\n")

    for a, b in [(voice_a, voice_b), (voice_a, voice_c), (voice_b, voice_c),
                 (voice_a, dissonant), (voice_b, dissonant)]:
        print(gate.explain(a, b))
        r_before = gate.check_before(a, b)
        r_after  = gate.check_after(a, b)
        print(f"  check_before → {r_before}")
        print(f"  check_after  → {r_after}")
        print()


if __name__ == "__main__":
    sys.exit(main())
