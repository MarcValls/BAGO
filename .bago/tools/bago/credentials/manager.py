"""CredentialManager — estado de providers, detección y tabla de estado."""

import json
import os
import subprocess
from pathlib import Path

from rich import box
from rich.table import Table

from ..constants import ACCOUNTS_FILE, CRED_FILE
from .accounts import AccountManager
from .login_flows import LoginFlowsMixin


class CredentialManager(LoginFlowsMixin):
    """Gestiona credenciales de todos los proveedores. /login para registrar."""

    PROVIDERS = {
        # ── LLM / AI providers ────────────────────────────────────────────────
        "github":      {"env": "GITHUB_TOKEN",         "bago_provider": "copilot",
                        "desc": "GitHub Copilot / Models",
                        "login_type": "github",
                        "group": "llm"},
        "openai":      {"env": "OPENAI_API_KEY",        "bago_provider": "codex",
                        "desc": "OpenAI / GPT Plus",
                        "login_type": "openai_cli",
                        "group": "llm"},
        "anthropic":   {"env": "ANTHROPIC_API_KEY",     "bago_provider": "anthropic",
                        "desc": "Anthropic Claude",
                        "login_type": "api_key",
                        "url": "https://console.anthropic.com/keys",
                        "group": "llm"},
        "gemini":      {"env": "GEMINI_API_KEY",        "bago_provider": "gemini",
                        "desc": "Google Gemini (Flash, Pro...)",
                        "login_type": "api_key",
                        "url": "https://aistudio.google.com/app/apikey",
                        "group": "llm"},
        "groq":        {"env": "GROQ_API_KEY",          "bago_provider": "groq",
                        "desc": "Groq — inferencia ultra-rapida (Llama, Mistral...)",
                        "login_type": "api_key",
                        "url": "https://console.groq.com/keys",
                        "group": "llm"},
        "mistral":     {"env": "MISTRAL_API_KEY",       "bago_provider": "mistral",
                        "desc": "Mistral AI (Mistral Large, Codestral...)",
                        "login_type": "api_key",
                        "url": "https://console.mistral.ai/api-keys",
                        "group": "llm"},
        "together":    {"env": "TOGETHER_API_KEY",      "bago_provider": "together",
                        "desc": "Together AI (Llama, Qwen, DBRX, +100 modelos)",
                        "login_type": "api_key",
                        "url": "https://api.together.ai/settings/api-keys",
                        "group": "llm"},
        "deepseek":    {"env": "DEEPSEEK_API_KEY",      "bago_provider": "deepseek",
                        "desc": "DeepSeek (V3, R1 — razonamiento)",
                        "login_type": "api_key",
                        "url": "https://platform.deepseek.com/api_keys",
                        "group": "llm"},
        "xai":         {"env": "XAI_API_KEY",           "bago_provider": "xai",
                        "desc": "xAI Grok (Grok-2, Grok Vision)",
                        "login_type": "api_key",
                        "url": "https://console.x.ai",
                        "group": "llm"},
        "perplexity":  {"env": "PPLX_API_KEY",          "bago_provider": "perplexity",
                        "desc": "Perplexity (sonar — busqueda en tiempo real)",
                        "login_type": "api_key",
                        "url": "https://www.perplexity.ai/settings/api",
                        "group": "llm"},
        "cohere":      {"env": "COHERE_API_KEY",        "bago_provider": "cohere",
                        "desc": "Cohere (Command R+, Embed...)",
                        "login_type": "api_key",
                        "url": "https://dashboard.cohere.com/api-keys",
                        "group": "llm"},
        "replicate":   {"env": "REPLICATE_API_TOKEN",   "bago_provider": "replicate",
                        "desc": "Replicate (modelos open-source en la nube)",
                        "login_type": "api_key",
                        "url": "https://replicate.com/account/api-tokens",
                        "group": "llm"},
        "huggingface": {"env": "HF_TOKEN",              "bago_provider": "huggingface",
                        "desc": "Hugging Face (Inference API + Hub)",
                        "login_type": "huggingface",
                        "url": "https://huggingface.co/settings/tokens",
                        "group": "llm"},
        "openrouter":  {"env": "OPENROUTER_API_KEY",    "bago_provider": "openrouter",
                        "desc": "OpenRouter (+200 modelos, un solo endpoint)",
                        "login_type": "api_key",
                        "url": "https://openrouter.ai/keys",
                        "group": "llm"},
        # ── Ollama ────────────────────────────────────────────────────────────
        "ollama":      {"env": None,                    "bago_provider": "ollama-local",
                        "desc": "Ollama local (sin clave)",
                        "login_type": "service",
                        "group": "llm"},
        "ollama_cloud":{"env": "OLLAMA_CLOUD_API_KEY",  "bago_provider": "ollama-cloud",
                        "desc": "Ollama Cloud (ollama.com)",
                        "login_type": "ollama_cloud",
                        "url": "https://ollama.com/settings/api",
                        "group": "llm"},
        "opencode":    {"env": None,                    "bago_provider": "opencode",
                        "desc": "OpenCode AI (CLI)",
                        "login_type": "opencode_cli",
                        "group": "llm"},
        # ── Repositorios de código ────────────────────────────────────────────
        "gitlab":      {"env": "GITLAB_TOKEN",          "bago_provider": None,
                        "desc": "GitLab (token o email+password sin navegador)",
                        "login_type": "gitlab",
                        "url": "https://gitlab.com/-/user_settings/personal_access_tokens",
                        "group": "repo"},
        "codeberg":    {"env": "CODEBERG_TOKEN",        "bago_provider": None,
                        "desc": "Codeberg (Gitea API — token o email+password)",
                        "login_type": "codeberg",
                        "url": "https://codeberg.org/user/settings/applications",
                        "group": "repo"},
        # ── Almacenamiento cloud ───────────────────────────────────────────────
        "sendcm":      {"env": None,                    "bago_provider": None,
                        "desc": "send.cm (email+password — sin navegador)",
                        "login_type": "sendcm",
                        "group": "cloud"},
    }

    ALIASES = {
        # LLM
        "gpt": "openai", "codex": "openai", "chatgpt": "openai",
        "claude": "anthropic", "claw": "anthropic",
        "copilot": "github", "gh": "github",
        "google": "gemini", "flash": "gemini", "bard": "gemini",
        "local": "ollama",
        "cloud": "ollama_cloud",
        "hermes": "openrouter", "mixtral": "openrouter", "llama": "openrouter",
        "grok": "xai",
        "pplx": "perplexity",
        "hf": "huggingface",
        "ds": "deepseek",
        # Repos
        "gl": "gitlab",
        "cb": "codeberg", "forgejo": "codeberg",
        # Cloud
        "send": "sendcm",
    }

    def __init__(self):
        self._creds: dict = {}
        self._load()
        self._apply_env()
        self._accounts = AccountManager(ACCOUNTS_FILE)
        self._accounts.import_from_creds(self._creds)  # migra si es primera vez
        self._accounts.apply_active_credentials()      # cuentas activas sobreescriben env

    @property
    def account_manager(self) -> AccountManager:
        return self._accounts

    # ── Persistencia ────────────────────────────────────────────────────────────

    def _load(self):
        if CRED_FILE.exists():
            try:
                self._creds = json.loads(CRED_FILE.read_text(encoding="utf-8"))
            except Exception:
                self._creds = {}

    def _save(self):
        from ._atomic import atomic_write_json
        atomic_write_json(CRED_FILE, self._creds, indent=2, ensure_ascii=True)

    def _apply_env(self):
        """Exporta credenciales guardadas como variables de entorno si no existen."""
        for name, info in self.PROVIDERS.items():
            env_key = info.get("env")
            if env_key and not os.environ.get(env_key):
                saved = self._creds.get(name)
                if saved:
                    os.environ[env_key] = saved

    def set(self, provider_name: str, key: str):
        self._creds[provider_name] = key
        env_key = self.PROVIDERS.get(provider_name, {}).get("env")
        if env_key:
            os.environ[env_key] = key
        self._save()

    # ── Detección de providers ───────────────────────────────────────────────────

    def _ollama_ok(self) -> bool:
        """Detecta si Ollama está disponible buscando en múltiples ubicaciones."""
        try:
            from ..providers import discover_ollama_url
            return discover_ollama_url(timeout=2) is not None
        except Exception:
            try:
                subprocess.check_output(
                    ["ollama", "list"], stderr=subprocess.DEVNULL, timeout=4
                )
                return True
            except Exception:
                return False

    def _codex_authed(self) -> bool:
        """True si codex CLI tiene sesión activa (GPT Plus sin API key)."""
        if self._creds.get("openai_via") in ("codex_login", "chatgpt_login"):
            return True
        try:
            for f in (Path.home() / ".codex").glob("*.json"):
                try:
                    data = json.loads(f.read_text())
                    if data.get("accessToken") or data.get("token") or data.get("auth"):
                        return True
                except Exception:
                    pass
        except Exception:
            pass
        return False

    def _chatgpt_authed(self) -> bool:
        """True si chatgpt CLI tiene sesión activa."""
        chatgpt_dir = Path.home() / "AppData" / "Roaming" / "chatgpt"
        for pattern in ["*.json", "config*", "auth*"]:
            for f in chatgpt_dir.glob(pattern) if chatgpt_dir.exists() else []:
                try:
                    data = json.loads(f.read_text())
                    if data.get("accessToken") or data.get("token"):
                        return True
                except Exception:
                    pass
        return False

    # ── Consultas de estado ──────────────────────────────────────────────────────

    def active_bago_providers(self) -> list[str]:
        """Lista de bago_provider strings con credenciales activas."""
        active = []
        for name, info in self.PROVIDERS.items():
            if name == "ollama":
                if self._ollama_ok():
                    active.append("ollama-local")
            elif name == "ollama_cloud":
                if (os.environ.get("OLLAMA_CLOUD_API_KEY") or
                        self._creds.get("ollama_cloud_via") == "ollama_signin"):
                    active.append("ollama-cloud")
            elif name == "openai":
                if os.environ.get("OPENAI_API_KEY") or self._codex_authed():
                    active.append("codex")
            elif name == "opencode":
                if self._creds.get("opencode_via"):
                    active.append("opencode")
            elif name == "sendcm":
                pass  # sendcm no es un proveedor LLM, no va en active_bago_providers
            else:
                env_key = info.get("env")
                if env_key and os.environ.get(env_key):
                    active.append(info["bago_provider"])
        return active

    def login_choices(self) -> list[tuple[str, str]]:
        """Lista (name, label) con estado plain-text para el menú interactivo."""
        active = self.active_bago_providers()
        out = []
        for name, info in self.PROVIDERS.items():
            bp = info.get("bago_provider")
            ok = (bp in active) if bp else False
            mark = "✓" if ok else "·"
            if name == "github":
                tok = os.environ.get("GITHUB_TOKEN", "")
                state = f"{tok[:8]}..." if tok else "sin credencial"
            elif name == "openai":
                k = os.environ.get("OPENAI_API_KEY", "")
                if k:
                    state = f"API key {k[:4]}…" if len(k) > 4 else "API key"
                elif ok:
                    state = "codex login (GPT Plus)"
                else:
                    state = "sin credencial"
            elif name == "ollama":
                state = "activo" if ok else "no disponible"
            elif name == "ollama_cloud":
                k = os.environ.get("OLLAMA_CLOUD_API_KEY", "")
                if k:
                    state = f"API key {k[:4]}…" if len(k) > 4 else "API key"
                elif ok:
                    state = "ollama signin"
                else:
                    state = "sin credencial"
            elif name == "opencode":
                state = self._creds.get("opencode_via") or "sin auth"
            elif name == "sendcm":
                token = self._creds.get("sendcm", {}).get("api_key", "")
                email = self._creds.get("sendcm", {}).get("email", "")
                if token:
                    state = f"✓ {email}" if email else f"token {token[:6]}…"
                    mark = "✓"
                else:
                    state = "sin credencial"
            else:
                env_key = info.get("env")
                val = os.environ.get(env_key, "") if env_key else ""
                state = (f"{val[:4]}…" if len(val) > 4 else "activo") if val else "sin credencial"
            out.append((name, f"{name:<14} {mark}  {state:<26}  {info['desc']}"))
        return out

    def status_table(self) -> Table:
        """Tabla Rich con el estado de todos los providers."""
        t = Table(box=box.SIMPLE, show_header=True, header_style="bold")
        t.add_column("Provider")
        t.add_column("Estado")
        t.add_column("Descripcion")
        for name, info in self.PROVIDERS.items():
            if name == "ollama":
                ok = self._ollama_ok()
                status = "[green]✓ activo[/green]" if ok else "[red]✗ no disponible[/red]"
            elif name == "openai":
                k = os.environ.get("OPENAI_API_KEY", "")
                if k:
                    masked = f"{k[:4]}…{k[-4:]}" if len(k) > 8 else "●●●"
                    status = f"[green]✓ API key {masked}[/green]"
                elif self._codex_authed():
                    status = "[green]✓ codex login (GPT Plus)[/green]"
                else:
                    status = "[red]✗ sin credencial[/red]"
            elif name == "ollama_cloud":
                k = os.environ.get("OLLAMA_CLOUD_API_KEY", "")
                if k:
                    masked = f"{k[:4]}…{k[-4:]}" if len(k) > 8 else "●●●"
                    status = f"[green]✓ API key {masked}[/green]"
                elif self._creds.get("ollama_cloud_via") == "ollama_signin":
                    status = "[green]✓ ollama signin (cuenta ollama.com)[/green]"
                else:
                    status = "[red]✗ sin credencial[/red]"
            elif name == "opencode":
                via = self._creds.get("opencode_via")
                status = f"[green]✓ {via}[/green]" if via else "[red]✗ no instalado / sin auth[/red]"
            else:
                env_key = info.get("env")
                val = os.environ.get(env_key, "") if env_key else ""
                if val:
                    masked = f"{val[:4]}…{val[-4:]}" if len(val) > 8 else "●●●"
                    status = f"[green]✓ {masked}[/green]"
                else:
                    status = "[red]✗ sin credencial[/red]"
            t.add_row(name, status, info["desc"])
        t.add_row("[dim]/login <provider>[/dim]", "", "[dim]para registrar[/dim]")
        return t
