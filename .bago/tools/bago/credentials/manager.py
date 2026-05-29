"""CredentialManager — estado de providers, detección y tabla de estado."""

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
import os
import subprocess
from pathlib import Path

from rich import box
from rich.table import Table

from ..constants import ACCOUNTS_FILE, CRED_FILE
from ..provider_state import (
    expand_provider_ids,
    load_provider_state,
    normalized_provider_id,
    save_provider_state,
)
from .accounts import AccountManager
from .auth_state import (
    active_bago_providers as _active_bago_providers,
    build_login_view,
    build_status_view,
    is_valid_api_key,
)
from .login_flows import LoginFlowsMixin


class CredentialManager(LoginFlowsMixin):
    """Gestiona credenciales de todos los proveedores. /login para registrar."""

    PROVIDERS = {
        # ── LLM / AI providers ────────────────────────────────────────────────
        "github":      {"env": "GITHUB_TOKEN",         "bago_provider": "copilot",
                        "desc": "GitHub Copilot / Models",
                        "login_type": "github",
                        "group": "llm"},
        "github-models":{"env": "GITHUB_TOKEN",         "bago_provider": "github-models",
                            "desc": "GitHub Models (endpoint models.github.ai)",
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
                        "desc": "send.now (compat. send.cm) — email+password sin navegador",
                        "login_type": "sendcm",
                        "group": "cloud"},
    }

    # ── Modo API-only (v3.5) ────────────────────────────────────────────────
    # Si True: desactiva login interactivo, usa solo API keys con freno de tokens
    API_ONLY_MODE: bool = False
    API_ONLY_MAX_TOKENS_PER_CALL: int = 10000
    API_ONLY_MAX_MONTHLY_USD: float = 50.0
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
        "sendnow": "sendcm",
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

    def _load_provider_state(self) -> dict:
        return load_provider_state()

    def _save_provider_state(self, data: dict) -> None:
        save_provider_state(data)

    def _ids_for_provider(self, name: str) -> set[str]:
        raw = normalized_provider_id(name)
        ids = expand_provider_ids(raw)
        for pname, info in self.PROVIDERS.items():
            canonical = pname.replace("_", "-")
            bago_provider = str(info.get("bago_provider") or "").replace("_", "-")
            if raw in {canonical, bago_provider}:
                ids.update({canonical, bago_provider})
        ids.discard("")
        return ids

    def disabled_providers(self) -> set[str]:
        data = self._load_provider_state()
        return {normalized_provider_id(x) for x in data.get("disabled", []) if str(x).strip()}

    def is_provider_enabled(self, name: str) -> bool:
        disabled = self.disabled_providers()
        return not bool(self._ids_for_provider(name) & disabled)

    def set_provider_enabled(self, name: str, enabled: bool) -> str:
        data = self._load_provider_state()
        disabled = self.disabled_providers()
        ids = self._ids_for_provider(name)
        if enabled:
            disabled.difference_update(ids)
        else:
            disabled.update(ids)
        data["disabled"] = sorted(disabled)
        self._save_provider_state(data)
        return "activado" if enabled else "desactivado"

    def _apply_env(self):
        """Exporta credenciales guardadas como variables de entorno si no existen."""
        for name, info in self.PROVIDERS.items():
            if not self.is_provider_enabled(name):
                continue
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
        # ── sincronizar con AccountManager para que persista ────────────────
        am = getattr(self, "_accounts", None)
        if am:
            from .accounts import AccountManager
            accounts = am.accounts_for(provider_name)
            if accounts:
                # actualizar la cuenta activa existente
                active_id = am.get_active_id(provider_name)
                if active_id:
                    am.update(active_id, credential=key, enabled=True)
                else:
                    # no hay activa: usar la primera
                    am.update(accounts[0]["id"], credential=key, enabled=True)
            else:
                # crear nueva cuenta
                am.add(provider=provider_name, label="", credential=key,
                       credential_type="api_key", make_active=True)
            am.apply_active_credentials()

    def logout(self, provider_name: str) -> str:
        """Cierra sesión del provider y borra credenciales activas locales."""
        raw = str(provider_name or "").strip().lower().replace("_", "-")
        if not raw:
            return "Provider vacío."

        alias = {
            "codex": "openai",
            "gpt": "openai",
            "copilot": "github",
            "ollama-local": "ollama",
            "ollama-cloud": "ollama_cloud",
            "sendnow": "sendcm",
        }.get(raw, raw)

        removed_keys = []
        for key in {alias, raw}:
            if key in self._creds:
                self._creds.pop(key, None)
                removed_keys.append(key)

        if alias == "openai":
            for k in ("openai_via", "OPENAI_API_KEY"):
                self._creds.pop(k, None)
            os.environ.pop("OPENAI_API_KEY", None)
            os.environ.pop("OPENAI_VIA", None)
            os.environ.pop("CODEx_VIA", None)
            os.environ.pop("CHATGPT_VIA", None)
            self._accounts.clear_provider("openai")
        elif alias == "github":
            os.environ.pop("GITHUB_TOKEN", None)
            os.environ.pop("GH_TOKEN", None)
            self._accounts.clear_provider("github")
        elif alias == "ollama_cloud":
            self._creds.pop("ollama_cloud_via", None)
            os.environ.pop("OLLAMA_CLOUD_API_KEY", None)
            os.environ.pop("OLLAMA_API_KEY", None)
            self._accounts.clear_provider("ollama_cloud")
        elif alias == "sendcm":
            self._creds.pop("sendcm", None)
        elif alias in self.PROVIDERS:
            env_key = self.PROVIDERS[alias].get("env")
            if env_key:
                os.environ.pop(env_key, None)
            self._accounts.clear_provider(alias)

        self._save()
        self._accounts.apply_active_credentials()
        if removed_keys:
            return f"logout OK: {alias} ({', '.join(sorted(removed_keys))})"
        return f"logout OK: {alias}"

    # ── Detección de providers ───────────────────────────────────────────────────

    def _ollama_ok(self) -> bool:
        """Detecta si Ollama está disponible buscando en múltiples ubicaciones."""
        try:
            from ..providers import discover_ollama_url
            return discover_ollama_url(timeout=0.5) is not None
        except Exception:
            try:
                subprocess.check_output(
                    ["ollama", "list"], stderr=subprocess.DEVNULL, timeout=1
                )
                return True
            except Exception:
                return False

    def _codex_authed(self) -> bool:
        """True si la sesión OAuth de Codex/ChatGPT está activa."""
        from ..codex_auth import resolve_openai_credential
        return resolve_openai_credential()[1] == "oauth"

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
        return _active_bago_providers(self)

    def login_choices(self) -> list[tuple[str, str]]:
        """Lista (name, label) con estado plain-text para el menú interactivo."""
        active = self.active_bago_providers()
        out = []
        for name, info in self.PROVIDERS.items():
            view = build_login_view(self, name, info, active)
            if not view:
                continue
            out.append((name, f"{name:<14} {view.mark}  {view.state:<26}  {view.desc}"))
        return out

    def status_table(self) -> Table:
        """Tabla Rich con el estado de todos los providers."""
        t = Table(box=box.SIMPLE, show_header=True, header_style="bold")
        t.add_column("Provider")
        t.add_column("Login/Auth")
        t.add_column("Cuota/Gasto")
        t.add_column("Descripcion")
        for name, info in self.PROVIDERS.items():
            view = build_status_view(self, name, info)
            if not view:
                continue
            t.add_row(name, view.status, view.quota, view.desc)
        t.add_row("[dim]/login <provider>[/dim]", "", "", "[dim]para registrar[/dim]")
        return t
