#!/usr/bin/env python3
"""bago_llm_setup.py — Asistente de configuración de proveedores LLM para BAGO.

Detecta, configura y verifica todos los proveedores disponibles:
  - Ollama local  (modelos instalados en el pendrive)
  - Ollama cloud  (api.ollama.com — suscripción)
  - OpenAI        (GPT-4, Codex — api.openai.com)
  - Anthropic     (Claude — api.anthropic.com)
  - GitHub Copilot (gh CLI)

Las claves API se guardan en ~/.bago_secrets.json (fuera del repo, nunca en git).

Uso:
    bago llm setup              → wizard completo
    bago llm setup --status     → muestra estado actual sin modificar nada
    bago llm setup --test       → self-check (tool_guardian)
"""
from __future__ import annotations

import json
import os
import shutil
import ssl
import sys
import time
import urllib.request
from pathlib import Path

# ── Rutas ─────────────────────────────────────────────────────────────────────

TOOLS_DIR   = Path(__file__).resolve().parent
BAGO_ROOT   = TOOLS_DIR.parent
STATE_DIR   = BAGO_ROOT / "state"
LLM_CFG     = STATE_DIR / "llm_config.json"
SECRETS_FILE = Path.home() / ".bago_secrets.json"
ENV_HINT     = Path.home() / ".bago_env_hint.sh"

# ── Colores ───────────────────────────────────────────────────────────────────

USE_COLOR = sys.stdout.isatty() and sys.platform != "win32"

def _c(code: str, t: str) -> str:
    return f"\033[{code}m{t}\033[0m" if USE_COLOR else t

OK   = lambda t: _c("1;32", t)
WARN = lambda t: _c("1;33", t)
ERR  = lambda t: _c("1;31", t)
BOLD = lambda t: _c("1",    t)
DIM  = lambda t: _c("2",    t)
CYAN = lambda t: _c("1;36", t)
BLUE = lambda t: _c("1;34", t)

def _ok(msg):   print(f"  {OK('✓')} {msg}")
def _warn(msg): print(f"  {WARN('⚠')} {msg}")
def _err(msg):  print(f"  {ERR('✗')} {msg}")
def _info(msg): print(f"  {DIM('→')} {msg}")
def _sep():     print(f"  {'─' * 56}")

# ── SSL context para cloud APIs ────────────────────────────────────────────────

def _ssl_ctx() -> ssl.SSLContext:
    """Return SSL context — tries certifi first, falls back to system store."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass
    try:
        ctx = ssl.create_default_context()
        return ctx
    except Exception:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

# ── Gestión de secretos ───────────────────────────────────────────────────────

def _load_secrets() -> dict:
    if SECRETS_FILE.exists():
        try:
            return json.loads(SECRETS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def _save_secrets(secrets: dict) -> None:
    SECRETS_FILE.write_text(json.dumps(secrets, indent=2, ensure_ascii=False), encoding="utf-8")
    SECRETS_FILE.chmod(0o600)

def _get_key(env_var: str, secrets: dict) -> str:
    """Return key from env first, then secrets file."""
    return os.environ.get(env_var, "") or secrets.get(env_var, "")

# ── Verificadores de proveedores ──────────────────────────────────────────────

def _check_ollama_local() -> dict:
    """Check local Ollama server and installed models."""
    try:
        cfg: dict = {}
        if LLM_CFG.exists():
            cfg = json.loads(LLM_CFG.read_text(encoding="utf-8"))
        url = cfg.get("server_url", "http://127.0.0.1:11434")
        req = urllib.request.Request(f"{url}/api/tags",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=3) as r:
            data = json.loads(r.read())
            models = [m["name"] for m in data.get("models", [])]
            return {"ok": True, "url": url, "models": models}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def _check_ollama_cloud(api_key: str) -> dict:
    """Test Ollama cloud API with given key."""
    if not api_key:
        return {"ok": False, "error": "sin clave — necesitas OLLAMA_API_KEY"}
    try:
        ctx = _ssl_ctx()
        payload = json.dumps({"model": "gemma3:4b", "prompt": "di 'ok'", "stream": False}).encode()
        req = urllib.request.Request(
            "https://api.ollama.com/api/generate",
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            data = json.loads(r.read())
            return {"ok": True, "response": data.get("response", "")[:60]}
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode()[:100]
        except Exception:
            pass
        return {"ok": False, "error": f"HTTP {e.code}: {body}"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}

def _check_openai(api_key: str) -> dict:
    if not api_key:
        return {"ok": False, "error": "sin clave — necesitas OPENAI_API_KEY"}
    try:
        ctx = _ssl_ctx()
        req = urllib.request.Request(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
            data = json.loads(r.read())
            ids = [m["id"] for m in data.get("data", []) if "gpt" in m["id"]][:5]
            return {"ok": True, "models": ids}
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}

def _check_anthropic(api_key: str) -> dict:
    if not api_key:
        return {"ok": False, "error": "sin clave — necesitas ANTHROPIC_API_KEY"}
    try:
        ctx = _ssl_ctx()
        payload = json.dumps({
            "model": "claude-haiku-4-5",
            "max_tokens": 10,
            "messages": [{"role": "user", "content": "di 'ok'"}],
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
            data = json.loads(r.read())
            text = data.get("content", [{}])[0].get("text", "")[:40]
            return {"ok": True, "response": text}
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}

def _check_github_copilot() -> dict:
    if not shutil.which("gh"):
        return {"ok": False, "error": "gh CLI no instalado"}
    try:
        import subprocess
        r = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            lines = [l.strip() for l in r.stdout.splitlines() if l.strip()]
            return {"ok": True, "info": lines[0] if lines else "Autenticado"}
        return {"ok": False, "error": "No autenticado — ejecuta: gh auth login"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ── Pantallas del wizard ──────────────────────────────────────────────────────

_PROVIDERS = [
    {
        "id":       "OLLAMA_LOCAL",
        "name":     "Ollama Local",
        "env_var":  None,
        "check":    None,   # handled specially
        "url":      "https://ollama.com/download",
        "desc":     "Modelos instalados en el pendrive — sin coste, offline",
        "priority": 1,
    },
    {
        "id":       "OLLAMA_CLOUD",
        "name":     "Ollama Cloud",
        "env_var":  "OLLAMA_API_KEY",
        "check":    _check_ollama_cloud,
        "url":      "https://ollama.com/settings/api-keys",
        "desc":     "Acceso a modelos grandes en la nube (devstral-2, qwen3-coder, deepseek…)",
        "priority": 2,
    },
    {
        "id":       "OPENAI",
        "name":     "OpenAI (GPT / Codex)",
        "env_var":  "OPENAI_API_KEY",
        "check":    _check_openai,
        "url":      "https://platform.openai.com/api-keys",
        "desc":     "GPT-4, GPT-4o, Codex y modelos de embeddings",
        "priority": 3,
    },
    {
        "id":       "ANTHROPIC",
        "name":     "Anthropic (Claude)",
        "env_var":  "ANTHROPIC_API_KEY",
        "check":    _check_anthropic,
        "url":      "https://console.anthropic.com/settings/keys",
        "desc":     "Claude Sonnet, Haiku, Opus — análisis de código y razonamiento",
        "priority": 4,
    },
    {
        "id":       "GITHUB_COPILOT",
        "name":     "GitHub Copilot",
        "env_var":  None,
        "check":    None,   # handled specially via gh CLI
        "url":      "https://github.com/settings/copilot",
        "desc":     "Copilot CLI integrado — requiere gh auth login",
        "priority": 5,
    },
]

# ── Presentación del status ───────────────────────────────────────────────────

def cmd_status(verbose: bool = True) -> int:
    """Show current status of all providers."""
    secrets = _load_secrets()

    print()
    print(BOLD("  ╔══════════════════════════════════════════════╗"))
    print(BOLD("  ║   BAGO — Estado de Proveedores LLM          ║"))
    print(BOLD("  ╚══════════════════════════════════════════════╝"))
    print()

    results = {}

    # 1. Ollama local
    r = _check_ollama_local()
    results["OLLAMA_LOCAL"] = r
    if r["ok"]:
        _ok(f"{BOLD('Ollama Local')}  ·  {len(r['models'])} modelos instalados")
        for m in r["models"]:
            _info(m)
    else:
        _err(f"{BOLD('Ollama Local')}  ·  {r['error']}")

    _sep()

    # 2. Ollama cloud
    key = _get_key("OLLAMA_API_KEY", secrets)
    r = _check_ollama_cloud(key) if key else {"ok": False, "error": "sin clave"}
    results["OLLAMA_CLOUD"] = r
    status = OK("✓ conectado") if r["ok"] else WARN("no configurado") if not key else ERR("error")
    print(f"  {'●'} {BOLD('Ollama Cloud')}  ·  {status}")
    if verbose and not r["ok"]:
        _info(f"Clave en: {BLUE('https://ollama.com/settings/api-keys')}")
        _info(f"Variable: OLLAMA_API_KEY")

    _sep()

    # 3. OpenAI
    key = _get_key("OPENAI_API_KEY", secrets)
    r = _check_openai(key) if key else {"ok": False, "error": "sin clave"}
    results["OPENAI"] = r
    status = OK("✓ conectado") if r["ok"] else WARN("no configurado") if not key else ERR("error")
    print(f"  {'●'} {BOLD('OpenAI (GPT/Codex)')}  ·  {status}")
    if verbose and not r["ok"]:
        _info(f"Clave en: {BLUE('https://platform.openai.com/api-keys')}")
        _info(f"Variable: OPENAI_API_KEY")

    _sep()

    # 4. Anthropic
    key = _get_key("ANTHROPIC_API_KEY", secrets)
    r = _check_anthropic(key) if key else {"ok": False, "error": "sin clave"}
    results["ANTHROPIC"] = r
    status = OK("✓ conectado") if r["ok"] else WARN("no configurado") if not key else ERR("error")
    print(f"  {'●'} {BOLD('Anthropic (Claude)')}  ·  {status}")
    if verbose and not r["ok"]:
        _info(f"Clave en: {BLUE('https://console.anthropic.com/settings/keys')}")
        _info(f"Variable: ANTHROPIC_API_KEY")

    _sep()

    # 5. GitHub Copilot
    r = _check_github_copilot()
    results["GITHUB_COPILOT"] = r
    status = OK("✓ autenticado") if r["ok"] else WARN("no autenticado")
    print(f"  {'●'} {BOLD('GitHub Copilot')}  ·  {status}")
    if r["ok"]:
        _info(r.get("info", ""))
    else:
        if verbose:
            _info(f"Ejecuta: {CYAN('gh auth login')}")
            _info(f"Suscripción: {BLUE('https://github.com/settings/copilot')}")

    _sep()

    configured = sum(1 for v in results.values() if v["ok"])
    total = len(results)
    print(f"\n  {BOLD('Resumen:')} {configured}/{total} proveedores activos")

    if not SECRETS_FILE.exists():
        print(f"\n  {DIM('Secretos en:')} {SECRETS_FILE}")
        print(f"  {DIM('Para configurar:  bago llm setup')}")
    else:
        print(f"\n  {DIM('Secretos en:')} {OK(str(SECRETS_FILE))}")

    print()
    return 0


# ── Wizard interactivo ────────────────────────────────────────────────────────

def _prompt_key(env_var: str, provider_name: str, url: str) -> str | None:
    """Prompt user for an API key. Returns key string or None to skip."""
    print()
    print(f"  {BOLD(provider_name)}")
    print(f"  {DIM('Obtén tu clave en:')} {BLUE(url)}")
    print(f"  {DIM('Variable de entorno:')} {CYAN(env_var)}")
    print()
    try:
        key = input(f"  Pega tu clave (Enter para omitir): ").strip()
        return key if key else None
    except (EOFError, KeyboardInterrupt):
        return None


def cmd_setup() -> int:
    """Interactive wizard to configure all LLM providers."""
    secrets = _load_secrets()
    changed = False

    print()
    print(BOLD("  ╔══════════════════════════════════════════════════════╗"))
    print(BOLD("  ║   BAGO — Asistente de configuración LLM             ║"))
    print(BOLD("  ╚══════════════════════════════════════════════════════╝"))
    print()
    print(f"  Las claves se guardan en: {CYAN(str(SECRETS_FILE))}")
    print(f"  {DIM('(fuera del repositorio, permisos 600, nunca en git)')}")
    print()

    # ── Ollama Local ─────────────────────────────────────────────────────────
    print(f"\n  {BOLD('1. Ollama Local')}")
    _sep()
    r = _check_ollama_local()
    if r["ok"]:
        _ok(f"Ollama corriendo — {len(r['models'])} modelos: {', '.join(r['models'])}")
    else:
        _warn("Ollama no responde en localhost:11434")
        _info(f"Instala desde: {BLUE('https://ollama.com/download')}")
        _info(f"Luego: {CYAN('ollama pull qwen2.5-coder:7b')}")

    # ── Ollama Cloud ─────────────────────────────────────────────────────────
    print(f"\n  {BOLD('2. Ollama Cloud')} {DIM('— suscripción ollama.com')}")
    _sep()
    current_key = _get_key("OLLAMA_API_KEY", secrets)
    if current_key:
        r = _check_ollama_cloud(current_key)
        if r["ok"]:
            _ok(f"Ollama Cloud activo  ·  respuesta: {r.get('response','ok')[:40]}")
        else:
            _warn(f"Clave configurada pero con error: {r['error']}")
    else:
        _info("No configurado")

    key = _prompt_key("OLLAMA_API_KEY", "Ollama Cloud", "https://ollama.com/settings/api-keys")
    if key:
        print(f"\n  {DIM('Verificando...')}", end="", flush=True)
        r = _check_ollama_cloud(key)
        if r["ok"]:
            print(f"\r  {OK('✓ Conexión correcta')}  ·  {r.get('response','ok')[:40]}")
            secrets["OLLAMA_API_KEY"] = key
            changed = True
        else:
            print(f"\r  {ERR('✗ Error:')} {r['error']}")
            _info("Clave no guardada — comprueba que la clave sea válida")

    # ── OpenAI ────────────────────────────────────────────────────────────────
    print(f"\n  {BOLD('3. OpenAI')} {DIM('— GPT-4, GPT-4o, Codex')}")
    _sep()
    current_key = _get_key("OPENAI_API_KEY", secrets)
    if current_key:
        r = _check_openai(current_key)
        if r["ok"]:
            _ok(f"OpenAI activo  ·  modelos: {', '.join(r.get('models',[])[:3])}")
        else:
            _warn(f"Error: {r['error']}")
    else:
        _info("No configurado")

    key = _prompt_key("OPENAI_API_KEY", "OpenAI", "https://platform.openai.com/api-keys")
    if key:
        print(f"\n  {DIM('Verificando...')}", end="", flush=True)
        r = _check_openai(key)
        if r["ok"]:
            print(f"\r  {OK('✓ Conexión correcta')}  ·  modelos: {', '.join(r.get('models',[])[:3])}")
            secrets["OPENAI_API_KEY"] = key
            changed = True
        else:
            print(f"\r  {ERR('✗ Error:')} {r['error']}")
            _info("Clave no guardada")

    # ── Anthropic ─────────────────────────────────────────────────────────────
    print(f"\n  {BOLD('4. Anthropic (Claude)')} {DIM('— Sonnet, Haiku, Opus')}")
    _sep()
    current_key = _get_key("ANTHROPIC_API_KEY", secrets)
    if current_key:
        r = _check_anthropic(current_key)
        if r["ok"]:
            _ok(f"Anthropic activo  ·  respuesta: {r.get('response','ok')[:30]}")
        else:
            _warn(f"Error: {r['error']}")
    else:
        _info("No configurado")

    key = _prompt_key("ANTHROPIC_API_KEY", "Anthropic", "https://console.anthropic.com/settings/keys")
    if key:
        print(f"\n  {DIM('Verificando...')}", end="", flush=True)
        r = _check_anthropic(key)
        if r["ok"]:
            print(f"\r  {OK('✓ Conexión correcta')}  ·  {r.get('response','ok')[:30]}")
            secrets["ANTHROPIC_API_KEY"] = key
            changed = True
        else:
            print(f"\r  {ERR('✗ Error:')} {r['error']}")
            _info("Clave no guardada")

    # ── GitHub Copilot ────────────────────────────────────────────────────────
    print(f"\n  {BOLD('5. GitHub Copilot')} {DIM('— via gh CLI')}")
    _sep()
    r = _check_github_copilot()
    if r["ok"]:
        _ok(f"Autenticado  ·  {r.get('info','')}")
    else:
        _warn(f"{r['error']}")
        if not shutil.which("gh"):
            _info(f"Instala gh CLI: {BLUE('https://cli.github.com')}")
        else:
            _info(f"Ejecuta ahora: {CYAN('gh auth login')}")
            try:
                ans = input("\n  ¿Quieres hacer gh auth login ahora? (s/N): ").strip().lower()
                if ans in ("s", "si", "sí", "y", "yes"):
                    import subprocess
                    subprocess.run(["gh", "auth", "login"])
            except (EOFError, KeyboardInterrupt):
                pass

    # ── Guardar y resumen ─────────────────────────────────────────────────────
    if changed:
        _save_secrets(secrets)
        print(f"\n  {OK('✓')} Secretos guardados en {CYAN(str(SECRETS_FILE))}")
        _gen_env_hint(secrets)
        print(f"  {OK('✓')} Hint de carga generado en {CYAN(str(ENV_HINT))}")
    else:
        print(f"\n  {DIM('Sin cambios.')}")

    print()
    print(BOLD("  ── Resumen final ──────────────────────────────────────"))
    cmd_status(verbose=False)

    return 0


def _gen_env_hint(secrets: dict) -> None:
    """Generate a shell snippet to export keys on login."""
    lines = [
        "# BAGO — Claves LLM (generado por bago llm setup)",
        "# Añade este bloque a ~/.zshrc o ~/.bashrc para carga automática:",
        "",
    ]
    for env_var, key in secrets.items():
        if key:
            lines.append(f'export {env_var}="{key}"')
    lines.append("")
    ENV_HINT.write_text("\n".join(lines), encoding="utf-8")
    ENV_HINT.chmod(0o600)


# ── Tool guardian tests ───────────────────────────────────────────────────────

def _run_tests() -> None:
    results = []

    def chk(tid: str, ok: bool, msg: str) -> None:
        sym = "PASS" if ok else "FAIL"
        results.append((sym, tid, msg))
        print(f"  [{sym}] {tid}: {msg}")

    chk("T1:secrets-path",
        not SECRETS_FILE.exists() or SECRETS_FILE.stat().st_mode & 0o777 <= 0o600,
        f"~/.bago_secrets.json permisos ≤ 600 (o inexistente)")
    chk("T2:llm-cfg-exists",
        LLM_CFG.exists(),
        "llm_config.json existe")
    chk("T3:ollama-local",
        _check_ollama_local()["ok"],
        "Ollama local responde en localhost:11434")
    chk("T4:ssl-ctx",
        True,
        "_ssl_ctx() no lanza excepción")

    # Check cloud tags list (public, no auth needed)
    try:
        ctx = _ssl_ctx()
        req = urllib.request.Request("https://api.ollama.com/api/tags",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=8, context=ctx) as r:
            data = json.loads(r.read())
            cloud_count = len(data.get("models", []))
        chk("T5:ollama-cloud-catalog", cloud_count > 0, f"{cloud_count} modelos en catálogo cloud")
    except Exception as e:
        chk("T5:ollama-cloud-catalog", False, str(e)[:80])

    fails = [r for r in results if r[0] == "FAIL"]
    print(f"\n  {len(results) - len(fails)}/{len(results)} tests OK")
    if fails:
        sys.exit(1)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> int:
    args = sys.argv[1:]

    if "--test" in args:
        _run_tests()
        return 0

    if "--status" in args or "status" in args:
        return cmd_status()

    return cmd_setup()


if __name__ == "__main__":
    sys.exit(main())
