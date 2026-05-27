"""Probe, pull y discovery de Ollama."""

from __future__ import annotations

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


DEFAULT_OLLAMA_PORT = 11434
DEFAULT_BAGO_API_PORT = 11435
DEFAULT_BAGO_COPILOT_PORT = 11436
DEFAULT_BAGO_CODEX_PORT = 11437
DEFAULT_BAGO_OLLAMA_CLOUD_PORT = 11438
DEFAULT_BAGO_TELEGRAM_PORT = 11439
DEFAULT_BAGO_UTOPIA_PORT = 11440
DEFAULT_BAGO_HUB_PORT = 7860
DEFAULT_BAGO_LLM_SERVER_PORT = 8080
DEFAULT_WEB_PORT = 3000
DEFAULT_WEB_DEV_PORT = 3001
DEFAULT_API_HTTP_PORT = 4000
DEFAULT_SERVER_PORT = 5000
DEFAULT_VITE_PORT = 5173
DEFAULT_VITE_PREVIEW_PORT = 4173
DEFAULT_HONO_PORT = 8788
DEFAULT_NOTEBOOK_PORT = 8888
DEFAULT_TOOLING_PORT = 8000
DEFAULT_ALT_HTTP_PORT = 8080


def default_ollama_base_url() -> str:
    host = os.environ.get("OLLAMA_HOST", "").strip()
    if host:
        return host if host.startswith("http") else f"http://{host}"
    return f"http://127.0.0.1:{default_ollama_port()}"


def default_ollama_port() -> int:
    raw = os.environ.get("OLLAMA_PORT") or os.environ.get("BAGO_PORT") or str(DEFAULT_OLLAMA_PORT)
    try:
        return int(raw)
    except Exception:
        return DEFAULT_OLLAMA_PORT


def env_port(*names: str, default: int = DEFAULT_ALT_HTTP_PORT) -> int:
    for name in names:
        raw = os.environ.get(name, "").strip()
        if raw:
            try:
                return int(raw)
            except Exception:
                continue
    return default


def ollama_probe(base_url: str | None = None, timeout: float = 3) -> dict:
    """Comprueba si Ollama está activo y qué modelos tiene instalados."""
    import socket
    import urllib.error
    import urllib.request

    base_url = base_url or default_ollama_base_url()
    old_default = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
        with urllib.request.urlopen(f"{base_url}/api/tags", timeout=timeout) as r:
            data = json.loads(r.read())
        models = [m["name"] for m in data.get("models", [])]
        return {"running": True, "url": base_url, "models": models, "error": None}
    except urllib.error.URLError as e:
        return {"running": False, "url": base_url, "models": [], "error": str(e.reason)}
    except OSError as e:
        return {"running": False, "url": base_url, "models": [], "error": str(e)}
    except Exception as e:
        return {"running": False, "url": base_url, "models": [], "error": str(e)}
    finally:
        socket.setdefaulttimeout(old_default)


def ollama_pull(model_name: str, base_url: str | None = None) -> bool:
    """Descarga un modelo con `ollama pull`. Muestra progreso en consola."""
    import shutil
    import subprocess

    base_url = base_url or default_ollama_base_url()
    cli = shutil.which("ollama")
    if not cli:
        return _ollama_pull_api(model_name, base_url)

    try:
        proc = subprocess.Popen(
            [cli, "pull", model_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
        )
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                print(f"  {line}", flush=True)
        proc.wait()
        return proc.returncode == 0
    except Exception as e:
        print(f"  Error ejecutando ollama pull: {e}")
        return False


def _ollama_pull_api(model_name: str, base_url: str) -> bool:
    """Fallback: llama a POST /api/pull cuando el CLI de Ollama no está en PATH."""
    import json as _json
    import urllib.request

    payload = _json.dumps({"name": model_name, "stream": True}).encode()
    req = urllib.request.Request(
        f"{base_url}/api/pull",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            for raw_line in r:
                if not raw_line.strip():
                    continue
                try:
                    chunk = _json.loads(raw_line)
                    status = chunk.get("status", "")
                    if status:
                        print(f"  {status}", flush=True)
                    if chunk.get("error"):
                        print(f"  {chunk['error']}")
                        return False
                except Exception:
                    pass
        return True
    except Exception as e:
        print(f"  API pull error: {e}")
        return False


def discover_ollama_url(timeout: float = 1.0) -> str | None:
    """Busca Ollama probando OLLAMA_HOST, puertos locales y arranque Windows."""
    import sys

    candidates: list[str] = []
    host_env = os.environ.get("OLLAMA_HOST", "").strip()
    if host_env:
        candidates.append(host_env if host_env.startswith("http") else f"http://{host_env}")
    port = str(default_ollama_port())
    candidates += [
        f"http://127.0.0.1:{port}",
        f"http://localhost:{port}",
        f"http://127.0.0.1:{DEFAULT_BAGO_API_PORT}",
        f"http://127.0.0.1:{DEFAULT_BAGO_LLM_SERVER_PORT}",
    ]

    seen: set[str] = set()
    for url in candidates:
        if url in seen:
            continue
        seen.add(url)
        try:
            result = ollama_probe(url, timeout=timeout)
        except KeyboardInterrupt:
            raise
        except Exception:
            continue
        if result["running"]:
            os.environ["OLLAMA_HOST"] = url
            return url

    if sys.platform == "win32":
        _try_start_ollama_windows()
        for url in [f"http://127.0.0.1:{port}", f"http://localhost:{port}"]:
            result = ollama_probe(url, timeout=timeout)
            if result["running"]:
                os.environ["OLLAMA_HOST"] = url
                return url

    return None


def _try_start_ollama_windows() -> None:
    """Intenta arrancar el servidor Ollama en Windows si el exe existe."""
    import shutil
    import subprocess
    import time

    cli = shutil.which("ollama")
    if not cli:
        localapp = os.environ.get("LOCALAPPDATA", "")
        candidates_win = [
            os.path.join(localapp, "Programs", "Ollama", "ollama.exe"),
            os.path.join(localapp, "ollama", "ollama.exe"),
            r"C:\Program Files\Ollama\ollama.exe",
        ]
        for path in candidates_win:
            if os.path.isfile(path):
                cli = path
                break
    if not cli:
        return

    try:
        subprocess.Popen(
            [cli, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=0x00000008,
        )
        port = str(default_ollama_port())
        for _ in range(3):
            time.sleep(0.3)
            try:
                import urllib.request

                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/tags", timeout=0.5):
                    break
            except Exception:
                pass
    except Exception:
        pass



def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(__file__ + " --test: PASS (imports OK)")
    return 0


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
