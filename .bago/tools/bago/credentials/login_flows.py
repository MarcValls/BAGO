"""LoginFlowsMixin — flujos interactivos de /login para CredentialManager.

Separado de manager.py para mantener la lógica de UI aislada del estado.
Se mezcla con CredentialManager mediante herencia múltiple.
"""

import subprocess

from prompt_toolkit import prompt as pt_prompt

from ..ui import console
from .accounts import AccountManager
from .flows import (
    flow_github,
    flow_openai,
    flow_ollama_cloud,
    flow_ollama_service,
    flow_opencode,
    flow_gittoken,
    flow_api_key,
    flow_huggingface,
    flow_sendcm,
)


class LoginFlowsMixin:
    """Métodos interactivos de /login. Requiere que self tenga:
    - self._accounts (AccountManager)
    - self._creds (dict)
    - self._save()
    - self.set(provider, key)
    - self.PROVIDERS / self.ALIASES
    """

    def do_login(self, alias: str) -> str:
        """Registra/gestiona credenciales.

        Subcomandos multi-cuenta:
          list                           — lista todas las cuentas
          switch <account-id>            — activa una cuenta
          remove <account-id>            — elimina una cuenta
          add <provider> [nombre]        — agrega una cuenta nueva
          <provider>                     — flujo clásico (reemplaza la 1ª cuenta)
        """
        parts = alias.strip().split(None, 2)
        sub = parts[0].lower() if parts else ""

        if sub == "list":
            return self._login_list()
        if sub == "switch":
            return self._login_switch(parts)
        if sub == "remove":
            return self._login_remove(parts)
        if sub == "add":
            return self._login_add(parts)

        # ── Flujo clásico ────────────────────────────────────────────────────
        name = self.ALIASES.get(alias.lower(), alias.lower())
        info = self.PROVIDERS.get(name)
        if not info:
            return (
                f"Provider '{alias}' desconocido.\n"
                f"  Providers: {', '.join(self.PROVIDERS)}\n"
                f"  Subcomandos: add · list · switch · remove"
            )
        return self._login_classic(name, info)

    # ── Subcomandos multi-cuenta ─────────────────────────────────────────────

    def _login_list(self) -> str:
        lines = self._accounts.summary_lines()
        console.print("\n[bold]Cuentas registradas:[/bold]")
        for line in lines:
            console.print(line)
        console.print(
            "\n[dim]  /login add <provider> [nombre]  — agregar cuenta nueva"
            "\n  /login switch <id>               — activar cuenta"
            "\n  /login remove <id>               — eliminar cuenta[/dim]"
        )
        return ""

    def _login_switch(self, parts: list) -> str:
        if len(parts) < 2:
            return "[red]Uso: /login switch <account-id>  (ej: github-2)[/red]"
        account_id = parts[1]
        if self._accounts.set_active(account_id):
            self._accounts.apply_active_credentials()
            acc = self._accounts.find(account_id)
            label = acc.get("label", account_id) if acc else account_id
            return f"[green]✓ Cuenta activa: {account_id} — {label}[/green]"
        return (
            f"[red]Cuenta '{account_id}' no encontrada. "
            f"Usa /login list para ver las disponibles.[/red]"
        )

    def _login_remove(self, parts: list) -> str:
        if len(parts) < 2:
            return "[red]Uso: /login remove <account-id>  (ej: github-2)[/red]"
        account_id = parts[1]
        if self._accounts.remove(account_id):
            self._accounts.apply_active_credentials()
            return f"[green]✓ Cuenta '{account_id}' eliminada.[/green]"
        return f"[red]Cuenta '{account_id}' no encontrada.[/red]"

    def _login_add(self, parts: list) -> str:
        if len(parts) < 2:
            return (
                "[red]Uso: /login add <provider> [nombre][/red]\n"
                "[dim]  Providers: github, openai, anthropic, openrouter, gemini, ollama_cloud[/dim]"
            )
        provider_raw = parts[1].lower()
        custom_label = parts[2] if len(parts) > 2 else ""
        provider = self.ALIASES.get(provider_raw, provider_raw)
        am_provider = self._bago_to_am_provider(provider)
        if am_provider not in AccountManager.PROVIDER_ENV and am_provider != "ollama":
            return f"[red]Provider '{provider_raw}' no soportado para multi-cuenta.[/red]"
        return self._do_add_account(am_provider, custom_label)

    # ── Flujo clásico por tipo de login ─────────────────────────────────────

    def _login_classic(self, name: str, info: dict) -> str:
        ltype = info["login_type"]
        if ltype == "github":
            return self._flow_github()
        if ltype == "gh_cli":          # alias legacy
            return self._flow_github()
        if ltype == "openai_cli":
            return self._flow_openai()
        if ltype == "api_key":
            return self._flow_api_key(name, info)
        if ltype == "ollama_cloud":
            return self._flow_ollama_cloud()
        if ltype == "opencode_cli":
            return self._flow_opencode()
        if ltype == "service":
            return self._flow_ollama_service()
        if ltype == "sendcm":
            return self._flow_sendcm()
        if ltype == "gitlab":
            return self._flow_gittoken("gitlab", "GitLab",
                                        "https://gitlab.com/api/v4/user",
                                        "PRIVATE-TOKEN")
        if ltype == "codeberg":
            return self._flow_gittoken("codeberg", "Codeberg",
                                        "https://codeberg.org/api/v1/user",
                                        "Authorization", prefix="token ")
        if ltype == "huggingface":
            return self._flow_huggingface()
        return f"[red]Tipo de login '{ltype}' no reconocido.[/red]"

    def _flow_github(self) -> str:
        return flow_github(self)

    def _flow_openai(self) -> str:
        return flow_openai(self)

    def _flow_api_key(self, name: str, info: dict) -> str:
        return flow_api_key(self, name, info)

    def _flow_ollama_cloud(self) -> str:
        return flow_ollama_cloud(self)

    def _flow_opencode(self) -> str:
        return flow_opencode(self)

    def _flow_ollama_service(self) -> str:
        return flow_ollama_service(self)

    def _flow_gittoken(self, provider: str, label: str,
                       verify_url: str, auth_header: str,
                       prefix: str = "") -> str:
        return flow_gittoken(self, provider, label, verify_url, auth_header, prefix)

    def _flow_huggingface(self) -> str:
        return flow_huggingface(self)

    def _flow_sendcm(self) -> str:
        return flow_sendcm(self)

    # ── Wizard de nueva cuenta ───────────────────────────────────────────────

    def _do_add_account(self, provider: str, custom_label: str = "") -> str:
        """Flujo interactivo para agregar una cuenta nueva de cualquier provider."""
        am = self._accounts
        existing = am.accounts_for(provider)
        n = len(existing)
        plabel = AccountManager.PROVIDER_LABELS.get(provider, provider)

        console.print(
            f"\n[bold]Agregar cuenta nueva — {plabel}[/bold]"
            + (f"\n[dim]  Ya tienes {n} cuenta{'s' if n != 1 else ''} de este tipo.[/dim]"
               if n > 0 else "")
        )

        if not custom_label:
            default = f"{plabel} #{n + 1}"
            raw = pt_prompt(f"Nombre/etiqueta [{default}]: ").strip()
            label = raw or default
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

        if provider == "openai":
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

        # Genérico: cualquier provider con API key
        url = self.PROVIDERS.get(provider, {}).get("url", "")
        if url:
            console.print(f"[dim]Obtén tu clave en: {url}[/dim]")
        key = pt_prompt(f"API Key para {label}: ", is_password=True).strip()
        if not key:
            return "Cancelado."
        account_id = am.add(provider, label, key, "api_key", make_active=True)
        am.apply_active_credentials()
        return f"[green]✓ Cuenta añadida: {account_id} — {label}[/green]"

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _bago_to_am_provider(self, name: str) -> str:
        """Convierte nombre de CredentialManager a tipo de AccountManager."""
        return {
            "github":       "github",
            "openai":       "openai",
            "anthropic":    "anthropic",
            "openrouter":   "openrouter",
            "gemini":       "gemini",
            "ollama_cloud": "ollama_cloud",
        }.get(name, name)
