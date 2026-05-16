
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
        "github":    {"env": "GITHUB_TOKEN",    "bago_provider": "copilot",
                      "desc": "GitHub Copilot", "login_type": "gh_cli"},
        "openai":    {"env": "OPENAI_API_KEY",  "bago_provider": "codex",
                      "desc": "OpenAI / GPT Plus (sin API key si tienes Plus)",
                      "login_type": "openai_cli"},
        "anthropic": {"env": "ANTHROPIC_API_KEY","bago_provider": "anthropic",
                      "desc": "Anthropic / Claude", "login_type": "api_key"},
        "ollama":    {"env": None,              "bago_provider": "ollama-local",
                      "desc": "Ollama local (sin clave)", "login_type": "service"},
    }
    ALIASES = {"gpt":"openai","codex":"openai","claude":"anthropic","claw":"anthropic",
               "copilot":"github","gh":"github","local":"ollama"}

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
            elif name == "openai":
                # Activo si: API key en env, O codex CLI autenticado, O chatgpt CLI autenticado
                if (os.environ.get("OPENAI_API_KEY") or
                        self._codex_authed() or self._chatgpt_authed()):
                    active.append("codex")
            else:
                env_key = info.get("env")
                if env_key and os.environ.get(env_key):
                    active.append(info["bago_provider"])
        return active

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
                elif self._chatgpt_authed():
                    status = "[green]✓ chatgpt login (GPT Plus)[/green]"
                else:
                    status = "[red]✗ sin credencial[/red]"
            else:
                env_key = info.get("env")
                val = os.environ.get(env_key, "") if env_key else ""
                if val:
                    masked = val[:4] + "…" + val[-4:] if len(val) > 8 else "●●●"
                    status = f"[green]✓ {masked}[/green]"
                else:
                    status = "[red]✗ sin credencial[/red]"
            t.add_row(name, status, info["desc"])
        t.add_row("[dim]/login <provider>[/dim]","","[dim]para registrar[/dim]")
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
            # GPT Plus: intentar auth via codex CLI o chatgpt CLI (sin API key)
            console.print(
                "[bold]OpenAI / GPT — elige método:[/bold]\n"
                "  [yellow]1[/yellow]  codex login    (GPT Plus — abre navegador, sin API key)\n"
                "  [yellow]2[/yellow]  chatgpt login  (ChatGPT app — abre navegador)\n"
                "  [yellow]3[/yellow]  API key        (pegar clave manual)\n"
            )
            choice = pt_prompt("Opción [1/2/3]: ").strip()

            if choice == "1":
                console.print("[dim]Ejecutando codex login...[/dim]")
                result = subprocess.run(["codex", "login"])
                if result.returncode == 0:
                    # Marcar que codex está autenticado (sin guardar key en credentials.json)
                    self._creds["openai_via"] = "codex_login"
                    self._save()
                    return "[green]✓ Codex CLI autenticado (GPT Plus activo)[/green]"
                return "[red]codex login fallido.[/red]"

            elif choice == "2":
                console.print("[dim]Ejecutando chatgpt...[/dim]")
                result = subprocess.run(["chatgpt"])
                if result.returncode == 0:
                    self._creds["openai_via"] = "chatgpt_login"
                    self._save()
                    return "[green]✓ ChatGPT CLI autenticado (GPT Plus activo)[/green]"
                return "[red]chatgpt login fallido.[/red]"

            else:  # opción 3 o cualquier otra: API key manual
                key = pt_prompt("OpenAI API Key: ", is_password=True).strip()
                if not key:
                    return "Cancelado."
                self.set("openai", key)
                return "[green]✓ OpenAI API key guardada.[/green]"

        elif ltype == "api_key":
            key = pt_prompt(f"{info['desc']} API Key: ", is_password=True).strip()
            if not key:
                return "Cancelado."
            self.set(name, key)
            return f"[green]✓ {info['desc']} API key guardada.[/green]"

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
