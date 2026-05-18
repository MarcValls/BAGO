
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

from prompt_toolkit import prompt as pt_prompt
from rich import box
from rich.table import Table

from .constants import ACCOUNTS_FILE, CRED_FILE
from .ui import console


# ── AccountManager ─────────────────────────────────────────────────────────────

class AccountManager:
    """Gestiona múltiples cuentas/tokens por tipo de proveedor.

    Almacena en ~/.bago/accounts.json:
    {
      "accounts": [
        {"id": "github-1", "provider": "github", "label": "Personal",
         "credential_type": "token", "credential": "ghp_...",
         "enabled": true, "created_at": "2025-01-01T12:00:00"},
        ...
      ],
      "active": {"github": "github-2", "gemini": "gemini-1"}
    }

    Uso básico:
        am = AccountManager(ACCOUNTS_FILE)
        am.add("github", "Trabajo", "ghp_xxx")   # → "github-2"
        am.set_active("github-2")
        am.apply_active_credentials()             # → os.environ["GITHUB_TOKEN"] = ...
    """

    # Tipos de proveedor soportados: tipo → variable de entorno
    PROVIDER_ENV = {
        "github":       "GITHUB_TOKEN",
        "openai":       "OPENAI_API_KEY",
        "anthropic":    "ANTHROPIC_API_KEY",
        "openrouter":   "OPENROUTER_API_KEY",
        "gemini":       "GEMINI_API_KEY",
        "ollama_cloud": "OLLAMA_CLOUD_API_KEY",
    }

    PROVIDER_LABELS = {
        "github":       "GitHub (Copilot + Models)",
        "openai":       "OpenAI / ChatGPT",
        "anthropic":    "Anthropic Claude",
        "openrouter":   "OpenRouter",
        "gemini":       "Google Gemini",
        "ollama_cloud": "Ollama Cloud",
    }

    def __init__(self, accounts_file: Path):
        self._file = accounts_file
        self._data: dict = {"accounts": [], "active": {}}
        self._load()

    # ── I/O ────────────────────────────────────────────────────────────────────

    def _load(self):
        if self._file.exists():
            try:
                self._data = json.loads(self._file.read_text(encoding="utf-8"))
            except Exception:
                self._data = {"accounts": [], "active": {}}

    def _save(self):
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._file.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        try:
            import stat
            self._file.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except Exception:
            pass

    # ── Queries ─────────────────────────────────────────────────────────────────

    @property
    def accounts(self) -> list:
        return self._data.get("accounts", [])

    def find(self, account_id: str) -> dict | None:
        for a in self.accounts:
            if a["id"] == account_id:
                return a
        return None

    def accounts_for(self, provider: str) -> list:
        return [a for a in self.accounts if a["provider"] == provider]

    def get_active_id(self, provider: str) -> str | None:
        return self._data.get("active", {}).get(provider)

    def get_active(self, provider: str) -> dict | None:
        aid = self.get_active_id(provider)
        return self.find(aid) if aid else None

    def all_providers(self) -> list[str]:
        """Lista de tipos de provider con al menos una cuenta registrada."""
        return list({a["provider"] for a in self.accounts})

    # ── Mutations ───────────────────────────────────────────────────────────────

    def add(
        self,
        provider: str,
        label: str,
        credential: str,
        credential_type: str = "api_key",
        make_active: bool = True,
    ) -> str:
        """Agrega una cuenta nueva. Devuelve el ID asignado (ej: 'github-2')."""
        existing_ids = {a["id"] for a in self.accounts}
        i = 1
        while f"{provider}-{i}" in existing_ids:
            i += 1
        account_id = f"{provider}-{i}"

        auto_label = f"{self.PROVIDER_LABELS.get(provider, provider)} #{i}"
        account = {
            "id":              account_id,
            "provider":        provider,
            "label":           label or auto_label,
            "credential_type": credential_type,
            "credential":      credential,
            "enabled":         True,
            "created_at":      datetime.now().isoformat(timespec="seconds"),
        }
        self._data.setdefault("accounts", []).append(account)
        if make_active or not self.get_active_id(provider):
            self._data.setdefault("active", {})[provider] = account_id
        self._save()
        return account_id

    def update(self, account_id: str, **kwargs) -> bool:
        """Actualiza campos de una cuenta (label, credential, enabled…)."""
        acc = self.find(account_id)
        if not acc:
            return False
        for k, v in kwargs.items():
            acc[k] = v
        self._save()
        return True

    def remove(self, account_id: str) -> bool:
        """Elimina una cuenta. Si era la activa, promueve la siguiente."""
        acc = self.find(account_id)
        if not acc:
            return False
        provider = acc["provider"]
        self._data["accounts"] = [a for a in self.accounts if a["id"] != account_id]
        # Reasignar activo si era la cuenta activa
        if self._data.get("active", {}).get(provider) == account_id:
            remaining = self.accounts_for(provider)
            if remaining:
                self._data["active"][provider] = remaining[0]["id"]
            else:
                self._data.get("active", {}).pop(provider, None)
        self._save()
        return True

    def set_active(self, account_id: str) -> bool:
        """Establece una cuenta como activa para su tipo de proveedor."""
        acc = self.find(account_id)
        if not acc:
            return False
        acc["enabled"] = True
        self._data.setdefault("active", {})[acc["provider"]] = account_id
        self._save()
        return True

    # ── Integración con el entorno ──────────────────────────────────────────────

    def apply_active_credentials(self):
        """Aplica las credenciales de las cuentas activas a variables de entorno."""
        for provider, env_key in self.PROVIDER_ENV.items():
            active = self.get_active(provider)
            if active and active.get("enabled") and active.get("credential"):
                os.environ[env_key] = active["credential"]

    def import_from_creds(self, creds_dict: dict):
        """Importa credenciales existentes de credentials.json como cuentas base.

        Solo importa un proveedor si no tiene ninguna cuenta registrada todavía.
        """
        mapping = {
            "github":       ("github",       "GITHUB_TOKEN",        "token"),
            "openai":       ("openai",        "OPENAI_API_KEY",      "api_key"),
            "anthropic":    ("anthropic",     "ANTHROPIC_API_KEY",   "api_key"),
            "openrouter":   ("openrouter",    "OPENROUTER_API_KEY",  "api_key"),
            "ollama_cloud": ("ollama_cloud",  "OLLAMA_CLOUD_API_KEY","api_key"),
        }
        for cred_key, (provider, env_key, ctype) in mapping.items():
            if self.accounts_for(provider):
                continue  # ya tiene cuentas — no sobreescribir
            value = creds_dict.get(cred_key) or os.environ.get(env_key, "")
            if value:
                self.add(
                    provider=provider,
                    label=f"{self.PROVIDER_LABELS.get(provider, provider)} (migrado)",
                    credential=value,
                    credential_type=ctype,
                    make_active=True,
                )

    # ── Representación ──────────────────────────────────────────────────────────

    def summary_lines(self) -> list[str]:
        """Líneas de texto para mostrar en /scan o /status."""
        if not self.accounts:
            return ["  [dim](sin cuentas registradas — usa /login add <provider>)[/dim]"]
        lines = []
        for provider in sorted(self.all_providers()):
            accs = self.accounts_for(provider)
            active_id = self.get_active_id(provider)
            plabel = self.PROVIDER_LABELS.get(provider, provider)
            lines.append(f"  [bold]{plabel}[/bold]  [dim]({len(accs)} cuenta{'s' if len(accs)!=1 else ''})[/dim]")
            for acc in accs:
                is_active = acc["id"] == active_id
                star = "[bold yellow]★[/bold yellow]" if is_active else "  "
                cred = acc.get("credential", "")
                masked = f"{cred[:4]}…{cred[-4:]}" if len(cred) > 8 else "●●●"
                label = acc.get("label", acc["id"])
                status_color = "green" if is_active and acc.get("enabled") else "dim"
                lines.append(
                    f"    {star} [{status_color}]{acc['id']:<16}[/{status_color}]"
                    f"  [{status_color}]{label:<28}[/{status_color}]"
                    f"  [dim]{masked}[/dim]"
                )
        return lines


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
        "gemini":    {"env": "GEMINI_API_KEY",        "bago_provider": "gemini",
                      "desc": "Google Gemini (Gemini 2.0, Flash, Pro...)",
                      "login_type": "api_key",
                      "url": "https://aistudio.google.com/app/apikey"},
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
        "google": "gemini", "flash": "gemini",
        "hermes": "openrouter",
        "mixtral": "openrouter",
        "llama": "openrouter",
        "cloud": "ollama_cloud",
    }

    def __init__(self):
        self._creds = {}
        self._load()
        self._apply_env()
        # ── Multi-account manager ──────────────────────────────────────────
        self._accounts = AccountManager(ACCOUNTS_FILE)
        self._accounts.import_from_creds(self._creds)  # migra si es la primera vez
        self._accounts.apply_active_credentials()      # cuentas activas sobreescriben env

    @property
    def account_manager(self) -> AccountManager:
        return self._accounts

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

    def do_login(self, alias: str) -> str:
        """Registra/gestiona credenciales de providers.

        Subcomandos multi-cuenta:
          add <provider> [alias-nombre]  — agrega una cuenta nueva
          list                           — lista todas las cuentas
          switch <account-id>            — activa una cuenta
          remove <account-id>            — elimina una cuenta
          <provider>                     — flujo clásico (reemplaza la 1ª cuenta)
        """
        parts = alias.strip().split(None, 2)
        sub = parts[0].lower() if parts else ""

        # ── Subcomando: list ────────────────────────────────────────────────────
        if sub == "list":
            lines = self._accounts.summary_lines()
            console.print("\n[bold]Cuentas registradas:[/bold]")
            for l in lines:
                console.print(l)
            console.print(
                "\n[dim]  /login add <provider> [nombre]  — agregar cuenta nueva"
                "\n  /login switch <id>               — activar cuenta"
                "\n  /login remove <id>               — eliminar cuenta[/dim]"
            )
            return ""

        # ── Subcomando: switch ──────────────────────────────────────────────────
        if sub == "switch":
            if len(parts) < 2:
                return "[red]Uso: /login switch <account-id>  (ej: github-2)[/red]"
            account_id = parts[1]
            if self._accounts.set_active(account_id):
                self._accounts.apply_active_credentials()
                acc = self._accounts.find(account_id)
                label = acc.get("label", account_id) if acc else account_id
                return f"[green]✓ Cuenta activa: {account_id} — {label}[/green]"
            return f"[red]Cuenta '{account_id}' no encontrada. Usa /login list para ver las disponibles.[/red]"

        # ── Subcomando: remove ──────────────────────────────────────────────────
        if sub == "remove":
            if len(parts) < 2:
                return "[red]Uso: /login remove <account-id>  (ej: github-2)[/red]"
            account_id = parts[1]
            if self._accounts.remove(account_id):
                self._accounts.apply_active_credentials()
                return f"[green]✓ Cuenta '{account_id}' eliminada.[/green]"
            return f"[red]Cuenta '{account_id}' no encontrada.[/red]"

        # ── Subcomando: add ─────────────────────────────────────────────────────
        if sub == "add":
            if len(parts) < 2:
                return (
                    "[red]Uso: /login add <provider> [nombre][/red]\n"
                    "[dim]  Providers: github, openai, anthropic, openrouter, gemini, ollama_cloud[/dim]"
                )
            provider_raw = parts[1].lower()
            custom_label = parts[2] if len(parts) > 2 else ""
            # Resolver alias
            provider = self.ALIASES.get(provider_raw, provider_raw)
            # Mapear bago_provider a tipo AccountManager
            am_provider = self._bago_to_am_provider(provider)
            if am_provider not in AccountManager.PROVIDER_ENV and am_provider != "ollama":
                return f"[red]Provider '{provider_raw}' no soportado para multi-cuenta.[/red]"
            return self._do_add_account(am_provider, custom_label)

        # ── Flujo clásico: /login <provider> ────────────────────────────────────
        name = self.ALIASES.get(alias.lower(), alias.lower())
        info = self.PROVIDERS.get(name)
        if not info:
            return (
                f"Provider '{alias}' desconocido.\n"
                f"  Providers: {', '.join(self.PROVIDERS)}\n"
                f"  Subcomandos: add · list · switch · remove"
            )

        ltype = info["login_type"]
        if ltype == "gh_cli":
            console.print(f"[dim]Ejecutando gh auth login...[/dim]")
            result = subprocess.run(["gh", "auth", "login"])
            if result.returncode != 0:
                return "Login GitHub fallido."
            try:
                token = subprocess.check_output(["gh", "auth", "token"], text=True).strip()
                self.set("github", token)
                # Actualizar o crear cuenta en AccountManager
                existing = self._accounts.accounts_for("github")
                if existing:
                    self._accounts.update(existing[0]["id"], credential=token)
                else:
                    self._accounts.add("github", "GitHub Personal", token, "token")
                self._accounts.apply_active_credentials()
                return f"[green]✓ GitHub token guardado ({token[:4]}…{token[-4:]})[/green]"
            except Exception as e:
                return f"Token obtenido pero no guardado: {e}"

        elif ltype == "openai_cli":
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

            else:
                console.print("[dim]Obtén tu clave en: https://platform.openai.com/api-keys[/dim]")
                key = pt_prompt("OpenAI API Key: ", is_password=True).strip()
                if not key:
                    return "Cancelado."
                self.set("openai", key)
                existing = self._accounts.accounts_for("openai")
                if existing:
                    self._accounts.update(existing[0]["id"], credential=key)
                else:
                    self._accounts.add("openai", "OpenAI Principal", key, "api_key")
                self._accounts.apply_active_credentials()
                return "[green]✓ OpenAI API key guardada.[/green]"

        elif ltype == "api_key":
            url = info.get("url", "")
            url_hint = f"[dim]Obtén tu clave en: {url}[/dim]\n" if url else ""
            console.print(url_hint + f"[bold]{info['desc']}[/bold]")
            key = pt_prompt(f"API Key: ", is_password=True).strip()
            if not key:
                return "Cancelado."
            self.set(name, key)
            am_provider = self._bago_to_am_provider(name)
            if am_provider in AccountManager.PROVIDER_ENV:
                existing = self._accounts.accounts_for(am_provider)
                if existing:
                    self._accounts.update(existing[0]["id"], credential=key)
                else:
                    self._accounts.add(am_provider, info["desc"], key, "api_key")
                self._accounts.apply_active_credentials()
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
                existing = self._accounts.accounts_for("ollama_cloud")
                if existing:
                    self._accounts.update(existing[0]["id"], credential=key)
                else:
                    self._accounts.add("ollama_cloud", "Ollama Cloud", key, "api_key")
                self._accounts.apply_active_credentials()
                return "[green]✓ Ollama Cloud API key guardada.[/green]"

        elif ltype == "opencode_cli":
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

    def _bago_to_am_provider(self, name: str) -> str:
        """Convierte nombre de CredentialManager a tipo de AccountManager."""
        mapping = {
            "github":      "github",
            "openai":      "openai",
            "anthropic":   "anthropic",
            "openrouter":  "openrouter",
            "gemini":      "gemini",
            "ollama_cloud":"ollama_cloud",
        }
        return mapping.get(name, name)

    def _do_add_account(self, provider: str, custom_label: str = "") -> str:
        """Flujo interactivo para agregar una cuenta nueva de cualquier provider."""
        am = self._accounts
        existing = am.accounts_for(provider)
        n_existing = len(existing)
        plabel = AccountManager.PROVIDER_LABELS.get(provider, provider)

        console.print(
            f"\n[bold]Agregar cuenta nueva — {plabel}[/bold]"
            + (f"\n[dim]  Ya tienes {n_existing} cuenta{'s' if n_existing!=1 else ''} de este tipo.[/dim]"
               if n_existing > 0 else "")
        )

        # Pedir nombre/etiqueta
        if not custom_label:
            default_label = f"{plabel} #{n_existing + 1}"
            raw = pt_prompt(f"Nombre/etiqueta [{default_label}]: ").strip()
            label = raw or default_label
        else:
            label = custom_label

        if provider == "github":
            console.print("[dim]Ejecutando gh auth login...[/dim]")
            result = subprocess.run(["gh", "auth", "login"])
            if result.returncode != 0:
                return "[red]gh auth login fallido.[/red]"
            try:
                token = subprocess.check_output(["gh", "auth", "token"], text=True).strip()
                account_id = am.add("github", label, token, "token", make_active=True)
                am.apply_active_credentials()
                return f"[green]✓ Cuenta añadida: {account_id} — {label}  ({token[:4]}…{token[-4:]})[/green]"
            except Exception as e:
                return f"[red]Error obteniendo token: {e}[/red]"

        elif provider == "openai":
            console.print(
                "[bold]OpenAI / GPT — elige método:[/bold]\n"
                "  [yellow]1[/yellow]  codex login  (GPT Plus — abre navegador)\n"
                "  [yellow]2[/yellow]  API key      (platform.openai.com)\n"
            )
            choice = pt_prompt("Opción [1/2]: ").strip()
            if choice == "1":
                result = subprocess.run(["codex", "login"])
                if result.returncode == 0:
                    account_id = am.add("openai", label, "__codex_oauth__", "oauth", make_active=True)
                    return f"[green]✓ Cuenta añadida: {account_id} — {label} (codex OAuth)[/green]"
                return "[red]codex login fallido.[/red]"
            else:
                key = pt_prompt("OpenAI API Key: ", is_password=True).strip()
                if not key:
                    return "Cancelado."
                account_id = am.add("openai", label, key, "api_key", make_active=True)
                am.apply_active_credentials()
                return f"[green]✓ Cuenta añadida: {account_id} — {label}[/green]"

        else:
            # Genérico: pedir API key
            url = self.PROVIDERS.get(provider, {}).get("url", "")
            if url:
                console.print(f"[dim]Obtén tu clave en: {url}[/dim]")
            key = pt_prompt(f"API Key para {label}: ", is_password=True).strip()
            if not key:
                return "Cancelado."
            account_id = am.add(provider, label, key, "api_key", make_active=True)
            am.apply_active_credentials()
            return f"[green]✓ Cuenta añadida: {account_id} — {label}[/green]"

