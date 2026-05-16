
from rich import box
from rich.panel import Panel

from ..ui import console, _menu_action, _menu_confirm, _menu_select, pi

def _cmd_auth(session):
    """Superset de /login: estado, login, revoke, futuro sign-up."""
    while True:
        active = session.creds.active_bago_providers()
        active_str = ", ".join(active) if active else "ninguno"
        choices = [
            ("status",   f"Estado providers  (activos: {active_str})"),
            ("login",    "Login / registrar provider"),
            ("revoke",   "Revocar credencial guardada"),
            ("refresh",  "Refresh tokens (actualizar)"),
            ("signup",   "[dim]Sign-up nuevo proveedor  (proximamente)[/dim]"),
        ]
        sel = _menu_select("BAGO / Auth", "Gestion de autenticacion y providers:", choices)
        if sel is None: break

        if sel == "status":
            console.print(Panel(session.creds.status_table(),
                                title="[bold]Providers BAGO[/bold]", box=box.ROUNDED))

        elif sel == "login":
            providers_choices = [
                ("github",    "GitHub Copilot  (gh auth login)"),
                ("gpt",       "GPT / OpenAI  (codex login o API key)"),
                ("anthropic", "Anthropic Claude  (API key)"),
                ("ollama",    "Ollama local  (verificar que esta corriendo)"),
            ]
            provider = _menu_select("Login", "Selecciona provider:", providers_choices)
            if provider:
                result = session.creds.do_login(provider)
                console.print(f"  {result}")

        elif sel == "revoke":
            cred_keys = list(session.creds._creds.keys())
            if not cred_keys:
                pi("No hay credenciales guardadas."); continue
            choices_r = [(k, f"{k}: {str(session.creds._creds[k])[:30]}...") for k in cred_keys]
            key = _menu_select("Revocar", "Que credencial revocar?", choices_r)
            if key:
                if _menu_confirm("Revocar", f"Eliminar '{key}' de credentials.json?"):
                    del session.creds._creds[key]
                    session.creds._save()
                    pi(f"Credencial '{key}' revocada.")

        elif sel == "refresh":
            pi("Refresh: re-ejecutando deteccion de providers activos...")
            active = session.creds.active_bago_providers()
            pi(f"Providers activos ahora: {', '.join(active) or 'ninguno'}")

        elif sel == "signup":
            _menu_action("Proximamente", "Sign-up de nuevos proveedores en desarrollo.\nPor ahora usa /auth -> Login -> API key.", [("Cerrar","ok")])
