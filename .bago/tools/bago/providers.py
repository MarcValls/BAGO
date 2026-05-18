
import json
import os
from pathlib import Path

from .constants import PROVIDERS_FILE, ROUTING_FILE

def load_providers():
    try:   return json.loads(PROVIDERS_FILE.read_text(encoding="utf-8-sig"))["providers"]
    except: return {}

def load_routing():
    try:   return json.loads(ROUTING_FILE.read_text(encoding="utf-8-sig"))
    except: return {"rules": [], "fallback": {"provider": "codex", "model": "gpt-5.4"}}

# ── Routing & strategy ─────────────────────────────────────────────────────────
def route_by_task(task, routing, providers, current_provider=None):
    """Count-based routing: picks the rule with most keyword hits (same logic as bago_orchestrator).
    LOCAL FIRST: si no hay ninguna regla que coincida y ya estamos en local, no cambiar.
    """
    tl = task.lower()
    best_rule = None
    best_hits = 0
    best_kw = None
    for rule in routing.get("rules", []):
        hits = sum(1 for kw in rule.get("keywords", []) if kw.lower() in tl)
        if hits > best_hits:
            best_hits = hits
            best_rule = rule
            best_kw = next((kw for kw in rule.get("keywords", []) if kw.lower() in tl), None)
    if best_rule:
        prov  = best_rule["provider"]
        model = best_rule["model"]
        wire  = providers.get(prov, {}).get("models", {}).get(model, {}).get("wire_name", model)
        return model, wire, prov, best_kw
    # LOCAL FIRST: sin regla coincidente → quedarse en local si ya estamos ahí
    if current_provider in ("ollama-local", "ollama-cloud"):
        mods = providers.get(current_provider, {}).get("models", {})
        if mods:
            first = next(iter(mods))
            wire = mods[first].get("wire_name", first)
            return first, wire, current_provider, None
    # Fallback de config (debe apuntar a local por defecto)
    fb = routing.get("fallback", {"provider": "ollama-local", "model": "qwen25-mini"})
    return fb.get("model", "qwen25-mini"), fb.get("model", "qwen25-mini"), fb.get("provider", "ollama-local"), None

def detect_strategy(text, active_providers):
    """
    Decide automaticamente la estrategia optima para una peticion.
    Retorna: ("single"|"chain"|"ensemble", [provider_list])
    single    — una sola llamada al mejor modelo
    chain     — pipeline: primer modelo genera, siguiente refina/revisa
    ensemble  — paralelo: varios modelos responden, el activo sintetiza
    """
    if len(active_providers) < 2:
        return "single", []

    tl = text.lower()

    # Senales de cadena: creacion + revision en la misma peticion
    creates  = any(w in tl for w in ["escrib","crea","genera","implementa","construye",
                                      "diseña","haz ","build","write","create","code","codigo"])
    reviews  = any(w in tl for w in ["explica","comenta","documenta","revisa","mejora",
                                      "optimiza","explain","review","improve","refactor",
                                      "y luego","despues","tras","then"])
    code_ctx = any(w in tl for w in ["codigo","code","funcion","function","clase","class",
                                      "script","api","test","algoritmo","algorithm"])

    # Senales de ensemble: opinion, comparacion, perspectivas multiples
    opinions = any(w in tl for w in ["mejor forma","mejor manera","best way","recomiend",
                                      "que opinas","opinion","pros y contras","ventajas",
                                      "desventajas","compara","versus"," vs ","alternativa",
                                      "cual es mejor","debate","perspectiva","enfoque"])

    if creates and (reviews or (code_ctx and reviews)):
        return "chain", active_providers[:2]

    if opinions:
        return "ensemble", active_providers[:min(3, len(active_providers))]

    # Peticion larga y compleja: chain por defecto
    if len(text) > 300 and creates:
        return "chain", active_providers[:2]

    return "single", []

def get_default_model(provider_name, providers):
    prov   = providers.get(provider_name, {})
    models = prov.get("models", {})
    if not models: return "", "", provider_name
    k = next(iter(models))
    return k, models[k].get("wire_name", k), provider_name

def best_model_for_provider(prov_name, providers):
    """Primer modelo del provider o None."""
    name, wire, prov = get_default_model(prov_name, providers)
    return (name, wire, prov) if name else None

# Modelos Claude no disponibles en GitHub Models → se redirigen a gpt-4o
_COPILOT_MODEL_MAP = {
    "claude-sonnet-4.6": "gpt-4o",
    "claude-sonnet-4.5": "gpt-4o",
    "claude-opus-4.7":   "gpt-4o",
    "claude-opus-4.5":   "gpt-4o",
    "claude-3-5-sonnet": "gpt-4o",
    "claude-3-opus":     "gpt-4o",
    "claude-3-haiku":    "gpt-4o-mini",
}

# Modelos ficticios de BAGO → nombres reales de OpenAI
_CODEX_MODEL_MAP = {
    "gpt-5.5":       "gpt-4o",
    "gpt-5.4":       "gpt-4o",
    "gpt-5.3-codex": "gpt-4o",
    "gpt-5.3":       "gpt-4o",
    "gpt-5.2-codex": "gpt-4o",
    "gpt-5.2":       "gpt-4o-mini",
    "gpt-5.4-mini":  "gpt-4o-mini",
    "gpt-5-mini":    "gpt-4o-mini",
    "gpt-5.1":       "gpt-4o-mini",
}

# ── LiteLLM resolver ───────────────────────────────────────────────────────────
def _codex_access_token():
    """Lee el access_token OAuth de ~/.codex/auth.json (ChatGPT Plus, sin API key)."""
    try:
        auth_file = Path.home() / ".codex" / "auth.json"
        if auth_file.exists():
            data = json.loads(auth_file.read_text())
            # Estructura: {"tokens": {"access_token": "..."}}
            tok = (data.get("tokens") or {}).get("access_token") or data.get("access_token")
            if tok:
                return tok
    except Exception:
        pass
    return None

# ── LiteLLM resolver ───────────────────────────────────────────────────────────
def resolve_litellm(provider, wire_name):
    if provider in ("ollama-local", "ollama-cloud"):
        return f"ollama/{wire_name}", {"api_base": "http://127.0.0.1:11434"}
    if provider == "copilot":
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN", "")
        if token:
            # GitHub Models no soporta Claude: redirigir al equivalente disponible
            mapped = _COPILOT_MODEL_MAP.get(wire_name, wire_name)
            return f"openai/{mapped}", {
                "api_base": "https://models.inference.ai.azure.com",
                "api_key": token,
            }
        return wire_name, {}
    if provider in ("codex", "openai"):
        # Prioridad 1: API key explícita
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if api_key:
            return wire_name, {"api_key": api_key}
        # Prioridad 2: OAuth token de Codex CLI (ChatGPT Plus, sin API key)
        codex_token = _codex_access_token()
        if codex_token:
            return wire_name, {"api_key": codex_token}
        # Prioridad 3: fallback a GitHub Models (copilot) si hay GH token
        gh_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN", "")
        if gh_token:
            safe = "gpt-4o-mini" if "mini" in wire_name else "gpt-4o"
            return f"openai/{safe}", {
                "api_base": "https://models.inference.ai.azure.com",
                "api_key": gh_token,
            }
        return wire_name, {}
    return wire_name, {}



def auto_detect_provider(creds, providers):
    active = creds.active_bago_providers()
    # LOCAL FIRST: preferir ollama-local si está disponible, luego cloud copilot/codex
    for preferred in ("ollama-local", "copilot", "codex", "anthropic", "ollama-cloud"):
        if preferred in active and preferred in providers:
            return preferred
    return next((name for name in providers if name in active), next(iter(providers), "ollama-local"))


# ── Ollama probe & pull ────────────────────────────────────────────────────────

def ollama_probe(base_url: str = "http://127.0.0.1:11434") -> dict:
    """Comprueba si Ollama está activo y qué modelos tiene instalados.

    Returns:
        {
          "running":  bool,
          "url":      str,
          "models":   [str, ...],   # nombres de modelos disponibles
          "error":    str | None,   # mensaje de error si no corre
        }
    """
    import urllib.request
    import urllib.error
    try:
        with urllib.request.urlopen(f"{base_url}/api/tags", timeout=3) as r:
            data = json.loads(r.read())
        models = [m["name"] for m in data.get("models", [])]
        return {"running": True, "url": base_url, "models": models, "error": None}
    except urllib.error.URLError as e:
        return {"running": False, "url": base_url, "models": [], "error": str(e.reason)}
    except Exception as e:
        return {"running": False, "url": base_url, "models": [], "error": str(e)}


def ollama_pull(model_name: str, base_url: str = "http://127.0.0.1:11434") -> bool:
    """Descarga un modelo con `ollama pull`. Muestra progreso en consola.

    Returns True si tuvo éxito, False si falló.
    """
    import subprocess, shutil
    cli = shutil.which("ollama")
    if not cli:
        # Intentar via API directamente si no hay CLI
        return _ollama_pull_api(model_name, base_url)

    try:
        proc = subprocess.Popen(
            [cli, "pull", model_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
        )
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                print(f"  {line}", flush=True)
        proc.wait()
        return proc.returncode == 0
    except Exception as e:
        print(f"  ❌ Error ejecutando ollama pull: {e}")
        return False


def _ollama_pull_api(model_name: str, base_url: str) -> bool:
    """Fallback: llama a POST /api/pull cuando el CLI de Ollama no está en PATH."""
    import urllib.request
    import json as _json
    payload = _json.dumps({"name": model_name, "stream": True}).encode()
    req = urllib.request.Request(
        f"{base_url}/api/pull",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            for raw_line in r:
                if not raw_line.strip():
                    continue
                try:
                    chunk = _json.loads(raw_line)
                    status = chunk.get("status", "")
                    if status:
                        print(f"  {status}", flush=True)
                    if chunk.get("error"):
                        print(f"  ❌ {chunk['error']}")
                        return False
                except Exception:
                    pass
        return True
    except Exception as e:
        print(f"  ❌ API pull error: {e}")
        return False


# ── Ollama discovery ───────────────────────────────────────────────────────────

def discover_ollama_url(timeout: int = 2) -> "str | None":
    """Busca Ollama en el PC probando múltiples ubicaciones y puertos.

    Orden de búsqueda:
      1. Variable de entorno OLLAMA_HOST
      2. Puerto por defecto localhost:11434
      3. Puertos alternativos comunes
      4. (Windows) LOCALAPPDATA\\Programs\\Ollama — si el ejecutable existe pero
         el servicio no responde, se intenta arrancarlo brevemente

    Devuelve la URL base funcional o None si no se encuentra.
    """
    import shutil, sys

    candidates: list[str] = []

    # 1. Variable de entorno
    host_env = os.environ.get("OLLAMA_HOST", "").strip()
    if host_env:
        candidates.append(host_env if host_env.startswith("http") else f"http://{host_env}")

    # 2. Puerto por defecto
    candidates += [
        "http://127.0.0.1:11434",
        "http://localhost:11434",
    ]

    # 3. Puertos alternativos
    candidates += [
        "http://127.0.0.1:11435",
        "http://127.0.0.1:8080",
    ]

    # Probar en orden (deduplicado)
    seen: set = set()
    for url in candidates:
        if url in seen:
            continue
        seen.add(url)
        result = ollama_probe(url)
        if result["running"]:
            # Guardar URL descubierta en env para uso posterior
            os.environ["OLLAMA_HOST"] = url
            return url

    # 4. (Windows) Si el ejecutable existe pero no responde, intentar arrancarlo
    if sys.platform == "win32":
        _try_start_ollama_windows()
        # Volver a probar la URL por defecto tras arranque
        for url in ["http://127.0.0.1:11434", "http://localhost:11434"]:
            result = ollama_probe(url)
            if result["running"]:
                os.environ["OLLAMA_HOST"] = url
                return url

    return None


def _try_start_ollama_windows():
    """Intenta arrancar el servidor Ollama en Windows si el exe existe."""
    import subprocess, shutil, time

    # Localizar ollama.exe
    cli = shutil.which("ollama")
    if not cli:
        # Buscar en ubicaciones conocidas de Windows
        localapp = os.environ.get("LOCALAPPDATA", "")
        candidates_win = [
            os.path.join(localapp, "Programs", "Ollama", "ollama.exe"),
            os.path.join(localapp, "ollama", "ollama.exe"),
            r"C:\Program Files\Ollama\ollama.exe",
        ]
        for p in candidates_win:
            if os.path.isfile(p):
                cli = p
                break

    if not cli:
        return

    try:
        subprocess.Popen(
            [cli, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=0x00000008,   # DETACHED_PROCESS en Windows
        )
        time.sleep(2)  # dar tiempo a que arranque
    except Exception:
        pass


# ── Provider health scan ───────────────────────────────────────────────────────

def scan_provider_health(creds, providers: dict, timeout: int = 3) -> dict:
    """Verifica la disponibilidad real de cada provider registrado.

    Realiza chequeos en paralelo con un timeout corto. Para providers cloud
    (copilot, codex, anthropic) comprueba credenciales + un ping HTTP ligero.
    Para Ollama ejecuta discover_ollama_url() y ollama_probe().

    Devuelve:
        {
          "provider_name": {
            "ok":      bool,
            "detail":  str,         # descripción del estado
            "models":  [str, ...],  # solo para Ollama
          },
          ...
        }
    """
    import concurrent.futures, urllib.request, urllib.error

    results: dict = {}

    def _check_ollama():
        url = discover_ollama_url(timeout=timeout)
        if url:
            probe = ollama_probe(url)
            n = len(probe["models"])
            detail = f"{url} — {n} modelos" if n else f"{url} — sin modelos instalados"
            return {"ok": True, "detail": detail, "models": probe["models"], "url": url}
        return {"ok": False, "detail": "no encontrado en ninguna ubicación", "models": [], "url": None}

    def _check_copilot():
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN", "")
        if not token:
            return {"ok": False, "detail": "sin GITHUB_TOKEN"}
        try:
            req = urllib.request.Request(
                "https://api.github.com/user",
                headers={"Authorization": f"token {token}", "User-Agent": "BAGO-CLI"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read())
                login = data.get("login", "?")
                return {"ok": True, "detail": f"@{login}"}
        except urllib.error.HTTPError as e:
            if e.code == 401:
                return {"ok": False, "detail": "token inválido (401)"}
            return {"ok": True, "detail": f"HTTP {e.code}"}
        except Exception as e:
            return {"ok": False, "detail": str(e)[:60]}

    def _check_codex():
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            # Verificar auth codex CLI
            codex_dir = Path.home() / ".codex"
            if codex_dir.exists():
                for f in codex_dir.glob("*.json"):
                    try:
                        d = json.loads(f.read_text())
                        if d.get("accessToken") or d.get("token"):
                            return {"ok": True, "detail": "codex CLI autenticado"}
                    except Exception:
                        pass
            return {"ok": False, "detail": "sin OPENAI_API_KEY ni codex auth"}
        return {"ok": True, "detail": f"API key ...{api_key[-4:]}"}

    def _check_anthropic():
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            return {"ok": False, "detail": "sin ANTHROPIC_API_KEY"}
        return {"ok": True, "detail": f"API key ...{key[-4:]}"}

    def _check_openrouter():
        key = os.environ.get("OPENROUTER_API_KEY", "")
        if not key:
            return {"ok": False, "detail": "sin OPENROUTER_API_KEY"}
        return {"ok": True, "detail": f"API key ...{key[-4:]}"}

    _checks = {
        "ollama-local": _check_ollama,
        "copilot":      _check_copilot,
        "codex":        _check_codex,
        "anthropic":    _check_anthropic,
        "openrouter":   _check_openrouter,
    }

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        futures = {prov: pool.submit(fn) for prov, fn in _checks.items()}
        for prov, fut in futures.items():
            try:
                results[prov] = fut.result(timeout=timeout + 1)
            except Exception as e:
                results[prov] = {"ok": False, "detail": f"error: {e}"}

    return results
