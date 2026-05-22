from __future__ import annotations

import json
import hashlib
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))


def _load_cycles(spiral_file: Path) -> dict[str, Any]:
    if spiral_file.exists():
        try:
            return json.loads(spiral_file.read_text())
        except (json.JSONDecodeError, OSError, ValueError):
            pass
    return {"cycles": [], "current_cycle": None, "total_radius": 0.0}



def _save_cycles(spiral_file: Path, data: dict[str, Any]) -> None:
    spiral_file.parent.mkdir(parents=True, exist_ok=True)
    spiral_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))



def _load_gs(gs_file: Path) -> dict[str, Any]:
    try:
        return json.loads(gs_file.read_text())
    except (json.JSONDecodeError, OSError, ValueError):
        return {}


# ── IDEA 3: Memoria episódica (hipocampo) ─────────────────────

def _load_episodic(episodes_file: Path) -> dict[str, Any]:
    if episodes_file.exists():
        try:
            return json.loads(episodes_file.read_text())
        except (json.JSONDecodeError, OSError, ValueError):
            pass
    return {"episodes": [], "total_episodes": 0}



def _save_episodic(episodes_file: Path, data: dict[str, Any]) -> None:
    episodes_file.parent.mkdir(parents=True, exist_ok=True)
    data["total_episodes"] = len(data.get("episodes", []))
    episodes_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))



def _compute_fingerprint(issues: list, gains: list, sv: dict) -> list[str]:
    """Genera etiquetas de fingerprint para búsqueda episódica."""
    tags = []
    health = sv.get("C", 100)
    if isinstance(health, (int, float)):
        if health < 80:
            tags.append("health<80")
        elif health < 95:
            tags.append("health<95")
        else:
            tags.append("health=100")
    drift = sv.get("Ds", 0)
    if drift > 5:
        tags.append("high-drift")
    elif drift > 0:
        tags.append("low-drift")
    else:
        tags.append("no-drift")
    if any("regresión" in i for i in issues):
        tags.append("regression")
    if any("health" in i for i in issues):
        tags.append("health-regression")
    if any("tools" in str(g) for g in gains):
        tags.append("tools-added")
    if sv.get("Gs", 1) == 0:
        tags.append("validate-fail")
    if sv.get("Gs", 1) == 1:
        tags.append("validate-ok")
    return tags



def _search_similar_episodes(
    episodes_file: Path,
    fingerprint: list[str],
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Busca episodios pasados con fingerprint similar (≥2 tags en común)."""
    data = _load_episodic(episodes_file)
    scored = []
    for ep in data.get("episodes", []):
        ep_fp = set(ep.get("fingerprint", []))
        overlap = len(set(fingerprint) & ep_fp)
        if overlap >= 2:
            scored.append((overlap, ep))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [ep for _, ep in scored[:limit]]


# ── IDEA 1: Gradiente de aprendizaje ─────────────────────────

def _default_gradient(steps: list[tuple[str, str, str]]) -> dict[str, Any]:
    return {
        "step_weights": {s[1]: 1.0 for s in steps},
        "proposal_weights": {},
        "last_gradient": {"health_delta": 0.0, "radius_delta": 0.0, "validate_pass": True},
    }



def _load_gradient(
    gradient_file: Path,
    steps: list[tuple[str, str, str]],
    voice_id: str = "main",
) -> dict[str, Any]:
    if gradient_file.exists():
        try:
            data = json.loads(gradient_file.read_text())
            return data.get(voice_id, _default_gradient(steps))
        except (json.JSONDecodeError, OSError, ValueError):
            pass
    return _default_gradient(steps)



def _save_gradient(gradient_file: Path, gdata: dict[str, Any], voice_id: str = "main") -> None:
    gradient_file.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {}
    if gradient_file.exists():
        try:
            data = json.loads(gradient_file.read_text())
        except (json.JSONDecodeError, OSError, ValueError):
            pass
    data[voice_id] = gdata
    gradient_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))


# ── IDEA 2: Polifonía — persistencia de voces ────────────────

def _load_voice_cycles(
    spiral_file: Path,
    voice_id: str,
    voices: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Carga o inicializa el estado de ciclos de una voz específica."""
    data = _load_cycles(spiral_file)
    voice_state = data.setdefault("voices", {})
    if voice_id not in voice_state:
        voice_state[voice_id] = {
            "cycles": [],
            "total_radius": 0.0,
            "phase": voices[voice_id]["phase"],
        }
    return data



def _save_voice_cycle(
    spiral_file: Path,
    data: dict[str, Any],
    voice_id: str,
    cycle_record: dict[str, Any],
    radius_earned: float,
) -> dict[str, Any]:
    """Guarda un ciclo completado en el historial de la voz y en el historial global."""
    data.setdefault("voices", {}).setdefault(voice_id, {"cycles": [], "total_radius": 0.0})
    data["voices"][voice_id]["cycles"].append(cycle_record)
    data["voices"][voice_id]["total_radius"] = round(
        data["voices"][voice_id]["total_radius"] + radius_earned,
        4,
    )
    tagged = dict(cycle_record)
    tagged["_voice"] = voice_id
    data.setdefault("cycles", []).append(tagged)
    data["total_radius"] = round(data.get("total_radius", 0) + radius_earned, 4)
    _save_cycles(spiral_file, data)
    return data



def _bago(
    cmd: list[str],
    bago_script: Path | None = None,
    root: Path | None = None,
    timeout: int = 30,
) -> tuple[int, str, str]:
    if bago_script is None or root is None:
        bago_root = _HERE.parent
        root = bago_root.parent
        bago_script = root / "bago"
    try:
        r = subprocess.run(
            [sys.executable, str(bago_script)] + cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(root),
        )
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as e:
        return -1, "", str(e)
