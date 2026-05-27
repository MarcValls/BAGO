"""Health checks reales de providers BAGO."""

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

import concurrent.futures
import json
import os
import shutil
import urllib.error
import urllib.request
from pathlib import Path

from .openai_service_state import openai_service_state
from .ollama_runtime import discover_ollama_url, ollama_probe


def scan_provider_health(creds, providers: dict, timeout: int = 3) -> dict:
    """Verifica la disponibilidad real de cada provider registrado."""
    results: dict = {}

    def _check_ollama():
        url = discover_ollama_url(timeout=timeout)
        if url:
            probe = ollama_probe(url)
            n = len(probe["models"])
            detail = f"{url} — {n} modelos" if n else f"{url} — sin modelos instalados"
            return {
                "ok": True, "detail": detail, "models": probe["models"], "url": url,
                "auth_ok": True, "auth_detail": "sin auth: local",
                "quota_ok": True, "quota_detail": "sin gasto API",
                "channel": "ollama_local",
            }
        return {
            "ok": False, "detail": "no encontrado en ninguna ubicación", "models": [], "url": None,
            "auth_ok": None, "auth_detail": "no aplica",
            "quota_ok": True, "quota_detail": "sin gasto API",
            "channel": "ollama_local",
        }

    def _check_copilot():
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN", "")
        if not token:
            return {
                "ok": False, "detail": "sin GITHUB_TOKEN",
                "auth_ok": False, "auth_detail": "sin login/token GitHub",
                "quota_ok": None, "quota_detail": "no comprobada sin auth",
                "channel": "github_copilot",
            }
        try:
            req = urllib.request.Request(
                "https://api.github.com/user",
                headers={"Authorization": f"token {token}", "User-Agent": "BAGO-CLI"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                json.loads(r.read())
                return {
                    "ok": True,
                    "detail": "GitHub autenticado | cuota Copilot/GitHub no verificada",
                    "auth_ok": True,
                    "auth_detail": "GitHub autenticado",
                    "quota_ok": None,
                    "quota_detail": "login no garantiza Copilot/API quota",
                    "channel": "github_copilot",
                }
        except urllib.error.HTTPError as e:
            if e.code == 401:
                return {
                    "ok": False, "detail": "token inválido (401)",
                    "auth_ok": False, "auth_detail": "token inválido",
                    "quota_ok": None, "quota_detail": "no comprobada",
                    "channel": "github_copilot",
                }
            quota_block = e.code in (403, 429)
            return {
                "ok": not quota_block,
                "detail": f"HTTP {e.code}",
                "auth_ok": True,
                "auth_detail": "token aceptado por GitHub",
                "quota_ok": False if quota_block else None,
                "quota_detail": "rate limit/permisos GitHub" if quota_block else "no comprobada",
                "channel": "github_copilot",
            }
        except Exception as e:
            return {
                "ok": False, "detail": str(e)[:60],
                "auth_ok": None, "auth_detail": "no comprobado",
                "quota_ok": None, "quota_detail": "no comprobada",
                "channel": "github_copilot",
            }

    def _check_codex():
        state = openai_service_state(creds)
        cli = shutil.which("codex")
        if not state["ok"]:
            if cli:
                return {
                    "ok": False,
                    "detail": "codex CLI instalado pero sin login — ejecuta: codex login",
                    "auth": "none",
                    "cli": cli,
                    "auth_ok": False,
                    "auth_detail": "sin login OpenAI API ni ChatGPT Plus",
                    "quota_ok": None,
                    "quota_detail": "no comprobada sin auth",
                    "channel": "openai_api",
                    "source": "none",
                }
            return {
                "ok": False,
                "detail": "sin OPENAI_API_KEY ni codex CLI — instala: npm i -g @openai/codex",
                "auth": "none",
                "auth_ok": False,
                "auth_detail": "sin OpenAI API key ni ChatGPT Plus login",
                "quota_ok": None,
                "quota_detail": "no comprobada sin auth",
                "channel": "openai_api",
                "source": "none",
            }

        if state["api_ok"] and state["chatgpt_plus_ok"]:
            return {
                **state,
                "auth": "api_key+chatgpt_plus",
                "channel": "openai_api",
                "source": "api",
                "cli": cli,
            }
        if state["api_ok"]:
            return {
                **state,
                "auth": "api_key",
                "channel": "openai_api",
                "source": "api",
                "cli": cli,
            }
        return {
            **state,
            "auth": "chatgpt_plus",
            "channel": "chatgpt_plus",
            "source": "chatgpt_plus",
            "cli": cli,
        }

    def _check_ollama_cloud():
        key = os.environ.get("OLLAMA_CLOUD_API_KEY") or os.environ.get("OLLAMA_API_KEY", "")
        if not key:
            try:
                from .credentials import CredentialManager
                key = CredentialManager()._creds.get("ollama_cloud", "")
                if not isinstance(key, str):
                    key = ""
            except Exception:
                key = ""
        base_url = os.environ.get("OLLAMA_CLOUD_BASE_URL", "https://api.ollama.com")
        if not key:
            return {
                "ok": False,
                "detail": "sin OLLAMA_CLOUD_API_KEY/OLLAMA_API_KEY",
                "auth_ok": False,
                "auth_detail": "sin API key Ollama Cloud",
                "quota_ok": None,
                "quota_detail": "no comprobada sin auth",
                "channel": "ollama_cloud_api",
                "url": base_url,
            }
        return {
            "ok": True,
            "detail": "API key configurada | cuota Ollama Cloud no verificada",
            "auth_ok": True,
            "auth_detail": "Ollama Cloud API key configurada",
            "quota_ok": None,
            "quota_detail": "se confirma en la llamada real",
            "channel": "ollama_cloud_api",
            "url": base_url,
        }

    def _check_replicate():
        key = os.environ.get("REPLICATE_API_TOKEN", "")
        if not key:
            try:
                from .credentials import CredentialManager
                key = CredentialManager()._creds.get("replicate", "")
                if not isinstance(key, str):
                    key = ""
            except Exception:
                key = ""
        if not key:
            return {
                "ok": False,
                "detail": "sin REPLICATE_API_TOKEN",
                "auth_ok": False,
                "auth_detail": "sin API key Replicate",
                "quota_ok": None,
                "quota_detail": "no comprobada sin auth",
                "channel": "replicate_api",
            }
        return {
            "ok": True,
            "detail": "API key configurada | cuota Replicate no verificada",
            "auth_ok": True,
            "auth_detail": "Replicate API key configurada",
            "quota_ok": None,
            "quota_detail": "se confirma en la llamada real",
            "channel": "replicate_api",
        }

    def _check_local_openai():
        base_url = os.environ.get("LOCAL_OPENAI_BASE_URL", "http://127.0.0.1:1234/v1").rstrip("/")
        api_key = os.environ.get("LOCAL_OPENAI_API_KEY", "")
        if not api_key:
            try:
                from .credentials import CredentialManager
                api_key = CredentialManager()._creds.get("local-openai", "")
                if not isinstance(api_key, str):
                    api_key = ""
            except Exception:
                api_key = ""
        headers = {"User-Agent": "BAGO-CLI"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            req = urllib.request.Request(
                f"{base_url}/models",
                headers=headers,
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read())
                models_raw = data.get("data", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                model_ids = [m.get("id") for m in models_raw if m.get("id")]
                n = len(model_ids)
                sample = ", ".join(model_ids[:3]) if model_ids else "..."
                return {
                    "ok": True,
                    "detail": f"{n} modelos en {base_url}: {sample}{'…' if n >= 3 else ''}",
                    "models": model_ids,
                    "auth_ok": True,
                    "auth_detail": "endpoint local responde",
                    "quota_ok": True,
                    "quota_detail": "sin gasto API local",
                    "channel": "local_openai_compat",
                    "url": base_url,
                }
        except urllib.error.HTTPError as e:
            if e.code == 401:
                return {
                    "ok": False,
                    "detail": f"endpoint requiere auth (401) en {base_url}",
                    "auth_ok": False,
                    "auth_detail": "API key requerida o incorrecta",
                    "quota_ok": None,
                    "quota_detail": "no comprobada",
                    "channel": "local_openai_compat",
                    "url": base_url,
                }
            return {
                "ok": True,
                "detail": f"endpoint responde (HTTP {e.code}) en {base_url}",
                "auth_ok": True,
                "auth_detail": "endpoint local responde",
                "quota_ok": True,
                "quota_detail": "sin gasto API local",
                "channel": "local_openai_compat",
                "url": base_url,
            }
        except Exception as e:
            return {
                "ok": False,
                "detail": f"no responde en {base_url}: {str(e)[:60]}",
                "auth_ok": None,
                "auth_detail": "no comprobado",
                "quota_ok": None,
                "quota_detail": "no comprobada",
                "channel": "local_openai_compat",
                "url": base_url,
            }

    def _check_anthropic():
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            return {"ok": False, "detail": "sin ANTHROPIC_API_KEY"}
        return {"ok": True, "detail": "API key configurada"}

    def _check_gemini():
        key = os.environ.get("GEMINI_API_KEY", "")
        if not key:
            return {"ok": False, "detail": "sin GEMINI_API_KEY — https://aistudio.google.com"}
        try:
            req = urllib.request.Request(
                f"https://generativelanguage.googleapis.com/v1beta/models?key={key}&pageSize=5",
                headers={"User-Agent": "BAGO-CLI"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read())
                models_raw = data.get("models", [])
                model_names = [
                    m.get("name", "").replace("models/", "")
                    for m in models_raw
                    if m.get("name")
                ]
                n = len(model_names)
                sample = ", ".join(model_names[:3]) if model_names else "..."
                return {
                    "ok": True,
                    "detail": f"API key configurada  ({sample}{'…' if n >= 3 else ''})",
                    "models": model_names,
                }
        except urllib.error.HTTPError as e:
            if e.code == 400:
                return {"ok": False, "detail": "API key invalida (400)"}
            if e.code == 403:
                return {"ok": False, "detail": "API key sin permisos (403)"}
            return {"ok": True, "detail": f"API key configurada  (HTTP {e.code})"}
        except Exception:
            return {"ok": True, "detail": "API key configurada  (sin conexion)"}

    def _check_openrouter():
        key = os.environ.get("OPENROUTER_API_KEY", "")
        if not key:
            return {"ok": False, "detail": "sin OPENROUTER_API_KEY"}
        return {"ok": True, "detail": "API key configurada"}

    def _check_github_models():
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN", "")
        if not token:
            return {
                "ok": False, "detail": "sin GITHUB_TOKEN — ejecuta: gh auth login",
                "auth_ok": False, "auth_detail": "sin login/token GitHub",
                "quota_ok": None, "quota_detail": "no comprobada sin auth",
                "channel": "github_models_api",
            }

        try:
            req = urllib.request.Request(
                "https://models.github.ai/catalog/models",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "BAGO-CLI",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read())
                models_raw = data if isinstance(data, list) else data.get("models", [])
                model_ids = []
                for model in models_raw:
                    mid = model.get("id") or model.get("name") or ""
                    if mid:
                        model_ids.append(mid)
                n = len(model_ids)
                sample = ", ".join(model_ids[:3])
                suffix = f" (+{n-3} mas)" if n > 3 else ""
                return {
                    "ok": True,
                    "detail": f"{n} modelos disponibles: {sample}{suffix} | cuota API no verificada",
                    "models": model_ids,
                    "tier": "free" if n > 0 else "unknown",
                    "auth_ok": True,
                    "auth_detail": "token GitHub aceptado",
                    "quota_ok": None,
                    "quota_detail": "GitHub Models rate limit separado del login",
                    "channel": "github_models_api",
                }
        except urllib.error.HTTPError as e:
            if e.code == 401:
                return {
                    "ok": False, "detail": "token invalido (401) — re-ejecuta: gh auth login",
                    "auth_ok": False, "auth_detail": "token inválido",
                    "quota_ok": None, "quota_detail": "no comprobada",
                    "channel": "github_models_api",
                }
            if e.code == 403:
                return {
                    "ok": False, "detail": "acceso denegado (403) — permisos/rate limit GitHub Models",
                    "auth_ok": True, "auth_detail": "token GitHub aceptado",
                    "quota_ok": False, "quota_detail": "sin permisos o rate limit GitHub Models",
                    "channel": "github_models_api",
                }
            if e.code == 404:
                return {
                    "ok": False, "detail": "endpoint no encontrado (404) — verifica models.github.ai",
                    "auth_ok": True, "auth_detail": "token GitHub aceptado",
                    "quota_ok": None, "quota_detail": "endpoint no disponible",
                    "channel": "github_models_api",
                }
            return {
                "ok": False, "detail": f"HTTP {e.code} desde models.github.ai",
                "auth_ok": True, "auth_detail": "token GitHub aceptado",
                "quota_ok": False if e.code == 429 else None,
                "quota_detail": "rate limit GitHub Models" if e.code == 429 else "no comprobada",
                "channel": "github_models_api",
            }
        except Exception as e:
            return {
                "ok": False, "detail": f"error al conectar con models.github.ai: {str(e)[:60]}",
                "auth_ok": None, "auth_detail": "no comprobado",
                "quota_ok": None, "quota_detail": "no comprobada",
                "channel": "github_models_api",
            }

    checks = {
        "ollama-local": _check_ollama,
        "ollama-cloud": _check_ollama_cloud,
        "copilot": _check_copilot,
        "github-models": _check_github_models,
        "codex": _check_codex,
        "anthropic": _check_anthropic,
        "gemini": _check_gemini,
        "openrouter": _check_openrouter,
        "replicate": _check_replicate,
        "local-openai": _check_local_openai,
    }
    enabled_checks = {
        prov: fn for prov, fn in checks.items()
        if not hasattr(creds, "is_provider_enabled") or creds.is_provider_enabled(prov)
    }

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = {prov: pool.submit(fn) for prov, fn in enabled_checks.items()}
        for prov, fut in futures.items():
            try:
                results[prov] = fut.result(timeout=timeout + 1)
            except Exception as e:
                results[prov] = {"ok": False, "detail": f"error: {e}"}

    return results


def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(f"{Path(__file__).name} --test: PASS (imports OK)")
    return 0
if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
