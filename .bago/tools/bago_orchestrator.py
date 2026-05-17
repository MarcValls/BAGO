#!/usr/bin/env python3
"""bago_orchestrator.py — Selecciona modelo óptimo según tarea, disponibilidad y coste.

Integra:
  - model_providers.json    (catálogo de modelos)
  - model_orchestrator.json (política de selección)
  - model_routing.json      (reglas por keyword)
  - Detección de health de proveedores

Uso:
  python bago_orchestrator.py [--mode offline|economico|estandar|full] [tarea]
"""
from __future__ import annotations

import argparse
import os
import json
import subprocess
import sys
from pathlib import Path

STATE_DIR = Path(__file__).resolve().parents[1] / "state"

# === Router dinámico integrado ===
_router_path = Path(__file__).parent / "bago_dynamic_router.py"
_dynamic_route = None
if _router_path.exists():
    import importlib.util
    _spec = importlib.util.spec_from_file_location("bago_dynamic_router", _router_path)
    _router_mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_router_mod)
    _dynamic_route = _router_mod.dynamic_route
# ==================================


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _detect_codex_env() -> dict:
    """Detecta si estamos ejecutando dentro de Codex CLI."""
    env = {
        "in_codex": False,
        "in_copilot": False,
        "codex_model": None,
        "codex_config": None,
    }
    # Detectar Codex CLI
    codex_config = Path.home() / ".codex" / "config.toml"
    if codex_config.exists():
        env["in_codex"] = True
        env["codex_config"] = str(codex_config)
        # Leer modelo activo
        try:
            for line in codex_config.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("model"):
                    env["codex_model"] = line.split("=")[-1].strip().strip('"').strip("'")
                    break
        except Exception:
            pass
    # Detectar Copilot CLI
    copilot_settings = Path.home() / ".copilot" / "settings.json"
    if copilot_settings.exists():
        env["in_copilot"] = True
    return env


def _check_provider(name: str, cmd: str = "") -> bool:
    """Ejecuta health check robusto de un proveedor."""
    try:
        if name == "ollama-local":
            # Verificar que ollama responde y tiene modelos
            r = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
            if r.returncode == 0 and r.stdout.strip():
                return True
            # Fallback: probar curl al endpoint
            r2 = subprocess.run("curl -s http://127.0.0.1:11434/api/tags".split(), capture_output=True, timeout=3)
            return r2.returncode == 0 and b"models" in r2.stdout

        elif name == "ollama-cloud":
            # Verificar conexión a API Ollama cloud
            r = subprocess.run("curl -s https://api.ollama.com/v1/models".split(), capture_output=True, timeout=5)
            return r.returncode == 0 and (b"models" in r.stdout or b"data" in r.stdout)

        elif name == "copilot":
            # Verificar gh copilot
            r = subprocess.run("gh copilot --version".split(), capture_output=True, timeout=5)
            if r.returncode == 0:
                return True
            # Fallback: verificar gh auth
            r2 = subprocess.run("gh auth status".split(), capture_output=True, timeout=5)
            return r2.returncode == 0 and b"Logged in" in r2.stdout

        elif name == "codex":
            # Verificar codex CLI
            r = subprocess.run("codex --version".split(), capture_output=True, timeout=5)
            if r.returncode == 0:
                return True
            # Fallback: verificar config de codex
            codex_config = Path.home() / ".codex" / "config.toml"
            return codex_config.exists()

        elif name == "openclaw":
            r = subprocess.run("openclaw --version".split(), capture_output=True, timeout=3)
            return r.returncode == 0

        else:
            if cmd:
                r = subprocess.run(cmd.split(), capture_output=True, timeout=5)
                return r.returncode == 0
            return False
    except Exception:
        return False


def _list_ollama_models() -> list[str]:
    """Lista modelos disponibles en Ollama local."""
    try:
        r = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
        if r.returncode != 0:
            return []
        models = []
        for line in r.stdout.strip().split("\n")[1:]:  # Skip header
            parts = line.split()
            if parts:
                models.append(parts[0])
        return models
    except Exception:
        return []


def _detect_chain() -> dict:
    """Detecta la cadena de acceso: Codex -> Copilot -> Ollama -> Cloud."""
    chain = {
        "codex": False,
        "copilot": False,
        "ollama_local": False,
        "ollama_cloud": False,
        "chain_access": [],
    }

    # Paso 1: ¿Estamos en Codex CLI?
    codex_config = Path.home() / ".codex" / "config.toml"
    chain["codex"] = codex_config.exists()

    # Paso 2: ¿Tenemos Copilot?
    try:
        r = subprocess.run("gh copilot --version".split(), capture_output=True, timeout=3)
        chain["copilot"] = r.returncode == 0
    except Exception:
        pass

    # Paso 3: ¿Ollama local?
    try:
        r = subprocess.run(["ollama", "list"], capture_output=True, timeout=3)
        chain["ollama_local"] = r.returncode == 0
    except Exception:
        pass

    # Paso 4: ¿Ollama cloud? (requiere API key)
    ollama_key = os.environ.get("OLLAMA_API_KEY")
    chain["ollama_cloud"] = bool(ollama_key)

    # Construir cadena de acceso
    access = []
    if chain["codex"]:
        access.append("codex")
    if chain["copilot"]:
        access.append("copilot")
    if chain["ollama_local"]:
        access.append("ollama-local")
    if chain["ollama_cloud"]:
        access.append("ollama-cloud")
    chain["chain_access"] = access

    return chain


def detect_providers(providers: dict, health_checks: dict) -> dict:
    """Detecta que proveedores estan disponibles via health checks + cadena."""
    available = {}
    chain = _detect_chain()
    env = _detect_codex_env()

    # Health checks robustos
    for name, cmd in health_checks.items():
        available[name] = _check_provider(name, cmd)

    # Si estamos en Codex CLI, codex siempre esta disponible
    if env["in_codex"]:
        available["codex"] = True

    # Si tenemos Ollama local, listar modelos disponibles
    if available.get("ollama-local", False):
        ollama_models = _list_ollama_models()
        if not ollama_models:
            available["ollama-local"] = False  # Ollama corriendo pero sin modelos

    # Cadena de acceso: desde Codex podemos acceder a todo
    if chain["codex"] and chain["copilot"]:
        # Tenemos acceso a GitHub Copilot desde Codex
        available["copilot"] = True

    # Log de cadena
    if chain["chain_access"]:
        print(f"  Cadena de acceso: {' -> '.join(chain['chain_access'])}")

    return available


def select_mode(auto_rules: list, providers_available: dict, args_mode: str | None) -> str:
    """Selecciona modo: explícito o automático."""
    if args_mode:
        return args_mode
    # Auto-detect
    ollama_local = providers_available.get("ollama-local", False)
    ollama_cloud = providers_available.get("ollama-cloud", False)
    copilot = providers_available.get("copilot", False)
    codex = providers_available.get("codex", False)
    internet = ollama_cloud or copilot or codex

    if ollama_local and not internet:
        return "offline"
    if ollama_local and internet and not codex:
        return "economico"
    if ollama_local and internet and codex:
        return "estandar"
    if all([ollama_local, ollama_cloud, copilot, codex]):
        return "full"
    return "offline"  # fallback seguro


def get_available_models() -> list[dict]:
    """Devuelve lista de modelos realmente disponibles."""
    health_script = Path(__file__).parent / "bago_health_check.py"
    if not health_script.exists():
        return []
    import importlib.util
    spec = importlib.util.spec_from_file_location("bago_health_check", health_script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    health = mod.full_health_check()

    models = []
    for provider, status in health.items():
        if not status["available"]:
            continue
        for m in status.get("models", []):
            models.append({
                "name": m["name"],
                "provider": provider,
                "active": m.get("active", False),
                "size": m.get("size", ""),
            })
    return models


def orchestrate(task: str, mode_name: str | None = None) -> dict:
    """Orquestador principal: selecciona modelo óptimo."""
    providers_data = _read_json(STATE_DIR / "model_providers.json")
    orchestrator = _read_json(STATE_DIR / "model_orchestrator.json")
    routing = _read_json(STATE_DIR / "model_routing.json")

    modes = orchestrator.get("modes", {})
    health_checks = orchestrator.get("health_checks", {})
    task_prefs = orchestrator.get("task_preference", {})
    auto_rules = orchestrator.get("auto_mode_selection", {}).get("rules", [])

    # 1. Detectar proveedores disponibles
    providers_available = detect_providers(providers_data.get("providers", {}), health_checks)

    # 2. Seleccionar modo
    mode = select_mode(auto_rules, providers_available, mode_name)
    mode_config = modes.get(mode, modes.get("offline", {}))

    # 0. Consultar router dinámico primero (reglas explícitas de model_routing.json)
    router_model = None
    router_provider = None
    router_reason = None
    if _dynamic_route:
        try:
            agents_for_router = []
            for p_name, p_avail in providers_available.items():
                if p_avail:
                    p_models = []
                    p_data = providers_data.get("providers", {}).get(p_name, {})
                    for m_name in p_data.get("models", {}).keys():
                        p_models.append(m_name)
                    agent_id = p_name.replace("ollama-local", "ollama").replace("ollama-cloud", "ollama-cloud")
                    agents_for_router.append({"id": agent_id, "available": True, "models": p_models})
            route = _dynamic_route(task, agents_for_router)
            if route.get("confidence", 0) >= 85 and route.get("rule_id") != "fallback":
                router_model = route.get("model")
                router_provider = route.get("provider")
                router_reason = route.get("reason")
        except Exception:
            pass

    # 3. Encontrar regla de routing por tarea (mejor coincidencia)
    text = task.lower()
    route = None
    best_hits = 0
    for rule in routing.get("rules", []):
        hits = sum(1 for kw in rule.get("keywords", []) if kw.lower() in text)
        if hits > best_hits:
            best_hits = hits
            route = rule

    # 4. Encontrar preferencia de tarea
    task_type = None
    for pref_name, pref in task_prefs.items():
        if any(kw in text for kw in pref.get("keywords", [])):
            task_type = pref_name
            break
    if not task_type and route:
        task_type = route.get("id", "")

    # 5. Filtrar modelos por modo (allowed_providers)
    allowed = set(mode_config.get("allowed_providers", []))
    candidates = []

    # Obtener modelos reales de Ollama si esta disponible
    ollama_real_models = _list_ollama_models() if providers_available.get("ollama-local") else []

    for prov_name, prov in providers_data.get("providers", {}).items():
        if prov_name not in allowed:
            continue
        if not providers_available.get(prov_name, False):
            continue
        for model_name, model in prov.get("models", {}).items():
            wire_name = model.get("wire_name", model_name)
            # Para Ollama local, verificar que el modelo realmente esta descargado
            if prov_name == "ollama-local":
                found = False
                wire_base = wire_name.split(":")[0]  # qwen2.5-coder
                for m in ollama_real_models:
                    m_base = m.split(":")[0]  # qwen2.5
                    # Coincidencia exacta
                    if wire_name == m:
                        found = True
                        break
                    # Coincidencia por familia solo si comparten nombre base principal
                    # qwen2.5-coder debe coincidir con qwen2.5-coder, NO con qwen2.5
                    if wire_base == m_base:
                        found = True
                        break
                if not found:
                    continue  # Modelo no descargado en Ollama
            candidates.append({
                "name": model_name,
                "provider": prov_name,
                "wire_name": wire_name,
                "cost": model.get("cost", "unknown"),
                "best_for": model.get("best_for", ""),
                "tokens": model.get("max_prompt_tokens", 0),
                "size_mb": model.get("size_mb", 0),
            })

    # 6. Scorear candidatos
    def score(c):
        s = 0
        env = _detect_codex_env()

        # Coste: menor es mejor (peso reducido para no dominar todo)
        cost_order = {"free": 0, "included": 1, "subscription": 2, "openai_credits": 3}
        s += (3 - cost_order.get(c["cost"], 3)) * 6

        # Preferencia de tarea
        if task_type and c["name"] in task_prefs.get(task_type, {}).get("models", []):
            s += 15

        # Clasificar tarea
        complex_tasks = ["code_complex", "code_frontier", "review_deep", "music_edit", "long_context", "music_analysis", "code_edits", "review_complex", "music_long_context"]
        simple_tasks = ["code_fast", "brainstorm", "music_render", "brainstorm_offline", "music_render_preview"]

        if env["in_codex"]:
            # En Codex CLI: tareas SIMPLES -> Ollama local gratis obligatorio
            if task_type in simple_tasks:
                if c["provider"] == "ollama-local" and c["cost"] == "free":
                    s += 80  # Inmenso bonus: ahorrar créditos para simples
                if c["provider"] == "codex":
                    s -= 30  # Penalizar Codex para simples

            # En Codex CLI: tareas COMPLEJAS -> Codex, el MÁS BARATO adecuado
            if task_type in complex_tasks:
                if c["provider"] == "codex":
                    s += 20
                    # Preferir gpt-5.4 o gpt-5.3-codex sobre gpt-5.5
                    if c["name"] == "gpt-5.4":
                        s += 15
                    if c["name"] == "gpt-5.3-codex":
                        s += 12
                    if c["name"] == "gpt-5.4-mini":
                        s += 8
                    if c["name"] == "gpt-5.5":
                        s -= 8   # Penalizar frontier innecesariamente
                if c["provider"] == "ollama-local":
                    s -= 30  # Penalizar local para complejas

        else:
            # Fuera de Codex: LOCAL FIRST — priorizar local salvo tarea compleja
            if c["provider"] == "ollama-local":
                s += 50   # bonus base: siempre intentar local primero
            if c["provider"] in ("codex", "copilot", "anthropic") and task_type not in complex_tasks:
                s -= 25   # penalizar cloud para tareas que no lo requieren
            if task_type in complex_tasks:
                if c["provider"] == "ollama-local" and (c["size_mb"] < 1000 or "mini" in c["name"]):
                    s -= 20  # modelos locales pequeños no aptos para complejo
                if c["provider"] in ("codex", "copilot"):
                    s += 20  # cloud necesario para complejo: revertir penalización
                if "mini" in c["name"] and c["provider"] != "ollama-local":
                    s -= 15
                else:
                    s += 10
            if task_type in simple_tasks:
                if c["provider"] == "ollama-local":
                    s += 15   # local + tarea simple = máxima preferencia
                if "mini" in c["name"] or c["size_mb"] < 1000:
                    s += 10
        return s

    candidates.sort(key=score, reverse=True)

    if not candidates:
        return {
            "error": f"No hay modelos disponibles para el modo '{mode}'",
            "mode": mode,
            "providers_available": providers_available,
        }

    best = candidates[0]
    # Si el router dinámico dio un modelo específico con alta confianza, forzarlo si está disponible
    if router_model:
        for c in candidates:
            if c["name"] == router_model and (not router_provider or c["provider"] == router_provider):
                best = c
                break
        else:
            for c in candidates:
                if c["name"] == router_model:
                    best = c
                    break

    reason = f"Modo: {mode}. Mejor score por coste y disponibilidad."
    if router_reason and router_model:
        reason = f"Router dinámico: {router_reason}"
    elif task_type:
        reason += f" Tarea: {task_type}"

    return {
        "task": task,
        "mode": mode,
        "model": best["name"],
        "provider": best["provider"],
        "wire_name": best["wire_name"],
        "cost": best["cost"],
        "reason": reason,
        "alternatives": [c["name"] for c in candidates[1:4]],
        "providers_available": providers_available,
        "candidates_count": len(candidates),
    }


def print_orchestration(task: str, mode: str | None = None) -> None:
    result = orchestrate(task, mode)
    if "error" in result:
        print(f"\n  ERROR {result['error']}")
        print(f"     Proveedores: {result['providers_available']}")
        return

    env = _detect_codex_env()
    print(f"\n  BAGO Orchestrator")
    if env["in_codex"]:
        print(f"  Entorno:    Codex CLI (modelo activo: {env.get('codex_model', 'desconocido')})")
    if env["in_copilot"]:
        print(f"  Entorno:    Copilot CLI detectado")
    print(f"  {'-'*46}")
    print(f"  Tarea:      {result['task']}")
    print(f"  Modo:       {result['mode']}")
    print(f"  Agente:     {result['provider']}")
    print(f"  Modelo:     {result['model']}")
    print(f"  Wire:       {result['wire_name']}")
    print(f"  Coste:      {result['cost']}")
    print(f"  Razón:      {result['reason']}")
    if result['alternatives']:
        print(f"  Alternativas: {', '.join(result['alternatives'])}")
    print(f"  Candidatos: {result['candidates_count']}")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BAGO Model Orchestrator")
    parser.add_argument("task", nargs="?", default="transponer partitura", help="Tarea a orquestar")
    parser.add_argument("--mode", choices=["offline", "economico", "estandar", "full"], help="Forzar modo")
    parser.add_argument("--check", action="store_true", help="Solo ver disponibilidad")
    args = parser.parse_args()

    if args.check:
        providers_data = _read_json(STATE_DIR / "model_providers.json")
        orchestrator = _read_json(STATE_DIR / "model_orchestrator.json")
        health = detect_providers(providers_data.get("providers", {}), orchestrator.get("health_checks", {}))
        print("\n  Disponibilidad de proveedores:")
        for name, ok in health.items():
            icon = "OK" if ok else "NO"
            print(f"    {icon} {name}")
        print()
    else:
        print_orchestration(args.task, args.mode)





