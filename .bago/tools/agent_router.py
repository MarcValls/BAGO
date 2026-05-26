#!/usr/bin/env python3
"""agent_router.py - Router hibrido local/Codex/Copilot para BAGO.

Modo recomendado: balanced + adaptive.

Flujo:
  1. Reglas duras para tareas con riesgo operativo.
  2. Clasificador local opcional para tareas ambiguas.
  3. Fallback determinista si Ollama no esta disponible o la confianza es baja.
  4. Historial JSONL para auditar decisiones.
"""
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

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from bago.ollama_runtime import default_ollama_base_url

TOOLS_DIR = Path(__file__).resolve().parent
BAGO_ROOT = TOOLS_DIR.parent
REPO_ROOT = BAGO_ROOT.parent
STATE_DIR = BAGO_ROOT / "state"
CFG_FILE = STATE_DIR / "llm_config.json"
HISTORY_FILE = STATE_DIR / "routing_history.jsonl"
OLLAMA_MODELS_DIR = BAGO_ROOT / ".models"

DEFAULT_POLICY: dict = {
    "mode": "balanced",
    "adaptive": True,
    "local_first": True,
    "local_classifier": True,
    "confidence_threshold": 75,
    "classifier_timeout_s": 8,
    "local_agent": "ollama",
    "escalate_to": ["codex", "copilot"],
    "cloud_for_repo_edits": True,
    "cloud_for_execution": True,
    "cloud_for_multifile": True,
    "safe_local_tasks": ["explain", "summarize", "plan", "brainstorm", "small_snippet"],
    "force_codex_tasks": ["edit_files", "run_commands", "tests", "multi_file", "install", "deploy"],
    "force_copilot_tasks": ["pr_review", "diff_review", "code_review"],
}

LOCAL_OK_KEYWORDS = {
    "explica", "explicar", "explain", "resumen", "resume", "summarize",
    "idea", "ideas", "brainstorm", "pregunta", "duda", "concepto",
    "compara", "plan", "planifica", "notas", "pseudocodigo", "pseudocódigo",
    "snippet", "ejemplo", "local", "privado", "offline", "sin internet",
    "rapido", "rápido",
}

CODE_ASSIST_KEYWORDS = {
    "codigo", "código", "code", "bug", "funcion", "función", "test", "tests",
    "pr", "pull request", "refactor", "review", "revision", "revisión", "git",
    "commit", "error", "debug", "typescript", "javascript", "python"  # noqa: HARDCODE,
}

CODEX_KEYWORDS = {
    "script", "archivo", "archivos", "editar", "edita", "modifica",
    "modificar", "implementar", "implementa", "ejecutar", "ejecuta",
    "automatizar", "pipeline", "api", "json", "bash", "powershell",
    "instala", "instalar", "configura", "deploy", "servidor", "repo",
    "proyecto", "tests", "migracion", "migración",
}

ESCALATION_KEYWORDS = {
    "edita", "editar", "modifica", "modificar", "cambia", "cambiar",
    "implementa", "implementar", "crea", "crear", "borra", "borrar",
    "ejecuta", "ejecutar", "instala", "instalar", "arregla", "arreglar",
    "fix", "debug", "falla", "fallo", "error", "test", "tests", "commit",
    "merge", "deploy", "produccion", "producción",
}

REVIEW_KEYWORDS = {
    "pr", "pull request", "review", "revision", "revisión", "revisa",
    "riesgo", "riesgos", "diff", "cambios", "comentarios",
}

MULTIFILE_HINTS = {
    "varios archivos", "multiarchivo", "todo el proyecto", "toda la app",
    "repo completo", "monorepo", "frontend y backend", "full stack",
}

MUSIC_KEYWORDS = {
    "partitura", "score", "musicxml", "transponer", "transpose", "arreglo",
    "arrangement", "nota", "compas", "compás", "clave", "armadura", "midi",
    "musescore", "audiveris", "omr", "render", "partituras", "scores",
    "tonalidad", "semitonos", "semitonos", "intervalo", "voz", "instrumento",
    "bajo", "piano", "guitarra", "violin", "flauta", "clarinete", "saxo",
    "trompeta", "mayor", "menor", "tono", "tempo", "bpm", "ritmo",
    "melodia", "armonia", "acorde", "escala", "modo",
}

ROUTING_FILE = STATE_DIR / "model_routing.json"


@dataclass
class Agent:
    id: str
    name: str
    subtitle: str
    icon: str
    color: str
    available: bool
    reason: str | None
    install_url: str
    models: list[str]
    active_model: str | None = None

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "subtitle": self.subtitle,
            "icon": self.icon,
            "color": self.color,
            "available": self.available,
            "reason": self.reason,
            "install_url": self.install_url,
            "models": self.models,
            "active_model": self.active_model,
        }


def _read_json(path: Path, fallback):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return fallback


def _select_model_for_task(task: str) -> dict | None:
    text = task.lower()
    rules = _read_json(ROUTING_FILE, {}).get("rules", [])
    for rule in rules:
        keywords = rule.get("keywords", [])
        hits = sum(1 for kw in keywords if kw.lower() in text)
        if hits >= 1:
            return {
                "provider": rule.get("provider"),
                "model": rule.get("model"),
                "reason": rule.get("reason"),
                "rule_id": rule.get("id"),
            }
    fallback = _read_json(ROUTING_FILE, {}).get("fallback", {})
    return {
        "provider": fallback.get("provider", "codex"),
        "model": fallback.get("model", "gpt-5.4"),
        "reason": "Fallback: ninguna regla coincide.",
        "rule_id": "fallback",
    }


def load_policy() -> dict:
    cfg = _read_json(CFG_FILE, {})
    policy = dict(DEFAULT_POLICY)
    policy.update(cfg.get("routing_policy", {}))
    policy["mode"] = str(policy.get("mode", "balanced")).lower()
    policy["adaptive"] = bool(policy.get("adaptive", True))
    policy["local_first"] = bool(policy.get("local_first", True))
    policy["local_classifier"] = bool(policy.get("local_classifier", True))
    try:
        policy["confidence_threshold"] = int(policy.get("confidence_threshold", 75))
    except Exception:
        policy["confidence_threshold"] = 75
    return policy


def _ollama_bin() -> Path | None:
    names = ["ollama.exe"] if sys.platform == "win32" else ["ollama-macos", "ollama"]
    for name in names:
        candidate = BAGO_ROOT / "bin" / name
        if candidate.exists():
            return candidate
    found = shutil.which("ollama")
    if found:
        return Path(found)
    if sys.platform == "win32":
        local = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
        if local.exists():
            return local
    return None



def _read_provider_models(provider: str) -> list[str]:
    """Lee modelos desde model_providers.json."""
    providers_file = Path(__file__).parents[2] / "state" / "model_providers.json"
    models: list[str] = []
    if providers_file.exists():
        try:
            data = json.loads(providers_file.read_text(encoding="utf-8"))
            provider_data = data.get("providers", {}).get(provider, {})
            models = list(provider_data.get("models", {}).keys())
        except Exception:
            pass
    return models


def _read_codex_models() -> tuple[list[str], str]:
    """Lee modelos Codex desde provider_registry + config local."""
    models = _read_provider_models("codex")
    if not models:
        # Fallback hardcoded (actualizado 2026-05-14)
        models = [
            "gpt-5.5", "gpt-5.4", "gpt-5.4-mini",
            "gpt-5.3-codex", "gpt-5.2"
        ]

    home = Path.home()
    active = "gpt-5.4"
    config = home / ".codex" / "config.toml"
    if config.exists():
        for line in config.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.strip().startswith("model"):
                active = line.split("=")[-1].strip().strip('"').strip("'")
                break

    cache = home / ".codex" / "models_cache.json"
    if cache.exists():
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            for model in data.get("models", []):
                slug = model.get("slug", "")
                if slug and slug not in models:
                    models.append(slug)
        except Exception:
            pass
    if active in models:
        models.remove(active)
    models.insert(0, active)
    return models or [active], active


def _read_copilot_models() -> list[str]:
    """Modelos disponibles en Copilot CLI — leídos desde provider_registry."""
    models = _read_provider_models("copilot")
    if not models:
        # Fallback hardcoded (actualizado 2026-05-14)
        models = [
            "claude-sonnet-4.6", "claude-opus-4.7",
            "gpt-5.5", "gpt-5.4", "gpt-5.4-mini",
            "gpt-5.3-codex", "gpt-5.2"
        ]
    # Preferencia del usuario desde settings
    settings = Path.home() / ".copilot" / "settings.json"
    if settings.exists():
        try:
            data = json.loads(settings.read_text(encoding="utf-8"))
            preferred = data.get("model") or data.get("defaultModel")
            if preferred and preferred in models:
                models.remove(preferred)
                models.insert(0, preferred)
        except Exception:
            pass
    return models
def load_agent_model(agent_id: str) -> str | None:
    """Devuelve el modelo configurado para un agente BAGO específico.

    Prioridad:
      1. Campo 'model' en agents_registry.json para ese agente.
      2. Clave 'agent_models.<agent_id>' en llm_config.json.
      3. None (el router elegirá el modelo por defecto).
    """
    registry_path = STATE_DIR / "agents_registry.json"
    registry = _read_json(registry_path, {})
    agent = registry.get(agent_id)
    if isinstance(agent, dict) and agent.get("model"):
        return agent["model"]
    cfg = _read_json(CFG_FILE, {})
    return cfg.get("agent_models", {}).get(agent_id)


def _ollama_models(ollama_bin: Path | None) -> list[str]:
    models: list[str] = []
    manifests = OLLAMA_MODELS_DIR / "manifests" / "registry.ollama.ai" / "library"
    if manifests.exists():
        for model_dir in sorted(p for p in manifests.iterdir() if p.is_dir()):
            for tag_file in sorted(p for p in model_dir.iterdir() if p.is_file()):
                models.append(f"{model_dir.name}:{tag_file.name}")
    if not models and ollama_bin:
        try:
            env = dict(os.environ, OLLAMA_MODELS=str(OLLAMA_MODELS_DIR))
            result = subprocess.run(
                [str(ollama_bin), "list"],
                capture_output=True,
                text=True,
                timeout=5,
                env=env,
            )
            for line in result.stdout.strip().splitlines()[1:]:
                if line.strip():
                    models.append(line.split()[0])
        except Exception:
            pass
    preferred = ["qwen2.5-coder:7b", "llama3.2:latest", "llama3.2:3b", "llama3.2:1b"]
    return sorted(models, key=lambda m: next((i for i, p in enumerate(preferred) if m == p), 99))


def detect_agents() -> list[dict]:
    gh = shutil.which("gh")
    copilot_bin = shutil.which("copilot")
    copilot_ok = bool(copilot_bin)
    copilot_reason = None
    if gh:
        try:
            result = subprocess.run(["gh", "copilot", "--version"], capture_output=True, text=True, timeout=4)
            copilot_ok = result.returncode == 0
            if copilot_ok:
                copilot_reason = None
        except subprocess.TimeoutExpired:
            copilot_ok = True
            copilot_reason = None
        except Exception:
            pass
    if not copilot_ok:
        copilot_reason = "copilot CLI no instalado o no encontrado"

    codex = shutil.which("codex")
    codex_models, codex_active = _read_codex_models()
    ollama_bin = _ollama_bin()
    ollama_models = _ollama_models(ollama_bin)
    claude = shutil.which("claude")

    agents = [
        Agent(
            id="copilot",
            name="BAGO Copilot",
            subtitle="GitHub Copilot CLI",
            icon="🤖",
            color="#4f8ef7",
            available=copilot_ok,
            reason=copilot_reason,
            install_url="https://github.com/github/gh-copilot",
            models=_read_copilot_models(),
        ),
        Agent(
            id="codex",
            name="BAGO Codex",
            subtitle=f"OpenAI Codex CLI · activo: {codex_active}",
            icon="⚡",
            color="#7c5ef7",
            available=bool(codex),
            reason=None if codex else "codex no instalado",
            install_url="https://github.com/openai/codex",
            models=codex_models,
            active_model=codex_active,
        ),
        Agent(
            id="ollama",
            name="BAGO Ollama",
            subtitle="Modelos locales (sin internet)",
            icon="◉",
            color="#3ecf8e",
            available=bool(ollama_bin),
            reason=None if ollama_bin else "Ollama no instalado o no encontrado",
            install_url="https://ollama.ai",
            models=ollama_models or (["qwen2.5-coder:7b"] if ollama_bin else []),
        ),
        Agent(
            id="claude",
            name="BAGO Claude",
            subtitle="Anthropic Claude CLI",
            icon="◆",
            color="#f6ad55",
            available=bool(claude),
            reason=None if claude else "Claude CLI no instalado",
            install_url="https://docs.anthropic.com/claude/docs/cli",
            models=["claude-opus-4", "claude-sonnet-4"],
        ),
    ]
    return [agent.as_dict() for agent in agents]


def _count_hits(text: str, keywords: set[str]) -> int:
    return sum(1 for keyword in keywords if keyword in text)


def _agent_model(agent: dict, preferred: str | None = None) -> str | None:
    models = agent.get("models") or []
    if preferred and preferred in models:
        return preferred
    return models[0] if models else preferred


def _available_chain(available: dict, wanted: list[str]) -> list[str]:
    result: list[str] = []
    for agent_id in wanted:
        if agent_id in available and agent_id not in result:
            result.append(agent_id)
    return result


def _signals(task: str) -> dict:
    text = task.lower()
    return {
        "local_hits": _count_hits(text, LOCAL_OK_KEYWORDS),
        "code_hits": _count_hits(text, CODE_ASSIST_KEYWORDS),
        "codex_hits": _count_hits(text, CODEX_KEYWORDS),
        "escalation_hits": _count_hits(text, ESCALATION_KEYWORDS),
        "review_hits": _count_hits(text, REVIEW_KEYWORDS),
        "multifile": any(hint in text for hint in MULTIFILE_HINTS),
        "music_hits": _count_hits(text, MUSIC_KEYWORDS),
    }


def _scores(available: dict, policy: dict, sig: dict) -> dict:
    local_id = policy.get("local_agent", "ollama")
    scores = {agent_id: 0 for agent_id in available}
    for agent_id in scores:
        if agent_id == local_id:
            scores[agent_id] += sig["local_hits"] * 12 + (10 if policy.get("local_first") else 0)
        elif agent_id == "copilot":
            scores[agent_id] += sig["code_hits"] * 12 + sig["review_hits"] * 14 + sig["escalation_hits"] * 5 + sig["music_hits"] * 6
        elif agent_id == "codex":
            scores[agent_id] += sig["codex_hits"] * 14 + sig["escalation_hits"] * 8 + (25 if sig["multifile"] else 0) + sig["music_hits"] * 10
        elif agent_id == "ollama-cloud":
            scores[agent_id] += sig["music_hits"] * 4 + sig["escalation_hits"] * 6
    return scores


def _hard_route(available: dict, policy: dict, sig: dict) -> dict | None:
    local_id = policy.get("local_agent", "ollama")
    scores = _scores(available, policy, sig)

    # Music tasks -> codex for safe file editing
    if sig["music_hits"] >= 1:
        agent_id = "codex" if "codex" in available else ("copilot" if "copilot" in available else None)
        if agent_id:
            agent = available[agent_id]
            route = _select_model_for_task(policy.get("_task", ""))
            model = route["model"] if route and route["model"] in agent.get("models", []) else _agent_model(agent)
            return _decision(
                agent, agent_id, model, "hard_guardrail",
                "Tarea musical detectada (partituras, transposición, arreglos). Se escala a agente con control de archivos.",
                88 if agent_id == "codex" else 75, scores, policy,
                _available_chain(available, [local_id, agent_id]),
            )

    if sig["review_hits"] >= 1:
        agent_id = "copilot" if "copilot" in available else ("codex" if "codex" in available else None)
        if agent_id:
            agent = available[agent_id]
            return _decision(
                agent, agent_id, _agent_model(agent), "hard_guardrail",
                "Revisión/PR/diff detectado; se escala fuera del modelo local.",
                92 if agent_id == "copilot" else 84, scores, policy,
                _available_chain(available, [local_id, agent_id]),
            )

    needs_codex = (
        sig["codex_hits"] >= 1
        or sig["escalation_hits"] >= 2
        or sig["multifile"]
    )
    if needs_codex:
        agent_id = "codex" if "codex" in available else ("copilot" if "copilot" in available else None)
        if agent_id:
            agent = available[agent_id]
            return _decision(
                agent, agent_id, _agent_model(agent), "hard_guardrail",
                "Cambios, ejecución, tests, instalación o multiarchivo requieren agente con control del repo.",
                90 if agent_id == "codex" else 78, scores, policy,
                _available_chain(available, [local_id, agent_id]),
            )
    return None


def _decision(agent: dict, agent_id: str, model: str | None, source: str, reason: str,
              confidence: int, scores: dict, policy: dict, fallback_chain: list[str],
              classifier: dict | None = None) -> dict:
    return {
        "agent": agent_id,
        "agent_name": agent.get("name", agent_id),
        "agent_icon": agent.get("icon", ""),
        "model": model,
        "reason": reason,
        "confidence": confidence,
        "source": source,
        "all_scores": scores,
        "policy": policy,
        "fallback_chain": fallback_chain,
        "classifier": classifier,
    }


def _ollama_server_up(server_url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{server_url.rstrip('/')}/api/tags", timeout=2) as response:
            return 200 <= response.status < 300
    except Exception:
        return False


def _classifier_prompt(task: str, available_ids: list[str]) -> str:
    return (
        "Eres el clasificador local de BAGO. Decide si una tarea debe ir a ollama, codex o copilot.\n"
        "Responde solo JSON valido, sin markdown.\n"
        "Reglas: editar archivos, ejecutar comandos, instalar, tests, deploy o multiarchivo => codex. "
        "PR, diff o revision de codigo => copilot. Explicar, resumir, planear, idear o dudas simples => ollama. "
        "Si no estas seguro, usa codex.\n"
        f"Agentes disponibles: {', '.join(available_ids)}.\n"
        "Formato: {\"agent\":\"ollama|codex|copilot\", \"confidence\":0-100, "
        "\"task_type\":\"explain|plan|edit_files|run_commands|tests|multi_file|pr_review|code_review|unknown\", "
        "\"reason\":\"frase corta\"}\n"
        f"Tarea: {task}"
    )


def _classify_with_ollama(task: str, available: dict, policy: dict) -> dict | None:
    cfg = _read_json(CFG_FILE, {})
    server_url = str(cfg.get("server_url") or os.environ.get("OLLAMA_HOST") or default_ollama_base_url())
    active_model = cfg.get("active_model") or "qwen25-coder"
    model_map = {
        "qwen25-coder": "qwen2.5-coder:7b",
        "phi3-mini": "phi3:mini",
        "llama32-3b": "llama3.2:3b",
        "deepseek-coder": "deepseek-coder:6.7b",
    }
    model = model_map.get(active_model, active_model)
    if not _ollama_server_up(server_url):
        return None

    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": _classifier_prompt(task, sorted(available))}],
        "stream": False,
        "temperature": 0,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{server_url.rstrip('/')}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        timeout = int(policy.get("classifier_timeout_s", 8))
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
        content = data["choices"][0]["message"]["content"].strip()
        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            content = content[start:end + 1]
        parsed = json.loads(content)
        agent = str(parsed.get("agent", "")).lower()
        confidence = int(parsed.get("confidence", 0))
        if agent not in {"ollama", "codex", "copilot"}:
            return None
        parsed["agent"] = agent
        parsed["confidence"] = max(0, min(100, confidence))
        return parsed
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, ValueError):
        return None


def _classifier_route(task: str, available: dict, policy: dict, sig: dict, scores: dict) -> dict | None:
    if not policy.get("local_classifier"):
        return None
    classifier = _classify_with_ollama(task, available, policy)
    if not classifier:
        return None

    threshold = int(policy.get("confidence_threshold", 75))
    chosen = classifier["agent"]
    confidence = int(classifier["confidence"])
    if confidence < threshold or chosen not in available:
        if "codex" in available:
            agent = available["codex"]
            return _decision(
                agent, "codex", _agent_model(agent), "classifier_fallback",
                f"Clasificador local sin confianza suficiente ({confidence}%). Escalo a Codex.",
                max(65, confidence), scores, policy,
                _available_chain(available, [policy.get("local_agent", "ollama"), "codex"]),
                classifier,
            )
        return None

    if chosen == "ollama" and (
        sig["review_hits"] or sig["codex_hits"] or sig["escalation_hits"] >= 2 or sig["multifile"]
    ):
        if "codex" in available:
            agent = available["codex"]
            return _decision(
                agent, "codex", _agent_model(agent), "guardrail_override",
                "El clasificador eligio local, pero los guardarrailes detectaron riesgo operativo.",
                86, scores, policy,
                _available_chain(available, [policy.get("local_agent", "ollama"), "codex"]),
                classifier,
            )

    agent = available[chosen]
    preferred = "qwen2.5-coder:7b" if chosen == policy.get("local_agent", "ollama") else None
    return _decision(
        agent, chosen, _agent_model(agent, preferred), "local_classifier",
        classifier.get("reason") or "Decision del clasificador local.",
        confidence, scores, policy,
        _available_chain(available, [policy.get("local_agent", "ollama"), chosen, "codex", "copilot"]),
        classifier,
    )


def route_task(task: str, agents: list[dict] | None = None, use_classifier: bool | None = None,
               record: bool = False) -> dict:
    agents = agents or detect_agents()
    available = {agent["id"]: agent for agent in agents if agent.get("available")}
    policy = load_policy()
    policy["_task"] = task
    if use_classifier is not None:
        policy["local_classifier"] = use_classifier

    if not available:
        result = {"agent": None, "reason": "Ningun agente disponible", "confidence": 0, "policy": policy}
        if record:
            record_decision(task, result)
        return result

    sig = _signals(task)
    scores = _scores(available, policy, sig)

    hard = _hard_route(available, policy, sig)
    if hard:
        result = hard
    else:
        result = _classifier_route(task, available, policy, sig, scores)
        if not result:
            result = _fallback_route(available, policy, sig, scores)

    if record:
        record_decision(task, result)
    return result


def _fallback_route(available: dict, policy: dict, sig: dict, scores: dict) -> dict:
    local_id = policy.get("local_agent", "ollama")
    force_cloud = sig["music_hits"] >= 1 or sig["review_hits"] >= 1 or sig["codex_hits"] >= 1 or sig["escalation_hits"] >= 1 or sig["code_hits"] >= 1

    if not force_cloud and local_id in available and policy.get("local_first"):
        agent = available[local_id]
        return _decision(
            agent, local_id, _agent_model(agent, "qwen2.5-coder:7b"), "rules_fallback",
            "Tarea de bajo riesgo o ambigua; BAGO usa local primero.",
            82 if sig["local_hits"] else 68, scores, policy,
            _available_chain(available, [local_id, "codex", "copilot"]),
        )
    best_id = max(scores, key=scores.get) if any(scores.values()) else next(iter(available))
    agent = available[best_id]
    return _decision(
        agent, best_id, _agent_model(agent), "rules_fallback",
        "Mejor agente disponible por reglas deterministas." + (" (override local por tarea especializada)" if force_cloud else ""),
        75 if force_cloud else 60, scores, policy, [best_id],
    )


def record_decision(task: str, decision: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "task": task,
        "agent": decision.get("agent"),
        "model": decision.get("model"),
        "confidence": decision.get("confidence"),
        "source": decision.get("source"),
        "reason": decision.get("reason"),
        "fallback_chain": decision.get("fallback_chain", []),
    }
    with HISTORY_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def print_decision(task: str, decision: dict) -> None:
    policy = decision.get("policy") or {}
    print()
    print("  BAGO Agent Router")
    print("  " + "-" * 46)
    print(f"  Politica : {policy.get('mode', '?')}/{'adaptive' if policy.get('adaptive') else 'static'}")
    print(f"  Tarea    : {task}")
    if not decision.get("agent"):
        print(f"  Decision : ninguno")
        print(f"  Motivo   : {decision.get('reason', '-')}")
        print()
        return
    print(f"  Decision : {decision.get('agent')}  ({decision.get('agent_name')})")
    print(f"  Modelo   : {decision.get('model') or '-'}")
    print(f"  Confianza: {decision.get('confidence')}%")
    print(f"  Fuente   : {decision.get('source')}")
    print(f"  Motivo   : {decision.get('reason')}")
    chain = decision.get("fallback_chain") or []
    if chain:
        print(f"  Fallback : {' -> '.join(chain)}")
    print()


def _history(limit: int) -> None:
    if not HISTORY_FILE.exists():
        print("  Sin historial de routing.")
        return
    lines = HISTORY_FILE.read_text(encoding="utf-8").splitlines()[-limit:]
    for line in lines:
        try:
            entry = json.loads(line)
        except Exception:
            continue
        print(f"  {entry.get('ts')}  {entry.get('agent'):<7} {entry.get('confidence')}%  {entry.get('task')}")


def _run_tests() -> int:
    agents = [
        {"id": "ollama", "name": "BAGO Ollama", "icon": "local", "available": True, "models": ["qwen2.5-coder:7b"]},
        {"id": "codex", "name": "BAGO Codex", "icon": "codex", "available": True, "models": ["gpt-5.5"]},
        {"id": "copilot", "name": "BAGO Copilot", "icon": "copilot", "available": True, "models": ["gpt-4.1"]},
    ]
    cases = [
        ("explicame este error de python", "ollama"),
        ("implementa login en varios archivos y ejecuta tests", "codex"),
        ("revisa este PR y dime riesgos", "copilot"),
        ("brainstorm de ideas offline", "ollama"),
    ]
    failures: list[str] = []
    for task, expected in cases:
        got = route_task(task, agents=agents, use_classifier=False)["agent"]
        ok = got == expected
        print(f"  {'OK' if ok else 'KO'} {task!r}: {got} (esperado {expected})")
        if not ok:
            failures.append(f"{task}: {got} != {expected}")
    print(f"\n  {len(cases) - len(failures)}/{len(cases)} tests pasaron")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Router hibrido local/Codex/Copilot para BAGO")
    parser.add_argument("task", nargs="*", help="Tarea a clasificar")
    parser.add_argument("--json", action="store_true", help="Imprime JSON")
    parser.add_argument("--no-classifier", action="store_true", help="No consulta al modelo local clasificador")
    parser.add_argument("--history", action="store_true", help="Muestra historial")
    parser.add_argument("--limit", type=int, default=10, help="Limite de historial")
    parser.add_argument("--test", action="store_true", help="Self-test")
    args = parser.parse_args()

    if args.test:
        return _run_tests()
    if args.history:
        _history(args.limit)
        return 0

    task = " ".join(args.task).strip()
    if not task:
        print("  Uso: bago route \"describe tu tarea\"")
        return 1

    decision = route_task(task, use_classifier=not args.no_classifier, record=True)
    if args.json:
        print(json.dumps(decision, ensure_ascii=False, indent=2))
    else:
        print_decision(task, decision)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

