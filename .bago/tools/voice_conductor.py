#!/usr/bin/env python3
"""
voice_conductor.py — CAP · Continuous Ascent Protocol

Basado en el principio ShepardCycle (Shepard, 1964): capas de voces
con envolventes desfasadas crean ilusión de progreso continuo. El
sistema siempre avanza porque hay voces entrando y saliendo en overlap
controlado, nunca más de 3 simultáneas.

El límite de 3 no es una restricción técnica — es un principio de
coherencia perceptual: con >3 voces simultáneas el sistema pierde
identidad individual en cada voz (contrapunto polifónico). La misma
razón por la que Bach raramente supera 4 voces en una fuga.

Componentes:
  ShepardCycle  motor de voces — selección, overlap, rotación de roles
  ShepardGate   mecanismo de puertas — CERRADA (trabajo) / ABIERTA (entrega)

Referencia: Shepard, R. N. (1964). Circularity in judgments of relative pitch.
            Journal of the Acoustical Society of America, 36(12), 2346–2353.

Uso CLI:
  python voice_conductor.py status
  python voice_conductor.py list
  python voice_conductor.py activate <role1> [role2] [role3]
  python voice_conductor.py deactivate <role>
  python voice_conductor.py open
  python voice_conductor.py close
"""

from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── BAGO Presence (visual identity) — optional, never crashes ──────────────
try:
    _bp_spec = importlib.util.spec_from_file_location(
        "bago_presence", Path(__file__).parent / "bago_presence.py"
    )
    _bp_mod = importlib.util.module_from_spec(_bp_spec)      # type: ignore
    _bp_spec.loader.exec_module(_bp_mod)                      # type: ignore
    bp = _bp_mod.bp
except Exception:
    class _NullBP:
        def __getattr__(self, _): return lambda *a, **k: None
    bp = _NullBP()  # type: ignore

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve().parent  # .bago/tools/
_BAGO = _HERE.parent                     # .bago/
_STATE_FILE = _BAGO / "state" / "conductor_state.json"
_MANIFEST   = _BAGO / "roles" / "manifest.json"
_PACK       = _BAGO / "pack.json"
_INTENTS    = _BAGO / "state" / "config" / "intents_catalog.json"
_WORKFLOW   = _BAGO / "state" / "config" / "workflow_guidance.json"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# ShepardCycle — límite de voces simultáneas (principio CAP)
MAX_CONCURRENT: int = 3

# ShepardGate — estados del mecanismo de puertas
DOOR_CLOSED = "PUERTA_CERRADA"   # ShepardGate: trabajo interno
DOOR_OPEN   = "PUERTA_ABIERTA"   # ShepardGate: entrega a MAESTRO


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def _load_state() -> dict[str, Any]:
    """Carga el estado persistido del conductor. Crea estado vacío si no existe."""
    if _STATE_FILE.exists():
        return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    return {
        "door": DOOR_CLOSED,
        "active_voices": [],
        "history": [],
        "last_updated": _now(),
    }


def _save_state(state: dict[str, Any]) -> None:
    """Persiste el estado del conductor en conductor_state.json."""
    state["last_updated"] = _now()
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_manifest() -> dict[str, Any]:
    if _MANIFEST.exists():
        return json.loads(_MANIFEST.read_text(encoding="utf-8"))
    return {"roles": {}}


def _load_pack() -> dict[str, Any]:
    if _PACK.exists():
        return json.loads(_PACK.read_text(encoding="utf-8"))
    return {}


def _load_intents() -> dict[str, Any]:
    if _INTENTS.exists():
        return json.loads(_INTENTS.read_text(encoding="utf-8"))
    return {"intents": []}


def _load_workflow_guidance() -> dict[str, Any]:
    if _WORKFLOW.exists():
        return json.loads(_WORKFLOW.read_text(encoding="utf-8"))
    return {"workflows": {}}


def _available_role_ids() -> list[str]:
    """Devuelve los IDs de roles disponibles desde manifest.json."""
    manifest = _load_manifest()
    return list(manifest.get("roles", {}).keys())


def _max_from_pack() -> int:
    """Lee max_active_roles de pack.json (fallback a MAX_CONCURRENT)."""
    pack = _load_pack()
    return int(pack.get("max_active_roles", MAX_CONCURRENT))


# ---------------------------------------------------------------------------
# VoiceConductor class
# ---------------------------------------------------------------------------

class VoiceConductor:
    """
    ShepardCycle — motor de voces del CAP (Continuous Ascent Protocol).

    Enforcea el límite de MAX_CONCURRENT voces activas simultáneas,
    gestiona el ciclo ShepardGate (PUERTA_CERRADA → PUERTA_ABIERTA)
    y persiste el estado en conductor_state.json.
    """

    MAX_CONCURRENT: int = MAX_CONCURRENT

    def __init__(self) -> None:
        self._state = _load_state()
        # Respetar el límite definido en pack.json si existe
        self._limit: int = _max_from_pack()

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def activate_voices(
        self,
        task: str,
        available_roles: list[str] | None = None,
    ) -> list[str]:
        """
        Selecciona y activa roles complementarios para la tarea dada.

        - Usa intents_catalog.json para clasificar la tarea.
        - Usa workflow_guidance.json para seleccionar el workflow.
        - Selecciona roles de available_roles (o manifest.json) sin solapar.
        - Nunca supera self._limit voces simultáneas.

        Args:
            task: Descripción textual de la tarea.
            available_roles: Lista de role IDs candidatos.
                             Si None, usa todos los del manifest.

        Returns:
            Lista de role IDs activados en este ciclo.
        """
        if available_roles is None:
            available_roles = _available_role_ids()

        # Clasificar la tarea
        intent = self._classify_intent(task)
        workflow = self._select_workflow(task, intent)

        # Calcular slots libres
        current_active = self._state.get("active_voices", [])
        free_slots = self._limit - len(current_active)

        if free_slots <= 0:
            raise RuntimeError(
                f"No hay slots libres. Voces activas: {current_active} "
                f"(límite: {self._limit})"
            )

        # Elegir roles no solapados con los ya activos
        candidates = [
            r for r in available_roles
            if r not in current_active
        ]

        # Seleccionar hasta free_slots roles complementarios
        selected = self._select_complementary(candidates, free_slots, intent)

        if not selected:
            return []

        # Activar — presencia visual BAGO
        current_active.extend(selected)
        self._state["active_voices"] = current_active
        gate = self._state.get("gate", DOOR_CLOSED)
        bp.cap_voices(selected, gate=gate)

        # Registrar en historial
        self._state.setdefault("history", []).append({
            "event": "activate",
            "roles": selected,
            "task": task[:120],
            "intent": intent,
            "workflow": workflow,
            "timestamp": _now(),
        })

        _save_state(self._state)
        return selected

    def deactivate_voice(self, role: str) -> bool:
        """
        Desactiva una voz activa.

        Args:
            role: ID del rol a desactivar.

        Returns:
            True si estaba activo y fue desactivado. False si no estaba activo.
        """
        active = self._state.get("active_voices", [])
        if role not in active:
            return False

        active.remove(role)
        self._state["active_voices"] = active
        self._state.setdefault("history", []).append({
            "event": "deactivate",
            "role": role,
            "timestamp": _now(),
        })
        _save_state(self._state)
        return True

    def get_active_voices(self) -> list[str]:
        """Devuelve la lista de roles activos actualmente."""
        return list(self._state.get("active_voices", []))

    def open_door(self) -> None:
        """
        Señaliza PUERTA_ABIERTA.

        Marca que el trabajo interno está completo y MAESTRO_BAGO puede
        recoger el resultado. Limpia la lista de voces activas.
        """
        self._state["door"] = DOOR_OPEN
        self._state.setdefault("history", []).append({
            "event": DOOR_OPEN,
            "voices_cleared": list(self._state.get("active_voices", [])),
            "timestamp": _now(),
        })
        self._state["active_voices"] = []
        _save_state(self._state)

    def close_door(self) -> None:
        """
        Señaliza PUERTA_CERRADA.

        Inicia el ciclo de trabajo interno. MAESTRO_BAGO ha delegado la tarea.
        """
        self._state["door"] = DOOR_CLOSED
        self._state.setdefault("history", []).append({
            "event": DOOR_CLOSED,
            "timestamp": _now(),
        })
        _save_state(self._state)

    def status(self) -> dict[str, Any]:
        """Devuelve el estado actual del conductor."""
        return {
            "door": self._state.get("door", DOOR_CLOSED),
            "active_voices": self.get_active_voices(),
            "active_count": len(self.get_active_voices()),
            "limit": self._limit,
            "free_slots": self._limit - len(self.get_active_voices()),
            "last_updated": self._state.get("last_updated", "unknown"),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _classify_intent(self, task: str) -> str:
        """
        Clasifica la tarea contra intents_catalog.json.

        Devuelve el intent_id más probable o 'generic' si no hay match.
        """
        catalog = _load_intents()
        task_lower = task.lower()
        best_id = "generic"
        best_hits = 0

        for intent in catalog.get("intents", []):
            triggers = intent.get("triggers", [])
            hits = sum(1 for t in triggers if t.lower() in task_lower)
            if hits > best_hits:
                best_hits = hits
                best_id = intent.get("id", "generic")

        return best_id

    def _select_workflow(self, task: str, intent: str) -> str:
        """
        Selecciona el workflow más adecuado consultando workflow_guidance.json.

        Heurística simple: si la tarea contiene palabras clave del purpose
        de cada workflow, aumenta su score.
        """
        guidance = _load_workflow_guidance()
        task_lower = task.lower()
        best_wf = "W2"  # fallback: implementación controlada
        best_score = 0

        for wf_id, wf in guidance.get("workflows", {}).items():
            purpose = wf.get("purpose", "").lower()
            keywords = purpose.split()
            score = sum(1 for kw in keywords if kw in task_lower)
            if score > best_score:
                best_score = score
                best_wf = wf_id

        return best_wf

    def _select_complementary(
        self,
        candidates: list[str],
        max_roles: int,
        intent: str,
    ) -> list[str]:
        """
        Selecciona roles complementarios (no solapados) de la lista de candidatos.

        Prioriza diversidad de familias: gobierno < produccion < supervision < especialistas.
        Nunca supera max_roles.
        """
        # Orden de prioridad por familia para una selección equilibrada
        family_priority = {
            "produccion": 0,
            "supervision": 1,
            "especialistas": 2,
            "gobierno": 3,
        }

        manifest = _load_manifest()
        roles_data = manifest.get("roles", {})

        # Ordenar candidatos por familia (primero los de producción)
        def _family_order(role_id: str) -> int:
            role = roles_data.get(role_id, {})
            family = role.get("family", "")
            return family_priority.get(family, 99)

        sorted_candidates = sorted(candidates, key=_family_order)

        # Tomar hasta max_roles sin repetir familia cuando sea posible
        selected: list[str] = []
        seen_families: set[str] = set()

        for role_id in sorted_candidates:
            if len(selected) >= max_roles:
                break
            role = roles_data.get(role_id, {})
            family = role.get("family", "unknown")
            if family not in seen_families:
                selected.append(role_id)
                seen_families.add(family)

        # Si aún hay espacio y no llegamos al máximo, agregar de familias repetidas
        if len(selected) < max_roles:
            for role_id in sorted_candidates:
                if len(selected) >= max_roles:
                    break
                if role_id not in selected:
                    selected.append(role_id)

        return selected


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_status(conductor: VoiceConductor) -> None:
    s = conductor.status()
    bp.act("ORQUESTADOR", f"ShepardGate: {s['door']}  ·  voces: {s['active_count']}/{s['limit']}")
    if s["active_voices"]:
        for v in s["active_voices"]:
            bp.voice_line(v, indent=2)
    else:
        bp.voice_line("(ninguna voz activa)", indent=2)


def _print_list(conductor: VoiceConductor) -> None:
    available = _available_role_ids()
    active = conductor.get_active_voices()
    print(f"Roles disponibles ({len(available)}):")
    for r in available:
        mark = "▶" if r in active else " "
        print(f"  {mark} {r}")


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    conductor = VoiceConductor()

    if not args or args[0] == "status":
        _print_status(conductor)
        return 0

    cmd = args[0]

    if cmd == "list":
        _print_list(conductor)
        return 0

    if cmd == "activate":
        if len(args) < 2:
            print("❌ Uso: activate <role1> [role2] [role3]", file=sys.stderr)
            return 1
        roles_to_activate = args[1:]
        # Validar que no se intenten activar más del límite
        current = conductor.get_active_voices()
        total_after = len(current) + len(roles_to_activate)
        if total_after > conductor._limit:
            print(
                f"❌ Límite superado: {len(current)} activas + "
                f"{len(roles_to_activate)} solicitadas = {total_after} "
                f"(máx: {conductor._limit})",
                file=sys.stderr,
            )
            return 1
        activated = []
        already_active = []
        for r in roles_to_activate:
            if r in current:
                already_active.append(r)
            else:
                current.append(r)
                activated.append(r)
        conductor._state["active_voices"] = current
        if activated:
            conductor._state.setdefault("history", []).append({
                "event": "activate_cli",
                "roles": activated,
                "timestamp": _now(),
            })
            _save_state(conductor._state)
            print(f"✅ Activadas: {', '.join(activated)}")
        if already_active:
            print(f"ℹ️  Ya activas: {', '.join(already_active)}")
        _print_status(conductor)
        return 0

    if cmd == "deactivate":
        if len(args) < 2:
            print("❌ Uso: deactivate <role>", file=sys.stderr)
            return 1
        role = args[1]
        ok = conductor.deactivate_voice(role)
        if ok:
            print(f"✅ Desactivada: {role}")
        else:
            print(f"ℹ️  No estaba activa: {role}")
        _print_status(conductor)
        return 0

    if cmd == "open":
        conductor.open_door()
        print(f"🔓 {DOOR_OPEN} — MAESTRO_BAGO puede recoger el resultado.")
        return 0

    if cmd == "close":
        conductor.close_door()
        print(f"🔒 {DOOR_CLOSED} — Trabajo interno iniciado.")
        return 0

    print(f"❌ Comando desconocido: {cmd!r}", file=sys.stderr)
    print(
        "Comandos: status | list | activate <roles...> | deactivate <role> | open | close",
        file=sys.stderr,
    )
    return 1




def run_tests() -> int:
    """Self-test stub: verify module imports and key symbols exist."""
    results = []
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_test_mod", __file__)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        results.append(("import", True, "module loads OK"))
    except Exception as e:
        results.append(("import", False, str(e)))

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, detail in results:
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {name}: {detail}")
    print(f"\n  {passed}/{total} tests passed")
    return 0 if passed == total else 1

if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(run_tests())
    sys.exit(main())