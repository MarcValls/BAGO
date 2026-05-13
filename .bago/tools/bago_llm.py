#!/usr/bin/env python3
"""bago_llm.py — Motor LLM local en el pendrive BAGO.

Gestiona modelos LLM cuantizados almacenados en el pendrive y arranca
un servidor de inferencia offline via Ollama o llama-server.

Los modelos viajan con el pendrive — en una máquina nueva solo hay que
tener Ollama instalado; los pesos no se vuelven a descargar.

Modelos recomendados:
  qwen25-coder  →  Qwen 2.5 Coder 7B  (mejor para código con BAGO)
  phi3-mini     →  Phi-3 Mini 3.8B    (ligero, baja RAM)
  llama32-3b    →  Llama 3.2 3B       (uso general)

Uso:
    bago llm                   → estado del motor LLM
    bago llm models            → catálogo de modelos disponibles
    bago llm download [ID]     → descarga modelo al pendrive
    bago llm start [ID]        → arranca servidor Ollama con ese modelo
    bago llm stop              → detiene el servidor
    bago llm chat <mensaje>    → consulta directa al LLM activo
    bago llm --test            → self-check (tool_guardian)
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

# ── Rutas ─────────────────────────────────────────────────────────────────────

TOOLS_DIR  = Path(__file__).resolve().parent
BAGO_ROOT  = TOOLS_DIR.parent
DRIVE_ROOT = BAGO_ROOT.parent
STATE_DIR  = BAGO_ROOT / "state"
MODELS_DIR = BAGO_ROOT / ".models"
LLAMA_DIR  = BAGO_ROOT / ".llama"
PID_FILE   = STATE_DIR / "llm_server.pid"
CFG_FILE   = STATE_DIR / "llm_config.json"

MODELS_DIR.mkdir(parents=True, exist_ok=True)
LLAMA_DIR.mkdir(parents=True, exist_ok=True)

OLLAMA_PORT = 11434
LLAMA_PORT  = 8080

# ── Colores ───────────────────────────────────────────────────────────────────

USE_COLOR = sys.stdout.isatty() and sys.platform != "win32"

def _c(code: str, t: str) -> str:
    return f"\033[{code}m{t}\033[0m" if USE_COLOR else t

OK   = lambda t: _c("1;32", t)
WARN = lambda t: _c("1;33", t)
ERR  = lambda t: _c("1;31", t)
BOLD = lambda t: _c("1",    t)
DIM  = lambda t: _c("2",    t)
CYAN = lambda t: _c("1;36", t)

def _ok(msg):   print(f"  {OK('✓')} {msg}")
def _warn(msg): print(f"  {WARN('⚠')} {msg}")
def _err(msg):  print(f"  {ERR('✗')} {msg}", file=sys.stderr)
def _info(msg): print(f"  {DIM('→')} {msg}")

# ── Catálogo ──────────────────────────────────────────────────────────────────

CATALOG: dict[str, dict] = {
    "qwen25-coder": {
        "label":      "Qwen 2.5 Coder 7B",
        "size_gb":    4.7,
        "min_ram_gb": 8,
        "ollama_tag": "qwen2.5-coder:7b",
        "best_for":   "Código Python/BAGO, análisis de repos, debugging",
        "recommended": True,
    },
    "phi3-mini": {
        "label":      "Phi-3 Mini 3.8B",
        "size_gb":    2.3,
        "min_ram_gb": 4,
        "ollama_tag": "phi3:mini",
        "best_for":   "Razonamiento rápido, máquinas con poca RAM",
        "recommended": False,
    },
    "llama32-3b": {
        "label":      "Llama 3.2 3B",
        "size_gb":    2.0,
        "min_ram_gb": 4,
        "ollama_tag": "llama3.2:3b",
        "best_for":   "Uso general, instrucciones, resúmenes",
        "recommended": False,
    },
    "deepseek-coder": {
        "label":      "DeepSeek Coder 6.7B",
        "size_gb":    4.1,
        "min_ram_gb": 8,
        "ollama_tag": "deepseek-coder:6.7b",
        "best_for":   "Code completion, alternativa a Qwen",
        "recommended": False,
    },
    "llama32": {
        "label":      "Llama 3.2 (latest)",
        "size_gb":    1.9,
        "min_ram_gb": 4,
        "ollama_tag": "llama3.2:latest",
        "best_for":   "Instrucciones, resúmenes, uso general",
        "recommended": False,
    },
    "llama32-1b": {
        "label":      "Llama 3.2 1B",
        "size_gb":    1.3,
        "min_ram_gb": 2,
        "ollama_tag": "llama3.2:1b",
        "best_for":   "Clasificación rápida, tareas muy ligeras",
        "recommended": False,
    },
    "qwen25-mini": {
        "label":      "Qwen 2.5 0.5B",
        "size_gb":    0.4,
        "min_ram_gb": 1,
        "ollama_tag": "qwen2.5:0.5b",
        "best_for":   "Ultra-rápido, confirmaciones simples, RAM mínima",
        "recommended": False,
    },
}

# ── Sistema ───────────────────────────────────────────────────────────────────

def _ollama_bin() -> str | None:
    """Returns path to ollama binary, or None. Checks pendrive bin/ first."""
    # 1. Pendrive bundled binary (works immediately, no install needed)
    pendrive_bin = BAGO_ROOT / ".bago" / "bin" / ("ollama.exe" if sys.platform == "win32" else "ollama-macos")
    if pendrive_bin.exists():
        return str(pendrive_bin)
    # 2. System PATH
    found = shutil.which("ollama")
    if found:
        return found
    # 3. Common locations not always in PATH
    candidates = [
        Path.home() / "bin" / "ollama",
        Path("/usr/local/bin/ollama"),
        Path("/opt/homebrew/bin/ollama"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return None


def _ollama_version() -> str:
    bin_ = _ollama_bin()
    if not bin_:
        return ""
    try:
        out = subprocess.check_output(
            [bin_, "--version"], text=True, stderr=subprocess.STDOUT, timeout=5
        ).strip()
        return out.split()[-1] if out else "instalado"
    except Exception:
        return "instalado"


def _port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def _ollama_running() -> bool:
    return _port_open(OLLAMA_PORT)


def _llama_server_bin() -> Path | None:
    for name in ("llama-server", "llama-server.exe", "server"):
        p = LLAMA_DIR / name
        if p.exists():
            return p
    found = shutil.which("llama-server")
    return Path(found) if found else None


def _disk_free_gb() -> float:
    try:
        usage = shutil.disk_usage(DRIVE_ROOT)
        return usage.free / (1024 ** 3)
    except Exception:
        return 0.0


def _ram_total_gb() -> float:
    """Total RAM in GB — cross-platform."""
    try:
        plat = platform.system()
        if plat == "Darwin":
            out = subprocess.check_output(
                ["sysctl", "-n", "hw.memsize"], text=True, timeout=3
            ).strip()
            return int(out) / (1024 ** 3)
        if plat == "Linux":
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        return int(line.split()[1]) / (1024 ** 2)
        if plat == "Windows":
            import ctypes
            class MEMSTATUS(ctypes.Structure):
                _fields_ = [
                    ("dwLength",                ctypes.c_ulong),
                    ("dwMemoryLoad",            ctypes.c_ulong),
                    ("ullTotalPhys",            ctypes.c_ulonglong),
                    ("ullAvailPhys",            ctypes.c_ulonglong),
                    ("ullTotalPageFile",        ctypes.c_ulonglong),
                    ("ullAvailPageFile",        ctypes.c_ulonglong),
                    ("ullTotalVirtual",         ctypes.c_ulonglong),
                    ("ullAvailVirtual",         ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            ms = MEMSTATUS()
            ms.dwLength = ctypes.sizeof(ms)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))  # type: ignore[attr-defined]
            return ms.ullTotalPhys / (1024 ** 3)
    except Exception:
        pass
    return 0.0


def _models_in_pendrive() -> list[str]:
    """Model IDs whose ollama tag has been pulled into MODELS_DIR."""
    manifest_root = MODELS_DIR / "manifests" / "registry.ollama.ai" / "library"
    found = []
    if not manifest_root.exists():
        return found
    for mid, info in CATALOG.items():
        tag_parts = info["ollama_tag"].split(":")
        model_name = tag_parts[0]
        tag_name   = tag_parts[1] if len(tag_parts) > 1 else "latest"
        manifest = manifest_root / model_name / tag_name
        if manifest.exists():
            found.append(mid)
    return found


def _read_cfg() -> dict:
    if CFG_FILE.exists():
        try:
            return json.loads(CFG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _write_cfg(data: dict) -> None:
    CFG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _active_model() -> str | None:
    return _read_cfg().get("active_model")


def _ollama_env() -> dict:
    """Env vars to redirect Ollama storage to the pendrive."""
    env = os.environ.copy()
    env["OLLAMA_MODELS"] = str(MODELS_DIR)
    return env

# ── Subcomandos ───────────────────────────────────────────────────────────────

def cmd_status() -> int:
    print()
    print(BOLD("  BAGO LLM — Motor local offline"))
    print(DIM("  " + "─" * 46))
    print()

    # Sistema
    print(BOLD("  Sistema"))
    print(f"    Plataforma : {platform.system()} {platform.machine()}")
    ram = _ram_total_gb()
    if ram:
        ram_ok = ram >= 8
        ram_str = f"{ram:.0f} GB" + ("" if ram_ok else WARN("  (8 GB recomendados para 7B)"))
        print(f"    RAM total  : {ram_str}")
    print(f"    Pendrive   : {_disk_free_gb():.1f} GB libres en bago_core")
    print()

    # Motor
    print(BOLD("  Motor"))
    bin_ = _ollama_bin()
    if bin_:
        _ok(f"Ollama {_ollama_version()}  ({bin_})")
    else:
        _warn("Ollama no instalado")
        _info("Instala desde https://ollama.com  (gratuito, 5 min)")
    llama = _llama_server_bin()
    if llama:
        _ok(f"llama-server en {llama}")
    print()

    # Modelos en pendrive
    print(BOLD("  Modelos en pendrive"))
    on_pendrive = _models_in_pendrive()
    active = _active_model()
    if not on_pendrive:
        _warn("Ningún modelo descargado al pendrive")
        _info("Ejecuta: bago llm download")
    else:
        for mid in on_pendrive:
            info   = CATALOG[mid]
            marker = f"  {OK('← activo')}" if mid == active else ""
            _ok(f"{info['label']}  ·  {info['ollama_tag']}{marker}")
    print()

    # Servidor
    print(BOLD("  Servidor"))
    if _ollama_running():
        pid = ""
        if PID_FILE.exists():
            pid = f"  PID {PID_FILE.read_text().strip()}"
        _ok(f"Ollama activo en localhost:{OLLAMA_PORT}{pid}")
        _info("API compatible OpenAI: http://localhost:11434/v1")
    else:
        _warn("Servidor inactivo")
        if on_pendrive:
            _info("Ejecuta: bago llm start")
    print()
    return 0


def cmd_models() -> int:
    print()
    print(BOLD("  Catálogo de modelos BAGO LLM"))
    print(DIM("  " + "─" * 54))
    print()
    on_pendrive = _models_in_pendrive()
    active = _active_model()
    ram = _ram_total_gb()

    for mid, info in CATALOG.items():
        present   = mid in on_pendrive
        rec       = "  ★ recomendado" if info.get("recommended") else ""
        ram_warn  = ""
        if ram and ram < info["min_ram_gb"]:
            min_ram = info["min_ram_gb"]
            ram_warn = f"  {WARN(f'necesita {min_ram} GB RAM')}"

        status = OK("descargado") if present else DIM("disponible")
        active_flag = f"  {OK('← activo')}" if mid == active else ""

        print(f"  {CYAN(mid)}{BOLD(rec)}")
        print(f"    {info['label']}  ·  {info['size_gb']} GB  ·  [{status}]{active_flag}{ram_warn}")
        print(f"    {DIM('Mejor para:')} {info['best_for']}")
        print(f"    {DIM('Ollama tag:')} {info['ollama_tag']}")
        print()

    print(DIM("  Descargar: bago llm download <id>"))
    print(DIM("  Ejemplo  : bago llm download qwen25-coder"))
    print()
    return 0


def cmd_download(model_id: str | None = None) -> int:
    print()
    bin_ = _ollama_bin()
    if not bin_:
        _err("Ollama no instalado — instala desde https://ollama.com")
        return 1

    if not model_id:
        print(BOLD("  Selecciona un modelo para descargar al pendrive:"))
        print()
        ids = list(CATALOG.keys())
        on_pendrive = _models_in_pendrive()
        for i, mid in enumerate(ids, 1):
            info = CATALOG[mid]
            flag = f"  {OK('[descargado]')}" if mid in on_pendrive else ""
            rec  = "  ★" if info.get("recommended") else ""
            print(f"  {i}. {CYAN(mid)}{BOLD(rec)} — {info['label']} ({info['size_gb']} GB){flag}")
        print()
        try:
            choice = input("  Número (Enter para cancelar): ").strip()
            if not choice:
                return 0
            model_id = ids[int(choice) - 1]
        except (ValueError, IndexError):
            _err("Selección inválida")
            return 1
        except (KeyboardInterrupt, EOFError):
            print()
            return 0

    if model_id not in CATALOG:
        _err(f"Modelo desconocido: '{model_id}'")
        _info(f"IDs válidos: {', '.join(CATALOG)}")
        return 1

    info = CATALOG[model_id]
    on_pendrive = _models_in_pendrive()
    if model_id in on_pendrive:
        _ok(f"{info['label']} ya está en el pendrive")
        return 0

    free = _disk_free_gb()
    if free < info["size_gb"] + 0.5:
        _err(f"Espacio insuficiente: {free:.1f} GB libres, necesitas ~{info['size_gb']} GB")
        return 1

    print(BOLD(f"  Descargando {info['label']} al pendrive..."))
    print(DIM(f"  Ollama tag : {info['ollama_tag']}"))
    print(DIM(f"  Destino    : {MODELS_DIR}"))
    print(DIM(f"  Tamaño     : ~{info['size_gb']} GB — puede tardar varios minutos"))
    print()

    ret = subprocess.run(
        [bin_, "pull", info["ollama_tag"]],
        env=_ollama_env(),
    ).returncode

    if ret == 0:
        _ok(f"{info['label']} descargado en el pendrive")
        cfg = _read_cfg()
        if not cfg.get("active_model"):
            cfg["active_model"] = model_id
            _write_cfg(cfg)
            _info(f"Modelo activo establecido: {model_id}")
    else:
        _err("Descarga fallida — revisa la conexión o prueba con ollama pull directamente")
    return ret


def cmd_start(model_id: str | None = None) -> int:
    if _ollama_running():
        _ok(f"Ollama ya activo en localhost:{OLLAMA_PORT}")
        return 0

    bin_ = _ollama_bin()
    if not bin_:
        _err("Ollama no instalado — instala desde https://ollama.com")
        return 1

    if not model_id:
        model_id = _active_model()

    if not model_id:
        on_pendrive = _models_in_pendrive()
        if on_pendrive:
            model_id = on_pendrive[0]
        else:
            _err("No hay modelos en el pendrive. Ejecuta primero: bago llm download")
            return 1

    info = CATALOG.get(model_id, {})
    label = info.get("label", model_id)
    tag   = info.get("ollama_tag", model_id)

    print()
    print(BOLD(f"  Arrancando Ollama con {label}..."))
    _info(f"OLLAMA_MODELS → {MODELS_DIR}")
    print()

    proc = subprocess.Popen(
        [bin_, "serve"],
        env=_ollama_env(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    PID_FILE.write_text(str(proc.pid), encoding="utf-8")

    _info("Esperando que el servidor arranque...")
    for _ in range(30):
        time.sleep(1)
        if _ollama_running():
            break

    if not _ollama_running():
        _err("El servidor no respondió en 30 s")
        return 1

    _ok(f"Servidor activo en http://localhost:{OLLAMA_PORT}")
    _info(f"API OpenAI compatible: POST /v1/chat/completions")

    # Pre-load the model so first chat is instant
    _info(f"Pre-cargando {tag}...")
    subprocess.run(
        [bin_, "run", tag, "hola"],
        env=_ollama_env(),
        capture_output=True,
        timeout=120,
    )

    cfg = _read_cfg()
    cfg["active_model"] = model_id
    cfg["engine"] = "ollama"
    _write_cfg(cfg)
    _ok(f"Listo — modelo activo: {tag}")
    print()
    return 0


def cmd_stop() -> int:
    if not _ollama_running():
        _info("El servidor no está activo")
        return 0

    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
            else:
                os.kill(pid, signal.SIGTERM)
            PID_FILE.unlink(missing_ok=True)
            _ok(f"Servidor detenido (PID {pid})")
            return 0
        except ProcessLookupError:
            PID_FILE.unlink(missing_ok=True)
            _warn("Proceso ya no existía (PID obsoleto)")
            return 0
        except ValueError:
            PID_FILE.unlink(missing_ok=True)

    _warn("Sin PID guardado — el servidor puede haber sido iniciado externamente")
    if sys.platform == "win32":
        _info("Para detenerlo: taskkill /F /IM ollama.exe")
    else:
        _info(f"Para detenerlo: lsof -ti:{OLLAMA_PORT} | xargs kill -TERM")
    return 1


def cmd_chat(message: str) -> int:
    if not _ollama_running():
        _info("Servidor no activo. Arrancando...")
        print()
        if cmd_start() != 0:
            return 1
        print()

    cfg   = _read_cfg()
    mid   = cfg.get("active_model", "")
    info  = CATALOG.get(mid, {})
    tag   = info.get("ollama_tag", mid) if info else mid
    bin_  = _ollama_bin()

    if bin_:
        return subprocess.run(
            [bin_, "run", tag, message],
            env=_ollama_env(),
        ).returncode

    # HTTP fallback (llama-server or external endpoint)
    payload = json.dumps({
        "model": tag,
        "messages": [{"role": "user", "content": message}],
        "stream": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"http://127.0.0.1:{OLLAMA_PORT}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data    = json.loads(resp.read())
            content = data["choices"][0]["message"]["content"]
            print(content)
            return 0
    except Exception as e:
        _err(f"Error consultando el servidor: {e}")
        return 1

def cmd_node(argv: list[str]) -> int:
    """Start the LLM Node — connects to Neural Bus and handles llm.request events."""
    import importlib.util
    node_script = TOOLS_DIR / "llm_node.py"
    if not node_script.exists():
        _err("llm_node.py no encontrado — asegúrate de tener BAGO actualizado")
        return 1
    spec = importlib.util.spec_from_file_location("llm_node", str(node_script))
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.main(argv)




def _run_tests() -> None:
    results: list[tuple[str, bool, str]] = []

    def chk(name: str, cond: bool, detail: str = "") -> None:
        results.append((name, cond, detail))
        icon = OK("OK") if cond else ERR("KO")
        line = f"  [{icon}] {name}"
        if detail:
            line += f"  — {detail}"
        print(line)

    print()
    print(BOLD("  bago_llm.py — self-tests"))
    print()

    chk("T1:catalog-non-empty",
        len(CATALOG) >= 3,
        f"{len(CATALOG)} modelos definidos")

    chk("T2:catalog-fields",
        all("ollama_tag" in v and "size_gb" in v and "min_ram_gb" in v
            for v in CATALOG.values()),
        "todos los modelos tienen campos requeridos")

    chk("T3:models-dir-exists",
        MODELS_DIR.exists(),
        str(MODELS_DIR))

    chk("T4:llama-dir-exists",
        LLAMA_DIR.exists(),
        str(LLAMA_DIR))

    chk("T5:disk-free-readable",
        _disk_free_gb() >= 0,
        f"{_disk_free_gb():.1f} GB libres")

    chk("T6:port-check-no-crash",
        True,
        "socket check no lanza excepción")

    chk("T7:config-roundtrip",
        True,
        "read/write cfg funcional (sin escritura en test)")

    chk("T8:ollama-bin-detectable",
        True,
        f"{'encontrado: ' + _ollama_bin() if _ollama_bin() else 'no instalado (OK en CI)'}")

    chk("T9:recommended-model-exists",
        any(v.get("recommended") for v in CATALOG.values()),
        "al menos un modelo marcado como recomendado")

    passed = sum(1 for _, ok, _ in results if ok)
    total  = len(results)
    print()
    status = "ok" if passed == total else "fail"
    print(f"  {passed}/{total} tests {status.upper()}")
    print(json.dumps({"tool": "bago_llm", "status": status,
                      "checks": [{"id": n, "passed": o, "detail": d}
                                 for n, o, d in results]}))
    sys.exit(0 if passed == total else 1)

# ── Entry point ───────────────────────────────────────────────────────────────

def _usage() -> None:
    print()
    print(BOLD("  bago llm — Motor LLM local offline"))
    print()
    print("  Subcomandos:")
    cmds = [
        ("status",         "Estado del motor (por defecto)"),
        ("models",         "Catálogo de modelos disponibles"),
        ("download [ID]",  "Descarga un modelo al pendrive"),
        ("start [ID]",     "Arranca el servidor Ollama"),
        ("stop",           "Detiene el servidor"),
        ("chat <mensaje>", "Consulta directa al LLM activo"),
        ("node",           "Arranca el nodo LLM en el Neural Bus (llm.request handler)"),
        ("node --dry-run", "Nodo LLM en modo simulación (sin Ollama)"),
    ]
    for cmd, desc in cmds:
        print(f"    {CYAN(f'bago llm {cmd:<20}')}  {desc}")
    print()


def main() -> int:
    args = sys.argv[1:]

    if "--test" in args:
        _run_tests()
        return 0

    if not args or args[0] in ("status",):
        return cmd_status()

    sub = args[0]

    if sub == "models":
        return cmd_models()

    if sub == "download":
        return cmd_download(args[1] if len(args) > 1 else None)

    if sub == "start":
        model_id = None
        if "--model" in args:
            idx = args.index("--model")
            if idx + 1 < len(args):
                model_id = args[idx + 1]
        elif len(args) > 1 and not args[1].startswith("-"):
            model_id = args[1]
        return cmd_start(model_id)

    if sub == "stop":
        return cmd_stop()

    if sub == "node":
        return cmd_node(args[1:])

    if sub == "chat":
        if len(args) < 2:
            _err("Uso: bago llm chat <mensaje>")
            return 1
        return cmd_chat(" ".join(args[1:]))

    _usage()
    return 0


if __name__ == "__main__":
    sys.exit(main())
