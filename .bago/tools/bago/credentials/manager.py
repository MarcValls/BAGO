"""CredentialManager — estado de providers, detección y tabla de estado."""

import json
import os
import subprocess
from pathlib import Path

from rich import box
from rich.table import Table

from ..constants import ACCOUNTS_FILE, CRED_FILE
from ..ui import console
from .accounts import AccountManager
from .login_flows import LoginFlowsMixin


class CredentialManager(LoginFlowsMixin):
    """Gestiona credenciales de todos los proveedores. /login para registrar."""

    PROVIDERS = {
        "github":      {"env": "GITHUB_TOKEN",         "bago_provider": "copilot",
                        "desc": "GitHub Copilot",       "login_type": "gh_cli"},
        "openai":      {"env": "OPENAI_API_KEY",        "bago_provider": "codex",
                        "desc": "OpenAI / GPT Plus (codex login o API key)",
                        "login_type": "openai_cli"},
        "anthropic":   {"env": "ANTHROPIC_API_KEY",     "bago_provider": "anthropic",
                        "desc": "Anthropic Claude / Claw (API key)",
                        "login_type": "api_key",
                        "url": "https://console.anthropic.com/keys"},
        "ollama":      {"env": None,                    "bago_provider": "ollama-local",
                        "desc": "Ollama local (sin clave)", "login_type": "service"},
        "gemini":      {"env": "GEMINI_API_KEY",        "bago_provider": "gemini",
                        "desc": "Google Gemini (Gemini 2.0, Flash, Pro...)",
                        "login_type": "api_key",
                        "url": "https://aistudio.google.com/app/apikey"},
        "ollama_cloud":{"env": "OLLAMA_CLOUD_API_KEY",  "bago_provider": "ollama-cloud",
                        "desc": "Ollama Cloud (ollama.com — signin o API key)",
                        "login_type": "ollama_cloud",
                        "url": "https://ollama.com/settings/api"},
        "opencode":    {"env": None,                    "bago_provider": "opencode",
                        "desc": "OpenCode AI (asistente de codigo con IA)",
                        "login_type": "opencode_cli"},
        "openrouter":  {"env": "OPENROUTER_API_KEY",    "bago_provider": "openrouter",
                        "desc": "OpenRouter — Hermes, Mixtral, Llama, DeepSeek y mas",
                        "login_type": "api_key",
                        "url": "https://openrouter.ai/keys"},
    }

    ALIASES = {
        "gpt": "openai", "codex": "openai",
        "claude": "anthropic", "claw": "anthropic",
        "copilot": "github", "gh": "github",
        "local": "ollama",
        "google": "gemini", "flash": "gemini",
        "hermes": "openrouter", "mixtral": "openrouter", "llama": "openrouter",
        "cloud": "ollama_cloud",
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
        CRED_FILE.parent.mkdir(parents=True, exist_ok=True)
        CRED_FILE.write_text(json.dumps(self._creds, indent=2), encoding="utf-8")
        try:
            import stat
            CRED_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except Exception:
            pass

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
            ok = info["bago_provider"] in active
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
