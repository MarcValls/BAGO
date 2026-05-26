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

from .codex_auth import codex_access_token
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
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if api_key:
            return {
                "ok": True,
                "detail": "API key configurada | cuota API no verificada",
                "auth": "api_key",
                "auth_ok": True,
                "auth_detail": "OpenAI API key configurada",
                "quota_ok": None,
                "quota_detail": "cuota/billing se confirma en la llamada real",
                "channel": "openai_api",
            }

        oauth_token = codex_access_token()
        if oauth_token:
            return {
                "ok": True,
                "detail": "ChatGPT/Codex OAuth login | no es credito API",
                "auth": "chatgpt_oauth",
                "auth_ok": True,
                "auth_detail": "ChatGPT/Codex OAuth",
                "quota_ok": None,
                "quota_detail": "login ChatGPT/Codex separado de OpenAI API billing",
                "channel": "chatgpt_codex_login",
            }

        codex_dir = Path.home() / ".codex"
        if codex_dir.exists():
            for f in codex_dir.glob("*.json"):
                try:
                    d = json.loads(f.read_text())
                    tok = (
                        d.get("access_token")
                        or d.get("accessToken")
                        or d.get("token")
                        or (d.get("tokens") or {}).get("access_token")
                        or (d.get("auth") or {}).get("access_token")
                    )
                    if tok:
                        return {
                            "ok": True,
                            "detail": "codex CLI autenticado | no es credito API",
                            "auth": "codex_cli",
                            "auth_ok": True,
                            "auth_detail": "codex CLI autenticado",
                            "quota_ok": None,
                            "quota_detail": "separado de OpenAI API billing",
                            "channel": "chatgpt_codex_login",
                        }
                except Exception:
                    pass

        cli = shutil.which("codex")
        if cli:
            return {
                "ok": False,
                "detail": "codex CLI instalado pero sin login — ejecuta: codex login",
                "auth": "none",
                "cli": cli,
                "auth_ok": False,
                "auth_detail": "sin login Codex/OpenAI",
                "quota_ok": None,
                "quota_detail": "no comprobada sin auth",
                "channel": "openai_api",
            }

        return {
            "ok": False,
            "detail": "sin OPENAI_API_KEY ni codex CLI — instala: npm i -g @openai/codex",
            "auth": "none",
            "auth_ok": False,
            "auth_detail": "sin OpenAI API key ni Codex login",
            "quota_ok": None,
            "quota_detail": "no comprobada sin auth",
            "channel": "openai_api",
        }

    def _check_ollama_cloud():
        key = os.environ.get("OLLAMA_CLOUD_API_KEY") or os.environ.get("OLLAMA_API_KEY", "")
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
