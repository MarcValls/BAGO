
import json
import os
import subprocess
from pathlib import Path

from prompt_toolkit import prompt as pt_prompt
from rich import box
from rich.table import Table

from .constants import CRED_FILE
from .ui import console

class CredentialManager:
    """Gestiona credenciales de todos los proveedores. /login para registrar."""
    PROVIDERS = {
        # ── Proveedores originales ──────────────────────────────────────────
        "github":    {"env": "GITHUB_TOKEN",         "bago_provider": "copilot",
                      "desc": "GitHub Copilot",       "login_type": "gh_cli"},
        "openai":    {"env": "OPENAI_API_KEY",        "bago_provider": "codex",
                      "desc": "OpenAI / GPT Plus (codex login o API key)",
                      "login_type": "openai_cli"},
        "anthropic": {"env": "ANTHROPIC_API_KEY",     "bago_provider": "anthropic",
                      "desc": "Anthropic Claude / Claw (API key)",
                      "login_type": "api_key",
                      "url": "https://console.anthropic.com/keys"},
        "ollama":    {"env": None,                    "bago_provider": "ollama-local",
                      "desc": "Ollama local (sin clave)", "login_type": "service"},
        # ── Proveedores nuevos ─────────────────────────────────────────────
        "ollama_cloud": {"env": "OLLAMA_CLOUD_API_KEY", "bago_provider": "ollama-cloud",
                         "desc": "Ollama Cloud (ollama.com — signin o API key)",
                         "login_type": "ollama_cloud",
                         "url": "https://ollama.com/settings/api"},
        "opencode":  {"env": None,                    "bago_provider": "opencode",
                      "desc": "OpenCode AI (asistente de codigo con IA)",
                      "login_type": "opencode_cli"},
        "openrouter":{"env": "OPENROUTER_API_KEY",    "bago_provider": "openrouter",
                      "desc": "OpenRouter — Hermes, Mixtral, Llama, DeepSeek y mas",
                      "login_type": "api_key",
                      "url": "https://openrouter.ai/keys"},
    }
    ALIASES = {
        "gpt": "openai", "codex": "openai",
        "claude": "anthropic", "claw": "anthropic",
        "copilot": "github", "gh": "github",
        "local": "ollama",
        "hermes": "openrouter",   # Hermes vía OpenRouter
        "mixtral": "openrouter",  # otros modelos via OpenRouter
        "llama": "openrouter",
        "cloud": "ollama_cloud",
    }

    def __init__(self):
        self._creds = {}
        self._load()
        self._apply_env()

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
        for name, info in self.PROVIDERS.items():
            env_key = info.get("env")
            if env_key and not os.environ.get(env_key):
                saved = self._creds.get(name)
                if saved:
                    os.environ[env_key] = saved

    def set(self, provider_name, key):
        self._creds[provider_name] = key
        env_key = self.PROVIDERS.get(provider_name, {}).get("env")
        if env_key:
            os.environ[env_key] = key
        self._save()

    def _ollama_ok(self):
        """Detecta si Ollama está disponible buscando en múltiples ubicaciones."""
        try:
            from .providers import discover_ollama_url
            url = discover_ollama_url(timeout=2)
            return url is not None
        except Exception:
            # Fallback: CLI directo
            import subprocess
            try:
                subprocess.check_output(["ollama", "list"], stderr=subprocess.DEVNULL, timeout=4)
                return True
            except Exception:
                return False

    def _codex_authed(self):
        """True si codex CLI tiene sesión activa (GPT Plus sin API key)."""
        # Marcador guardado por /login openai opción 1
        if self._creds.get("openai_via") in ("codex_login", "chatgpt_login"):
            return True
        try:
            codex_state = Path.home() / ".codex"
            for f in codex_state.glob("*.json"):
                try:
                    data = json.loads(f.read_text())
                    if data.get("accessToken") or data.get("token") or data.get("auth"):
                        return True
                except Exception:
                    pass
            return False
        except Exception:
            return False

    def _chatgpt_authed(self):
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

    def active_bago_providers(self):
        """Devuelve lista de bago_provider strings que tienen credenciales activas."""
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
                if (os.environ.get("OPENAI_API_KEY") or self._codex_authed()):
                    active.append("codex")
            elif name == "opencode":
                if self._creds.get("opencode_via"):
                    active.append("opencode")
            else:
                env_key = info.get("env")
                if env_key and os.environ.get(env_key):
                    active.append(info["bago_provider"])
        return active

    def login_choices(self):
        """Devuelve lista (name, label) con estado plain-text para _menu_pick."""
        active = self.active_bago_providers()
        out = []
        for name, info in self.PROVIDERS.items():
            bp = info["bago_provider"]
            ok = bp in active
            mark = "\u2713" if ok else "\u00b7"  # ✓ · 
            if name == "github":
                tok = os.environ.get("GITHUB_TOKEN", "")
                state = f"{tok[:8]}..." if tok else "sin credencial"
            elif name == "openai":
                k = os.environ.get("OPENAI_API_KEY", "")
                if k:
                    state = f"API key {k[:4]}\u2026" if len(k) > 4 else "API key"
                elif ok:
                    state = "codex login (GPT Plus)"
                else:
                    state = "sin credencial"
            elif name == "ollama":
                state = "activo" if ok else "no disponible"
            elif name == "ollama_cloud":
                k = os.environ.get("OLLAMA_CLOUD_API_KEY", "")
                if k:
                    state = f"API key {k[:4]}\u2026" if len(k) > 4 else "API key"
                elif ok:
                    state = "ollama signin"
                else:
                    state = "sin credencial"
            elif name == "opencode":
                state = self._creds.get("opencode_via") or "sin auth"
            else:
                env_key = info.get("env")
                val = os.environ.get(env_key, "") if env_key else ""
                state = (f"{val[:4]}\u2026" if len(val) > 4 else "activo") if val else "sin credencial"
            label = f"{name:<14} {mark}  {state:<26}  {info['desc']}"
            out.append((name, label))
        return out

    def status_table(self):
        t = Table(box=box.SIMPLE, show_header=True, header_style="bold")
        t.add_column("Provider"); t.add_column("Estado"); t.add_column("Descripcion")
        for name, info in self.PROVIDERS.items():
            if name == "ollama":
                ok = self._ollama_ok()
                status = "[green]✓ activo[/green]" if ok else "[red]✗ no disponible[/red]"
            elif name == "openai":
                if os.environ.get("OPENAI_API_KEY"):
                    k = os.environ["OPENAI_API_KEY"]
                    masked = k[:4] + "…" + k[-4:] if len(k) > 8 else "●●●"
                    status = f"[green]✓ API key {masked}[/green]"
                elif self._codex_authed():
                    status = "[green]✓ codex login (GPT Plus)[/green]"
                else:
                    status = "[red]✗ sin credencial[/red]"
            elif name == "ollama_cloud":
                if os.environ.get("OLLAMA_CLOUD_API_KEY"):
                    k = os.environ["OLLAMA_CLOUD_API_KEY"]
                    masked = k[:4] + "…" + k[-4:] if len(k) > 8 else "●●●"
                    status = f"[green]✓ API key {masked}[/green]"
                elif self._creds.get("ollama_cloud_via") == "ollama_signin":
                    status = "[green]✓ ollama signin (cuenta ollama.com)[/green]"
                else:
                    status = "[red]✗ sin credencial[/red]"
            elif name == "opencode":
                via = self._creds.get("opencode_via")
                status = (f"[green]✓ {via}[/green]" if via
                          else "[red]✗ no instalado / sin auth[/red]")
            else:
                env_key = info.get("env")
                val = os.environ.get(env_key, "") if env_key else ""
                if val:
                    masked = val[:4] + "…" + val[-4:] if len(val) > 8 else "●●●"
                    status = f"[green]✓ {masked}[/green]"
                else:
                    status = "[red]✗ sin credencial[/red]"
            t.add_row(name, status, info["desc"])
        t.add_row("[dim]/login <provider>[/dim]", "", "[dim]para registrar[/dim]")
        return t

    def do_login(self, alias):
        name = self.ALIASES.get(alias.lower(), alias.lower())
        info = self.PROVIDERS.get(name)
        if not info:
            return f"Provider '{alias}' desconocido. Opciones: {', '.join(self.PROVIDERS)}"

        ltype = info["login_type"]
        if ltype == "gh_cli":
            console.print(f"[dim]Ejecutando gh auth login...[/dim]")
            result = subprocess.run(["gh", "auth", "login"])
            if result.returncode != 0:
                return "Login GitHub fallido."
            try:
                token = subprocess.check_output(["gh", "auth", "token"], text=True).strip()
                self.set("github", token)
                return f"[green]✓ GitHub token guardado ({token[:4]}…{token[-4:]})[/green]"
            except Exception as e:
                return f"Token obtenido pero no guardado: {e}"

        elif ltype == "openai_cli":
            # GPT Plus: codex CLI (sin API key) o API key manual
            console.print(
                "[bold]OpenAI / GPT — elige método:[/bold]\n"
                "  [yellow]1[/yellow]  codex login  (GPT Plus — abre navegador, sin API key)\n"
                "  [yellow]2[/yellow]  API key      (pegar clave desde platform.openai.com)\n"
            )
            choice = pt_prompt("Opción [1/2]: ").strip()

            if choice == "1":
                console.print("[dim]Ejecutando codex login (abre navegador para autenticar)...[/dim]")
                result = subprocess.run(["codex", "login"])
                if result.returncode == 0:
                    self._creds["openai_via"] = "codex_login"
                    self._save()
                    return "[green]✓ Codex CLI autenticado (GPT Plus activo)[/green]"
                return "[red]codex login fallido. Prueba la opción 2 con API key.[/red]"

            else:  # opción 2 o cualquier otra: API key manual
                console.print("[dim]Obtén tu clave en: https://platform.openai.com/api-keys[/dim]")
                key = pt_prompt("OpenAI API Key: ", is_password=True).strip()
                if not key:
                    return "Cancelado."
                self.set("openai", key)
                return "[green]✓ OpenAI API key guardada.[/green]"

        elif ltype == "api_key":
            url = info.get("url", "")
            url_hint = f"[dim]Obtén tu clave en: {url}[/dim]\n" if url else ""
            console.print(url_hint + f"[bold]{info['desc']}[/bold]")
            key = pt_prompt(f"API Key: ", is_password=True).strip()
            if not key:
                return "Cancelado."
            self.set(name, key)
            return f"[green]✓ {info['desc']} — API key guardada.[/green]"

        elif ltype == "ollama_cloud":
            console.print(
                "[bold]Ollama Cloud — elige método:[/bold]\n"
                "  [yellow]1[/yellow]  ollama signin  (login con tu cuenta ollama.com)\n"
                "  [yellow]2[/yellow]  API key        (desde ollama.com/settings/api)\n"
            )
            choice = pt_prompt("Opción [1/2]: ").strip()
            if choice == "1":
                console.print("[dim]Ejecutando ollama signin...[/dim]")
                result = subprocess.run(["ollama", "signin"])
                if result.returncode == 0:
                    self._creds["ollama_cloud_via"] = "ollama_signin"
                    self._save()
                    return "[green]✓ Ollama Cloud autenticado con ollama signin.[/green]"
                return "[red]ollama signin fallido. Prueba la opción 2 con API key.[/red]"
            else:
                console.print("[dim]Obtén tu clave en: https://ollama.com/settings/api[/dim]")
                key = pt_prompt("Ollama Cloud API Key: ", is_password=True).strip()
                if not key:
                    return "Cancelado."
                self.set("ollama_cloud", key)
                return "[green]✓ Ollama Cloud API key guardada.[/green]"

        elif ltype == "opencode_cli":
            # Verificar si opencode está instalado
            try:
                subprocess.check_output(["opencode", "--version"],
                                         stderr=subprocess.DEVNULL, timeout=5)
                opencode_ok = True
            except Exception:
                opencode_ok = False

            if not opencode_ok:
                console.print(
                    "[bold yellow]OpenCode no está instalado.[/bold yellow]\n"
                    "[dim]Instala con:[/dim]  npm install -g opencode-ai\n"
                    "[dim]Más info:[/dim]    https://opencode.ai\n"
                )
                install = pt_prompt("¿Instalar ahora? [s/n]: ").strip().lower()
                if install == "s":
                    console.print("[dim]Ejecutando npm install -g opencode-ai...[/dim]")
                    r = subprocess.run(["npm", "install", "-g", "opencode-ai"])
                    if r.returncode != 0:
                        return "[red]Instalación fallida. Instala manualmente: npm install -g opencode-ai[/red]"
                    console.print("[green]✓ opencode instalado.[/green]")
                else:
                    return "Cancelado. Instala opencode manualmente."

            console.print("[dim]Ejecutando opencode auth login...[/dim]")
            result = subprocess.run(["opencode", "auth", "login"])
            if result.returncode == 0:
                self._creds["opencode_via"] = "opencode_login"
                self._save()
                return "[green]✓ OpenCode autenticado.[/green]"
            # Si el comando auth no existe, intentar solo ejecutarlo
            self._creds["opencode_via"] = "opencode_installed"
            self._save()
            return "[green]✓ OpenCode instalado y marcado como activo.[/green]"

        elif ltype == "service":
            if self._ollama_ok():
                try:
                    out = subprocess.check_output(["ollama", "list"], text=True,
                                                  stderr=subprocess.DEVNULL)
                    console.print(out)
                    return "[green]✓ Ollama activo y disponible.[/green]"
                except Exception:
                    pass
            return "[red]Ollama no disponible. Instala desde https://ollama.com[/red]"
