"""LoginFlowsMixin — flujos interactivos de /login para CredentialManager.

Separado de manager.py para mantener la lógica de UI aislada del estado.
Se mezcla con CredentialManager mediante herencia múltiple.
"""

import subprocess
from pathlib import Path

from prompt_toolkit import prompt as pt_prompt

from ..ui import console
from .accounts import AccountManager


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
        """GitHub: PAT directo (sin navegador) o gh auth login (abre browser)."""
        console.print(
            "[bold]GitHub — elige método:[/bold]\n"
            "  [yellow]1[/yellow]  Personal Access Token  (pegar token — sin navegador)\n"
            "  [yellow]2[/yellow]  gh auth login          (flujo OAuth — puede abrir navegador)\n"
        )
        choice = pt_prompt("Opción [1/2]: ").strip()

        if choice == "1":
            console.print("[dim]Genera tu token en: GitHub → Settings → Developer settings → Personal access tokens[/dim]")
            console.print("[dim]Permisos mínimos recomendados: repo, read:org, gist[/dim]")
            token = pt_prompt("GitHub Personal Access Token: ", is_password=True).strip()
            if not token:
                return "Cancelado."
            # Verificar token contra API de GitHub
            try:
                import urllib.request, json as _json
                req = urllib.request.Request(
                    "https://api.github.com/user",
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    user = _json.loads(resp.read())["login"]
                console.print(f"  [green]✓ Verificado: @{user}[/green]")
            except Exception:
                console.print("  [yellow]⚠  No se pudo verificar el token (sin conexión), guardando de todas formas.[/yellow]")
                user = "?"
            self.set("github", token)
            existing = self._accounts.accounts_for("github")
            if existing:
                self._accounts.update(existing[0]["id"], credential=token)
            else:
                self._accounts.add("github", f"GitHub @{user}", token, "token")
            self._accounts.apply_active_credentials()
            return f"[green]✓ GitHub PAT guardado  (@{user}  {token[:4]}…{token[-4:]})[/green]"

        # Opción 2: gh auth login
        result = subprocess.run(["gh", "auth", "login"])
        if result.returncode != 0:
            return "Login GitHub fallido."
        try:
            token = subprocess.check_output(["gh", "auth", "token"], text=True).strip()
            self.set("github", token)
            existing = self._accounts.accounts_for("github")
            if existing:
                self._accounts.update(existing[0]["id"], credential=token)
            else:
                self._accounts.add("github", "GitHub Personal", token, "token")
            self._accounts.apply_active_credentials()
            return f"[green]✓ GitHub token guardado ({token[:4]}…{token[-4:]})[/green]"
        except Exception as e:
            return f"Token obtenido pero no guardado: {e}"

    def _flow_openai(self) -> str:
        console.print(
            "[bold]OpenAI / GPT — elige método:[/bold]\n"
            "  [yellow]1[/yellow]  codex login  (GPT Plus — abre navegador, sin API key)\n"
            "  [yellow]2[/yellow]  API key      (pegar clave desde platform.openai.com)\n"
        )
        choice = pt_prompt("Opción [1/2]: ").strip()
        if choice == "1":
            console.print("[dim]Ejecutando codex login (abre navegador)...[/dim]")
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

    def _flow_api_key(self, name: str, info: dict) -> str:
        url = info.get("url", "")
        if url:
            console.print(f"[dim]Obtén tu clave en: {url}[/dim]")
        console.print(f"[bold]{info['desc']}[/bold]")
        key = pt_prompt("API Key: ", is_password=True).strip()
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

    def _flow_ollama_cloud(self) -> str:
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

    def _flow_opencode(self) -> str:
        try:
            subprocess.check_output(
                ["opencode", "--version"], stderr=subprocess.DEVNULL, timeout=5
            )
            opencode_ok = True
        except Exception:
            opencode_ok = False

        if not opencode_ok:
            console.print(
                "[bold yellow]OpenCode no está instalado.[/bold yellow]\n"
                "[dim]Instala con:[/dim]  npm install -g opencode-ai\n"
                "[dim]Más info:[/dim]    https://opencode.ai\n"
            )
            if pt_prompt("¿Instalar ahora? [s/n]: ").strip().lower() == "s":
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

    def _flow_ollama_service(self) -> str:
        if self._ollama_ok():
            try:
                out = subprocess.check_output(
                    ["ollama", "list"], text=True, stderr=subprocess.DEVNULL
                )
                console.print(out)
                return "[green]✓ Ollama activo y disponible.[/green]"
            except Exception:
                pass
        return "[red]Ollama no disponible. Instala desde https://ollama.com[/red]"

    def _flow_gittoken(self, provider: str, label: str,
                       verify_url: str, auth_header: str,
                       prefix: str = "") -> str:
        """Flujo genérico para repos con token (GitLab, Codeberg/Gitea, etc).
        Opción 1: pegar token directamente (sin navegador).
        Opción 2: email + password → API genera token (sin navegador).
        """
        import urllib.request, json as _json, urllib.parse

        console.print(
            f"[bold]{label} — elige método:[/bold]\n"
            f"  [yellow]1[/yellow]  Personal Access Token  (pegar token — sin navegador)\n"
            f"  [yellow]2[/yellow]  Email + contraseña     (BAGO genera token por API — sin navegador)\n"
        )
        choice = pt_prompt("Opción [1/2]: ").strip()

        if choice == "2":
            # Obtener token por API con email+password (Gitea / GitLab)
            base = verify_url.rsplit("/", 2)[0]  # https://codeberg.org
            email = pt_prompt(f"Email {label}: ").strip()
            if not email:
                return "Cancelado."
            password = pt_prompt("Contraseña: ", is_password=True).strip()
            if not password:
                return "Cancelado."
            token_name = "bago_token"
            # Gitea API: POST /api/v1/users/{user}/tokens
            # GitLab no soporta password→token por API pública (solo PAT UI)
            if "codeberg" in verify_url or "gitea" in verify_url:
                # Buscar username primero
                try:
                    import base64 as _b64
                    cred = _b64.b64encode(f"{email}:{password}".encode()).decode()
                    req = urllib.request.Request(
                        f"{base}/api/v1/user",
                        headers={"Authorization": f"Basic {cred}", "Accept": "application/json"},
                    )
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        username = _json.loads(resp.read())["login"]
                    # Crear token de acceso
                    payload = _json.dumps({"name": token_name}).encode()
                    req2 = urllib.request.Request(
                        f"{base}/api/v1/users/{username}/tokens",
                        data=payload,
                        headers={
                            "Authorization": f"Basic {cred}",
                            "Content-Type": "application/json",
                        },
                        method="POST",
                    )
                    with urllib.request.urlopen(req2, timeout=10) as resp2:
                        data = _json.loads(resp2.read())
                    token = data.get("sha1") or data.get("token") or ""
                    if not token:
                        return f"[red]No se pudo obtener token de {label}: {data}[/red]"
                    console.print(f"  [green]✓ Token generado para @{username}[/green]")
                except Exception as e:
                    return f"[red]Error generando token en {label}: {e}[/red]"
            else:
                # GitLab no permite crear PAT por password API — pedir manualmente
                console.print(f"  [yellow]{label} no permite crear tokens por contraseña vía API.[/yellow]")
                console.print(f"  [dim]Ve a: {self.PROVIDERS.get(provider, {}).get('url', '')}[/dim]")
                token = pt_prompt(f"{label} Personal Access Token: ", is_password=True).strip()
                if not token:
                    return "Cancelado."
        else:
            url = self.PROVIDERS.get(provider, {}).get("url", "")
            if url:
                console.print(f"[dim]Genera tu token en: {url}[/dim]")
            token = pt_prompt(f"{label} Token: ", is_password=True).strip()
            if not token:
                return "Cancelado."

        # Verificar token
        try:
            req = urllib.request.Request(
                verify_url,
                headers={auth_header: f"{prefix}{token}", "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                user_data = _json.loads(resp.read())
                username = user_data.get("username") or user_data.get("login") or user_data.get("name") or "?"
            console.print(f"  [green]✓ Verificado: @{username}[/green]")
        except Exception:
            username = "?"
            console.print(f"  [yellow]⚠  Token no verificado (sin conexión), guardando de todas formas.[/yellow]")

        # Guardar en creds + variable de entorno
        env_key = self.PROVIDERS.get(provider, {}).get("env")
        if env_key:
            import os
            os.environ[env_key] = token
        self._creds.setdefault(provider, {})["token"] = token
        self._creds[provider]["username"] = username
        self._save()
        return f"[green]✓ {label} autenticado: @{username}  ({token[:4]}…{token[-4:]})[/green]"

    def _flow_huggingface(self) -> str:
        """Hugging Face: pegar token o usar huggingface-cli login."""
        console.print(
            "[bold]Hugging Face — elige método:[/bold]\n"
            "  [yellow]1[/yellow]  Token directo     (pegar token — sin navegador)\n"
            "  [yellow]2[/yellow]  huggingface-cli   (si está instalado)\n"
        )
        choice = pt_prompt("Opción [1/2]: ").strip()

        if choice == "2":
            try:
                result = subprocess.run(["huggingface-cli", "login"])
                if result.returncode == 0:
                    # Leer token del cache de HF
                    hf_cache = Path.home() / ".cache" / "huggingface" / "token"
                    if hf_cache.exists():
                        token = hf_cache.read_text().strip()
                        self.set("huggingface", token)
                        return f"[green]✓ Hugging Face autenticado via CLI[/green]"
                    return "[green]✓ Hugging Face CLI login OK[/green]"
                return "[red]huggingface-cli login fallido.[/red]"
            except FileNotFoundError:
                console.print("  [yellow]huggingface-cli no encontrado. Usando opción 1.[/yellow]")

        console.print("[dim]Genera tu token en: https://huggingface.co/settings/tokens[/dim]")
        console.print("[dim]Tipo recomendado: 'read' para inferencia, 'write' para subir modelos[/dim]")
        token = pt_prompt("Hugging Face Token (hf_...): ", is_password=True).strip()
        if not token:
            return "Cancelado."

        # Verificar
        try:
            import urllib.request, json as _json
            req = urllib.request.Request(
                "https://huggingface.co/api/whoami-v2",
                headers={"Authorization": f"Bearer {token}"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = _json.loads(resp.read())
                username = data.get("name") or data.get("login") or "?"
            console.print(f"  [green]✓ Verificado: @{username}[/green]")
        except Exception:
            username = "?"
            console.print("  [yellow]⚠  No verificado (sin conexión), guardando de todas formas.[/yellow]")

        self.set("huggingface", token)
        return f"[green]✓ Hugging Face token guardado (@{username}  {token[:6]}…)[/green]"

    def _flow_sendcm(self) -> str:
        """Login a send.cm por email+contraseña — sin navegador, todo en el REPL."""
        console.print(
            "[bold]send.cm — login directo por API[/bold]\n"
            "[dim]  No necesitas abrir el navegador. Introduce tus credenciales de send.cm.[/dim]\n"
            "[dim]  Regístrate gratis en https://send.cm si aún no tienes cuenta.[/dim]\n"
        )

        # Comprobar si ya hay token guardado
        existing = self._creds.get("sendcm", {}).get("api_key", "")
        if existing:
            console.print(f"  [dim]Token actual: {existing[:6]}…{existing[-4:]}[/dim]")
            overwrite = pt_prompt("¿Reemplazar token existente? [s/N]: ").strip().lower()
            if overwrite not in ("s", "si", "sí", "y", "yes"):
                return "[dim]Login cancelado — token existente conservado.[/dim]"

        email = pt_prompt("Email send.cm: ").strip()
        if not email:
            return "Cancelado."
        password = pt_prompt("Contraseña: ", is_password=True).strip()
        if not password:
            return "Cancelado."

        try:
            import urllib.request, urllib.parse, json as _json
            payload = _json.dumps({"email": email, "password": password}).encode()
            req = urllib.request.Request(
                "https://send.cm/api/v2/login",
                data=payload,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = _json.loads(resp.read().decode())
        except Exception as e:
            return f"[red]Error de conexión con send.cm: {e}[/red]"

        # La API devuelve token en data.token o data.api_key según versión
        token = (
            data.get("data", {}).get("token")
            or data.get("data", {}).get("api_key")
            or data.get("token")
            or data.get("api_key")
            or ""
        )
        if not token:
            msg = data.get("message") or data.get("error") or str(data)
            return f"[red]Login fallido: {msg}[/red]"

        # Guardar en credentials.json
        self._creds.setdefault("sendcm", {})["api_key"] = token
        self._creds["sendcm"]["email"] = email
        self._save()
        return f"[green]✓ send.cm autenticado: {email}  (token {token[:6]}…{token[-4:]})[/green]"

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
