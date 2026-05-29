"""bago music-saas — CLI integrado para bago-music-saas (FastAPI + Telegram + PWA).

Delegata a cli.py del repo clonado o usa la API remota configurada.
"""

from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso
import importlib.util
import os, sys, json, shutil, subprocess, urllib.request, urllib.error
from pathlib import Path

REPO_URL  = "https://github.com/MarcValls/bago-music-saas"
PWA_URL   = "https://marcvalls.github.io/bago-music-saas/"
CONFIG_F  = Path.home() / ".bago_music_saas.json"

_HELP = """
bago music-saas [comando]

Comandos:
  status            Estado del SaaS (API remota, bot Telegram, PWA)
  dev               Clona el repo y arranca el servidor local (FastAPI :7430)
  webhook <url>     Registra el webhook de Telegram
  test              Prueba la conexión bot Telegram + API remota
  open [tool]       Abre en navegador: transposer | teacher | editor | pwa
  build             Estado de GitHub Actions (requiere gh CLI)
  config            Muestra / edita configuración activa
  plans             Descripción de los planes Free / Pro / Studio
"""

def _load_cfg() -> dict:
    if CONFIG_F.exists():
        try:
            return json.loads(CONFIG_F.read_text())
        except Exception:
            pass
    return {}

def _save_cfg(cfg: dict) -> None:
    CONFIG_F.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))

def _token() -> str:
    return os.environ.get("BAGO_TELEGRAM_TOKEN", _load_cfg().get("telegram_token", ""))

def _api_url() -> str:
    return os.environ.get("BAGO_MUSIC_URL", _load_cfg().get("api_url", ""))

def _clone_dir() -> Path:
    return Path(os.environ.get("BAGO_MUSIC_SAAS_DIR") or (Path.home() / "bago-music-saas"))

def _missing_tool(tool: str, hint: str) -> None:
    print(f"✗  No se encuentra '{tool}' en este equipo.", file=sys.stderr)
    print(f"   {hint}", file=sys.stderr)


# ── subcommands ──────────────────────────────────────────────────────────────

def cmd_status() -> None:
    cfg = _load_cfg()
    token = _token()
    api   = _api_url()

    ok = lambda s: f"\033[32m✓\033[0m  {s}"
    warn = lambda s: f"\033[33m⚠ \033[0m {s}"
    err  = lambda s: f"\033[31m✗\033[0m  {s}"

    print("\n\033[1m🎵 BAGO Music SaaS — Estado\033[0m\n")

    # Telegram bot
    if token:
        try:
            with urllib.request.urlopen(
                f"https://api.telegram.org/bot{token}/getMe", timeout=5
            ) as r:
                data = json.loads(r.read())
            name = data["result"].get("username", "?")
            print(ok(f"Telegram bot    @{name}"))
        except Exception as e:
            print(err(f"Telegram bot    error: {e}"))
    else:
        print(warn("Telegram bot    BAGO_TELEGRAM_TOKEN no definido"))

    # Remote API
    if api:
        try:
            with urllib.request.urlopen(f"{api.rstrip('/')}/", timeout=5) as r:
                print(ok(f"API remota      {api}"))
        except Exception:
            print(warn(f"API remota      {api} — sin respuesta"))
    else:
        print(warn("API remota      no configurada — usa: bago music-saas config"))

    print(f"\n  🌐 PWA:   {PWA_URL}")
    print(f"  📦 Repo:  {REPO_URL}\n")


def cmd_dev() -> None:
    """Clone repo (if needed) and start local server."""
    clone_dir = _clone_dir()
    git = shutil.which("git")
    if not clone_dir.exists():
        if not git:
            _missing_tool(
                "git",
                "Instala Git o clona el repo manualmente en "
                f"{clone_dir}: https://git-scm.com/download/win",
            )
            sys.exit(2)
        print(f"Clonando en {clone_dir}…")
        r = subprocess.run([git, "clone", REPO_URL, str(clone_dir)])
        if r.returncode != 0:
            print("Error al clonar el repo.", file=sys.stderr)
            sys.exit(1)
    else:
        if git:
            subprocess.run([git, "-C", str(clone_dir), "pull", "--ff-only"])
        else:
            print("⚠  git no encontrado; se omite actualización del repo local.")

    if importlib.util.find_spec("uvicorn") is None:
        _missing_tool(
            "uvicorn",
            "Instala las dependencias del SaaS con: python -m pip install uvicorn fastapi",
        )
        sys.exit(2)

    env = os.environ.copy()
    env.setdefault("BAGO_TELEGRAM_TOKEN", _token() or "PLACEHOLDER")
    print("\n🚀 Iniciando FastAPI en http://localhost:7430 …\n")
    subprocess.run(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--reload", "--port", "7430"],
        cwd=clone_dir, env=env,
    )


def cmd_webhook(url: str) -> None:
    token = _token()
    if not token:
        print("⚠  BAGO_TELEGRAM_TOKEN no definido.", file=sys.stderr)
        sys.exit(1)
    webhook_url = f"{url.rstrip('/')}/webhook"
    api_call = f"https://api.telegram.org/bot{token}/setWebhook"
    data = json.dumps({"url": webhook_url}).encode()
    req = urllib.request.Request(api_call, data=data,
                                  headers={"Content-Type": "application/json"},
                                  method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            result = json.loads(r.read())
        if result.get("ok"):
            print(f"✓  Webhook registrado en {webhook_url}")
        else:
            print(f"✗  Error: {result}", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"✗  {e}", file=sys.stderr)
        sys.exit(1)


def cmd_test() -> None:
    token = _token()
    api   = _api_url()
    ok_s  = "\033[32m✓\033[0m"
    err_s = "\033[31m✗\033[0m"
    print()
    if token:
        try:
            with urllib.request.urlopen(
                f"https://api.telegram.org/bot{token}/getMe", timeout=5
            ) as r:
                data = json.loads(r.read())
            print(f"  {ok_s} Bot Telegram @{data['result']['username']}")
        except Exception as e:
            print(f"  {err_s} Bot Telegram: {e}")
    else:
        print(f"  ⚠  Token no definido")
    if api:
        try:
            urllib.request.urlopen(f"{api.rstrip('/')}/", timeout=5)
            print(f"  {ok_s} API remota {api}")
        except Exception as e:
            print(f"  {err_s} API remota {api}: {e}")
    else:
        print("  ⚠  API remota no configurada")
    print()


def cmd_open(tool: str = "pwa") -> None:
    import webbrowser
    urls = {
        "transposer": f"{PWA_URL}transposer.html",
        "teacher":    f"{PWA_URL}score_teacher.html",
        "editor":     f"{PWA_URL}matrix_editor.html",
        "pwa":        PWA_URL,
    }
    target = urls.get(tool.lower(), PWA_URL)
    webbrowser.open(target)
    print(f"🌐 Abriendo {target}")


def cmd_build() -> None:
    try:
        r = subprocess.run(
            ["gh", "run", "list", "--repo", "MarcValls/bago-music-saas",
             "--limit", "5", "--json", "name,status,conclusion,createdAt"],
            capture_output=True, text=True
        )
        if r.returncode != 0:
            print("⚠  gh CLI no disponible o no autenticado.")
            print(f"   Visita: {REPO_URL}/actions")
            return
        runs = json.loads(r.stdout)
        print(f"\n  Últimos GitHub Actions — {REPO_URL}/actions\n")
        for run in runs:
            icon = {"success": "✅", "failure": "❌", "cancelled": "⚠ "}.get(
                run.get("conclusion", ""), "🔄"
            )
            print(f"  {icon}  {run['name']}  ({run.get('status', '?')})  {run['createdAt'][:10]}")
        print()
    except Exception as e:
        print(f"✗  {e}")


def cmd_config() -> None:
    cfg = _load_cfg()
    print(f"\n  Config: {CONFIG_F}\n")
    print(f"  api_url       : {cfg.get('api_url', '— no definido')}")
    print(f"  telegram_token: {'***' if cfg.get('telegram_token') else '— no definido'}")
    print()
    if not cfg.get("api_url"):
        api_url = input("  API URL (ej: https://bago-music.onrender.com): ").strip()
        if api_url:
            cfg["api_url"] = api_url
    if not cfg.get("telegram_token"):
        tok = input("  Token Telegram (vacío para usar ENV): ").strip()
        if tok:
            cfg["telegram_token"] = tok
    _save_cfg(cfg)
    print("  ✓  Configuración guardada.\n")


def cmd_plans() -> None:
    print("""
\033[1m🎵 BAGO Music SaaS — Planes\033[0m

  \033[32mFREE\033[0m
    • Transpositor web
    • Score Teacher básico
    • Editor Matricial (lectura)

  \033[33mPRO\033[0m
    • Todo Free +
    • Bot Telegram: transposición por mensaje
    • Editor Matricial completo
    • Exportación MIDI

  \033[35mSTUDIO\033[0m
    • Todo Pro +
    • API REST privada
    • Android TWA (APK)
    • Integración BAGO framework
    • Soporte prioritario
""")


# ── entrypoint ───────────────────────────────────────────────────────────────

def main(args: list[str] | None = None) -> None:
    argv = (args or sys.argv)[1:]
    if argv and argv[0].lower() in ("music-saas", "music_saas"):
        argv = argv[1:]
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(_HELP)
        return

    sub = argv[0].lower()
    rest = argv[1:]

    dispatch = {
        "status":  cmd_status,
        "dev":     cmd_dev,
        "test":    cmd_test,
        "build":   cmd_build,
        "config":  cmd_config,
        "plans":   cmd_plans,
    }

    if sub == "webhook":
        if not rest:
            print("Uso: bago music-saas webhook <url>", file=sys.stderr)
            sys.exit(1)
        cmd_webhook(rest[0])
    elif sub == "open":
        cmd_open(rest[0] if rest else "pwa")
    elif sub in dispatch:
        dispatch[sub]()
    else:
        print(f"Comando desconocido: {sub}")
        print(_HELP)
        sys.exit(1)


if __name__ == "__main__":
    main()
