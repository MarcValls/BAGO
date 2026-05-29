
import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich import box
from rich.panel import Panel

from ..providers import auto_detect_provider, get_default_model, load_providers
from ..ui import console, _menu_action, _menu_confirm, _menu_pick, _menu_select, pi


def _cmd_login(session):
    """
    /login sin argumento: picker navegable de providers con estado inline.
    Flecha arriba/abajo para navegar, Enter para seleccionar, Esc para salir.
    """
    while True:
        choices = session.creds.login_choices()
        provider = _menu_pick(
            "Login / Providers BAGO",
            "Selecciona provider para registrar o verificar:",
            choices,
        )
        if provider is None:
            return
        result = session.creds.do_login(provider)
        console.print(f"  {result}")


def _cmd_auth(session):
    """Superset de /login: estado, login, revoke, futuro sign-up."""
    while True:
        active = session.creds.active_bago_providers()
        active_str = ", ".join(active) if active else "ninguno"
        choices = [
            ("status",   f"Estado providers  (activos: {active_str})"),
            ("login",    "Login / registrar provider"),
            ("logout",   "Logout / borrar credencial activa"),
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
                # ── LLM / IA ──
                ("github",       "GitHub Copilot / Models   (PAT sin navegador o gh auth)"),
                ("openai",       "OpenAI / GPT Plus          (codex login)"),
                ("anthropic",    "Anthropic Claude            (API key — sin navegador)"),
                ("gemini",       "Google Gemini               (API key — sin navegador)"),
                ("groq",         "Groq — inferencia rapida    (API key — sin navegador)"),
                ("mistral",      "Mistral AI                  (API key — sin navegador)"),
                ("together",     "Together AI +100 modelos    (API key — sin navegador)"),
                ("deepseek",     "DeepSeek V3 / R1            (API key — sin navegador)"),
                ("xai",          "xAI Grok                    (API key — sin navegador)"),
                ("perplexity",   "Perplexity sonar            (API key — sin navegador)"),
                ("cohere",       "Cohere Command R+           (API key — sin navegador)"),
                ("replicate",    "Replicate open-source       (API key — sin navegador)"),
                ("huggingface",  "Hugging Face                (token — sin navegador)"),
                ("openrouter",   "OpenRouter +200 modelos     (API key — sin navegador)"),
                # ── Ollama ──
                ("ollama",       "Ollama local                (sin clave — verificar)"),
                ("ollama_cloud", "Ollama Cloud                (API key o ollama signin)"),
                ("opencode",     "OpenCode AI CLI             (instala si necesario)"),
                # ── Repositorios ──
                ("gitlab",       "GitLab                      (token o email+pass — sin nav.)"),
                ("codeberg",     "Codeberg / Forgejo          (token o email+pass — sin nav.)"),
                # ── Almacenamiento ──
                ("sendcm",       "send.now (compat. send.cm)  (email+contraseña — sin nav.)"),
            ]
            provider = _menu_select("Login", "Selecciona provider a registrar:", providers_choices)
            if provider:
                result = session.creds.do_login(provider)
                console.print(f"  {result}")

        elif sel == "logout":
            logout_choices = []
            seen = set()
            for provider, _label in session.creds.login_choices():
                if provider in seen:
                    continue
                seen.add(provider)
                logout_choices.append((provider, provider))
            provider = _menu_select("Logout", "Qué provider quieres cerrar sesión?", logout_choices)
            if provider:
                result = session.creds.logout(provider)
                session.providers = load_providers()
                if provider in (session.provider, "openai", "github", "ollama_cloud", "sendcm"):
                    new_prov = auto_detect_provider(session.creds, session.providers)
                    name, wire, prov = get_default_model(new_prov, session.providers)
                    if name:
                        session.provider, session.model_name, session.wire_name = prov, name, wire
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
            _menu_action("Proximamente", "Sign-up de nuevos proveedores en desarrollo.\nPor ahora usa /auth -> Login -> provider.", [("Cerrar","ok")])
