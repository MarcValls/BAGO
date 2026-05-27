from __future__ import annotations

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import json
import re
from pathlib import Path

from .constants import ROUTING_FILE, USER_BAGO, PROVIDERS_FILE, STATE_DIR

RUNTIME_FILE = USER_BAGO / "routing_runtime.json"
PRESETS_FILE = STATE_DIR / "routing_presets.json"

DEFAULT_PRESETS = {
    "balanced": {
        "description": "Balance general entre coste, velocidad y calidad.",
        "orch_mode": "standard",
        "provider_order": ["ollama-local", "copilot", "codex", "ollama-cloud"],
        "contract_loop": {"enabled": True, "max_iter": 3, "min_score": 0.84},
    },
    "local-first": {
        "description": "Prioriza local y solo escala fuera si falla o no alcanza contrato.",
        "orch_mode": "eco",
        "provider_order": ["ollama-local", "ollama-cloud", "copilot", "codex"],
        "contract_loop": {"enabled": True, "max_iter": 2, "min_score": 0.78},
    },
    "review-heavy": {
        "description": "Genera y luego revisa con modelos de mayor criterio.",
        "orch_mode": "full",
        "provider_order": ["copilot", "codex", "ollama-local", "ollama-cloud"],
        "contract_loop": {"enabled": True, "max_iter": 4, "min_score": 0.88},
    },
    "contract-strict": {
        "description": "No cierra hasta acercarse al contrato objetivo; mas iteraciones.",
        "orch_mode": "full",
        "provider_order": ["codex", "copilot", "ollama-local", "ollama-cloud"],
        "contract_loop": {"enabled": True, "max_iter": 6, "min_score": 1.0},
    },
    "music-build": {
        "description": "Construccion del proyecto musical: analisis fuerte, revision cruzada y cierre estricto.",
        "orch_mode": "full",
        "provider_order": ["codex", "copilot", "ollama-local", "ollama-cloud"],
        "contract_loop": {"enabled": True, "max_iter": 5, "min_score": 1.0},
    },
    "music-runtime": {
        "description": "Runtime integrado en el producto: local-first, rapido y con salida contractual.",
        "orch_mode": "eco",
        "provider_order": ["ollama-local", "ollama-cloud", "copilot", "codex"],
        "contract_loop": {"enabled": True, "max_iter": 3, "min_score": 1.0},
    },
}

DEFAULT_RUNTIME = {
    "active_preset": "balanced",
    "contract": {"text": "", "source": "none"},
}

_STOPWORDS = {
    "solo", "sin", "con", "para", "pero", "como", "esto", "esta", "este", "debe",
    "deben", "devolver", "devuelve", "respuesta", "salida", "usar", "uses", "must",
    "the", "and", "that", "with", "from", "into", "sobre", "entre", "hasta",
}


def _read_json(path: Path, fallback):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        pass
    return fallback


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def ensure_runtime_files() -> None:
    if not PRESETS_FILE.exists():
        _write_json(PRESETS_FILE, DEFAULT_PRESETS)
    if not RUNTIME_FILE.exists():
        _write_json(RUNTIME_FILE, DEFAULT_RUNTIME)


def load_presets() -> dict:
    ensure_runtime_files()
    data = _read_json(PRESETS_FILE, DEFAULT_PRESETS)
    if not isinstance(data, dict):
        return dict(DEFAULT_PRESETS)
    merged = dict(DEFAULT_PRESETS)
    merged.update(data)
    return merged


def load_runtime() -> dict:
    ensure_runtime_files()
    runtime = _read_json(RUNTIME_FILE, DEFAULT_RUNTIME)
    if not isinstance(runtime, dict):
        runtime = dict(DEFAULT_RUNTIME)
    runtime.setdefault("active_preset", DEFAULT_RUNTIME["active_preset"])
    runtime.setdefault("contract", {"text": "", "source": "none"})
    return runtime


def save_runtime(runtime: dict) -> None:
    _write_json(RUNTIME_FILE, runtime)


def active_settings() -> dict:
    presets = load_presets()
    runtime = load_runtime()
    preset_name = runtime.get("active_preset", "balanced")
    preset = presets.get(preset_name, presets["balanced"])
    return {
        "preset_name": preset_name,
        "preset": preset,
        "runtime": runtime,
        "contract_text": (runtime.get("contract") or {}).get("text", "").strip(),
    }


def apply_preset(name: str) -> dict:
    presets = load_presets()
    if name not in presets:
        raise KeyError(name)
    runtime = load_runtime()
    runtime["active_preset"] = name
    save_runtime(runtime)
    return presets[name]


def set_contract(text: str, source: str = "explicit") -> None:
    runtime = load_runtime()
    runtime["contract"] = {"text": text.strip(), "source": source}
    save_runtime(runtime)


def clear_contract() -> None:
    runtime = load_runtime()
    runtime["contract"] = {"text": "", "source": "none"}
    save_runtime(runtime)


def _find_line_limit(text: str) -> int | None:
    m = re.search(r"(?:max|máx|maximo|máximo)\s*(\d+)\s*l[ií]neas", text, re.I)
    return int(m.group(1)) if m else None


def infer_contract(user_input: str) -> str:
    text = user_input.strip()
    clauses: list[str] = []
    lower = text.lower()
    for raw in text.splitlines():
        line = raw.strip(" -*\t")
        if not line:
            continue
        if raw.lstrip().startswith(("-", "*")):
            clauses.append(line)
    if "solo código" in lower or "solo codigo" in lower:
        clauses.append("solo codigo")
    if "sin explicación" in lower or "sin explicacion" in lower:
        clauses.append("sin explicacion")
    if "sin comentarios" in lower:
        clauses.append("sin comentarios")
    if "solo diff" in lower:
        clauses.append("solo diff")
    max_lines = _find_line_limit(text)
    if max_lines:
        clauses.append(f"max {max_lines} lineas")
    if not clauses:
        return ""
    out = []
    seen = set()
    for clause in clauses:
        norm = clause.lower().strip()
        if norm not in seen:
            seen.add(norm)
            out.append(clause)
    return "\n".join(f"- {c}" for c in out)


def resolve_contract(user_input: str, explicit: str = "") -> str:
    explicit = (explicit or "").strip()
    if explicit:
        return explicit
    runtime_contract = active_settings()["contract_text"]
    if runtime_contract:
        return runtime_contract
    return infer_contract(user_input)


def _keywords(line: str) -> set[str]:
    words = re.findall(r"[a-zA-ZáéíóúÁÉÍÓÚ0-9_./-]+", line.lower())
    return {w for w in words if len(w) >= 4 and w not in _STOPWORDS}


def validate_contract(contract_text: str, output_text: str) -> dict:
    contract_text = (contract_text or "").strip()
    output_text = output_text or ""
    if not contract_text:
        return {"ok": True, "score": 1.0, "unmet": [], "checks": []}

    checks = []
    unmet = []
    out_lower = output_text.lower()

    clauses = [ln.strip(" -*\t") for ln in contract_text.splitlines() if ln.strip()]
    for clause in clauses:
        clause_lower = clause.lower()
        ok = True
        detail = clause
        if clause_lower == "solo codigo":
            ok = not any(tok in out_lower for tok in ["explicacion", "explanation", "porque", "why ", "resumen"])
        elif clause_lower == "sin explicacion":
            ok = not any(tok in out_lower for tok in ["porque", "explic", "reason", "overview"])
        elif clause_lower == "sin comentarios":
            ok = "#" not in output_text and "//" not in output_text
        elif clause_lower == "solo diff":
            ok = any(tok in output_text for tok in ["*** Begin Patch", "diff --git", "@@"])
        elif clause_lower.startswith("max ") and " lineas" in clause_lower:
            m = re.search(r"max\s+(\d+)\s+lineas", clause_lower)
            limit = int(m.group(1)) if m else 0
            ok = len(output_text.splitlines()) <= limit
            detail = f"{clause} ({len(output_text.splitlines())}/{limit})"
        else:
            kws = _keywords(clause)
            if kws:
                hits = sum(1 for kw in kws if kw in out_lower)
                ok = hits >= max(1, len(kws) // 2)
                detail = f"{clause} ({hits}/{len(kws)} keywords)"
        checks.append({"clause": clause, "ok": ok, "detail": detail})
        if not ok:
            unmet.append(detail)

    score = 1.0 if not checks else (sum(1 for c in checks if c["ok"]) / len(checks))
    return {"ok": not unmet, "score": round(score, 3), "unmet": unmet, "checks": checks}


def load_providers_snapshot() -> dict:
    return _read_json(PROVIDERS_FILE, {}).get("providers", {})


def load_routing_snapshot() -> dict:
    return _read_json(ROUTING_FILE, {"rules": [], "fallback": {"provider": "ollama-local", "model": "qwen25-mini"}})


def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(f"{Path(__file__).name} --test: PASS (imports OK)")
    return 0
if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
