"""
BAGO Hardware Probe — detecta RAM, GPU, disco y clasifica modelos por viabilidad.

Sin dependencias externas: usa subprocess + stdlib.
"""

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

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional


# ─── Resultado del análisis ───────────────────────────────────────────────────

@dataclass
class HWInfo:
    # RAM
    ram_total_gb: float = 0.0
    ram_free_gb:  float = 0.0
    # GPU
    gpu_name:     str   = ""
    gpu_vram_gb:  float = 0.0       # VRAM total
    gpu_free_gb:  float = 0.0       # VRAM libre ahora
    has_gpu:      bool  = False
    # Disco (donde viven los modelos)
    disk_path:    str   = ""
    disk_free_gb: float = 0.0
    disk_total_gb: float = 0.0
    # CPU
    cpu_name:     str   = ""
    cpu_cores:    int   = 0
    # OS
    os_name:      str   = ""
    # Errores de detección
    errors:       list[str] = field(default_factory=list)


# ─── Detección ────────────────────────────────────────────────────────────────

def _run(cmd: str, timeout: int = 5) -> str:
    try:
        return subprocess.check_output(
            cmd, shell=True, text=True,
            stderr=subprocess.DEVNULL, timeout=timeout,
        ).strip()
    except Exception:
        return ""


def _detect_ram_windows() -> tuple[float, float]:
    """Devuelve (total_gb, free_gb) leyendo wmic."""
    out = _run("wmic OS get TotalVisibleMemorySize,FreePhysicalMemory /format:csv")
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) == 3 and parts[1].isdigit():
            free_kb  = int(parts[1])
            total_kb = int(parts[2])
            return total_kb / 1_048_576, free_kb / 1_048_576
    return 0.0, 0.0


def _detect_ram_linux() -> tuple[float, float]:
    try:
        with open("/proc/meminfo") as f:
            data = f.read()
        total = free = avail = 0
        for line in data.splitlines():
            if line.startswith("MemTotal:"):
                total = int(line.split()[1])
            elif line.startswith("MemAvailable:"):
                avail = int(line.split()[1])
        return total / 1_048_576, avail / 1_048_576
    except Exception:
        return 0.0, 0.0


def _detect_ram() -> tuple[float, float]:
    if platform.system() == "Windows":
        return _detect_ram_windows()
    return _detect_ram_linux()


def _detect_nvidia() -> tuple[str, float, float]:
    """Devuelve (nombre, vram_total_gb, vram_free_gb). ("",-1,-1) si no hay NVIDIA."""
    out = _run("nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader")
    if not out:
        return "", 0.0, 0.0
    # Puede haber varias GPUs; usamos la primera
    line = out.splitlines()[0]
    parts = [p.strip() for p in line.split(",")]
    if len(parts) < 3:
        return "", 0.0, 0.0
    name = parts[0]
    try:
        total_mb = float(parts[1].split()[0])
        free_mb  = float(parts[2].split()[0])
        return name, total_mb / 1024, free_mb / 1024
    except (ValueError, IndexError):
        return name, 0.0, 0.0


def _detect_amd() -> tuple[str, float, float]:
    """Intenta rocm-smi para GPUs AMD."""
    out = _run("rocm-smi --showmeminfo vram --csv")
    if not out:
        return "", 0.0, 0.0
    lines = out.splitlines()
    if len(lines) < 2:
        return "", 0.0, 0.0
    parts = lines[1].split(",")
    try:
        total_bytes = int(parts[1].strip())
        used_bytes  = int(parts[2].strip())
        free_bytes  = total_bytes - used_bytes
        return "AMD GPU", total_bytes / 1e9, free_bytes / 1e9
    except Exception:
        return "", 0.0, 0.0


def _detect_cpu() -> tuple[str, int]:
    name = ""
    if platform.system() == "Windows":
        name = _run("wmic cpu get Name /format:value").replace("Name=", "").strip()
    elif platform.system() == "Darwin":
        name = _run("sysctl -n machdep.cpu.brand_string")
    else:
        for line in _run("cat /proc/cpuinfo").splitlines():
            if "model name" in line:
                name = line.split(":")[-1].strip()
                break
    cores = os.cpu_count() or 0
    return name[:60], cores


def _models_disk_path() -> str:
    """Devuelve la ruta donde Ollama guarda los modelos."""
    env = os.environ.get("OLLAMA_MODELS", "")
    if env and os.path.exists(env):
        return env
    # Rutas por defecto de Ollama
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, ".ollama", "models"),           # Linux / Windows default
        os.path.join(home, "Library", "Application Support", "Ollama", "models"),  # macOS
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    # Fallback: directorio del usuario
    return home


@lru_cache(maxsize=1)
def probe_hardware() -> HWInfo:
    """Detecta hardware y devuelve HWInfo. Resultado en caché (sólo se detecta 1 vez)."""
    hw = HWInfo()
    hw.os_name = f"{platform.system()} {platform.release()}"

    # RAM
    hw.ram_total_gb, hw.ram_free_gb = _detect_ram()

    # GPU
    gpu_name, vram_total, vram_free = _detect_nvidia()
    if not gpu_name:
        gpu_name, vram_total, vram_free = _detect_amd()
    if gpu_name:
        hw.gpu_name    = gpu_name
        hw.gpu_vram_gb = vram_total
        hw.gpu_free_gb = vram_free
        hw.has_gpu     = True

    # Disco
    disk_path = _models_disk_path()
    hw.disk_path = disk_path
    try:
        usage = shutil.disk_usage(disk_path)
        hw.disk_free_gb  = usage.free  / 1e9
        hw.disk_total_gb = usage.total / 1e9
    except Exception as e:
        hw.errors.append(f"disco: {e}")

    # CPU
    hw.cpu_name, hw.cpu_cores = _detect_cpu()

    return hw


def invalidate_hw_cache() -> None:
    """Fuerza nueva detección en la próxima llamada a probe_hardware()."""
    probe_hardware.cache_clear()


# ─── Compatibilidad de modelos ────────────────────────────────────────────────

# Overhead de Ollama al cargar un modelo Q4 (factor sobre size_gb)
_RAM_OVERHEAD = 1.25   # necesitas ~25% más que el tamaño del archivo

# Margen de seguridad para considerar "recomendado" vs "podría funcionar"
_RAM_SAFE_MARGIN  = 1.15  # >= este margen → OK
_RAM_WARN_MARGIN  = 0.90  # >= este margen pero < safe → WARN
# < warn_margin → NO


@dataclass
class Compat:
    level: str      # "ok" | "warn" | "no"
    reason: str     # explicación breve
    disk_ok: bool   # ¿hay disco suficiente?
    disk_needed_gb: float


def model_compat(size_gb: float, hw: Optional[HWInfo] = None) -> Compat:
    """Clasifica la viabilidad de un modelo según el hardware.

    Reglas:
    - GPU primero: si VRAM total >= size_gb * 1.05 → ideal (GPU)
    - CPU: necesita free_ram >= size_gb * RAM_OVERHEAD
    - Split GPU+CPU (partial offload): si vram + free_ram cubre el modelo
    - Disco: necesita size_gb × 1.05 libres en el directorio de modelos
    """
    if hw is None:
        hw = probe_hardware()

    needed_ram  = size_gb * _RAM_OVERHEAD
    needed_disk = size_gb * 1.05

    # ── Disco ──────────────────────────────────────────────────────────────
    disk_ok = hw.disk_free_gb >= needed_disk

    # ── GPU total fit ───────────────────────────────────────────────────────
    if hw.has_gpu and hw.gpu_vram_gb >= size_gb * 1.05:
        reason = f"✓ Cabe en GPU ({hw.gpu_vram_gb:.1f} GB VRAM)"
        if not disk_ok:
            reason += f"  ⚠ disco: necesitas {needed_disk:.1f} GB, libres {hw.disk_free_gb:.1f} GB"
        return Compat("ok", reason, disk_ok, needed_disk)

    # ── CPU RAM fit ─────────────────────────────────────────────────────────
    if hw.ram_free_gb >= needed_ram * _RAM_SAFE_MARGIN:
        reason = f"✓ Cabe en RAM ({hw.ram_free_gb:.0f} GB libres)"
        if hw.has_gpu and hw.gpu_vram_gb > 0:
            reason += f"  (GPU {hw.gpu_vram_gb:.1f} GB demasiado pequeña para carga completa)"
        if not disk_ok:
            reason += f"  ⚠ disco: necesitas {needed_disk:.1f} GB"
        return Compat("ok", reason, disk_ok, needed_disk)

    # ── Zona de advertencia ─────────────────────────────────────────────────
    if hw.ram_free_gb >= needed_ram * _RAM_WARN_MARGIN:
        reason = (
            f"⚠  Ajustado ({hw.ram_free_gb:.0f}/{needed_ram:.0f} GB) — "
            f"puede ir lento o fallar si el sistema está cargado"
        )
        return Compat("warn", reason, disk_ok, needed_disk)

    # ── Split GPU+CPU (partial offload) ─────────────────────────────────────
    if hw.has_gpu:
        combined = hw.gpu_vram_gb + hw.ram_free_gb
        if combined >= needed_ram:
            reason = (
                f"⚠  Offload parcial GPU+RAM "
                f"({hw.gpu_vram_gb:.1f}+{hw.ram_free_gb:.0f} GB) — "
                f"funcionará pero más lento"
            )
            return Compat("warn", reason, disk_ok, needed_disk)

    # ── No hay suficiente memoria ───────────────────────────────────────────
    reason = (
        f"✗  Necesita ~{needed_ram:.0f} GB RAM, disponibles {hw.ram_free_gb:.0f} GB"
    )
    if hw.has_gpu:
        reason += f"  (VRAM {hw.gpu_vram_gb:.1f} GB insuficiente)"
    return Compat("no", reason, disk_ok, needed_disk)


# ─── Resumen legible ──────────────────────────────────────────────────────────

def hw_summary_lines(hw: Optional[HWInfo] = None) -> list[str]:
    """Devuelve líneas Rich para mostrar en un panel."""
    if hw is None:
        hw = probe_hardware()

    lines = []

    # CPU
    cpu = hw.cpu_name or "Desconocido"
    lines.append(f"  [bold]CPU[/bold]   {cpu}  [{hw.cpu_cores} núcleos]")

    # RAM
    ram_bar = "█" * int(min((hw.ram_total_gb - hw.ram_free_gb) / hw.ram_total_gb * 20, 20)) if hw.ram_total_gb else ""
    ram_bar += "░" * (20 - len(ram_bar))
    lines.append(
        f"  [bold]RAM[/bold]   {hw.ram_total_gb:.1f} GB total  ·  "
        f"[green]{hw.ram_free_gb:.1f} GB libres[/green]  [{ram_bar}]"
    )

    # GPU
    if hw.has_gpu:
        vram_used = hw.gpu_vram_gb - hw.gpu_free_gb
        vbar = "█" * int(min(vram_used / hw.gpu_vram_gb * 20, 20)) if hw.gpu_vram_gb else ""
        vbar += "░" * (20 - len(vbar))
        lines.append(
            f"  [bold]GPU[/bold]   {hw.gpu_name}  ·  "
            f"{hw.gpu_vram_gb:.1f} GB VRAM  ·  "
            f"[{'green' if hw.gpu_free_gb > 1 else 'yellow'}]{hw.gpu_free_gb:.1f} GB libres[/]  [{vbar}]"
        )
    else:
        lines.append("  [bold]GPU[/bold]   [dim]Sin GPU detectada (o sin nvidia-smi/rocm-smi)[/dim]")

    # Disco
    disk_color = "green" if hw.disk_free_gb > 20 else ("yellow" if hw.disk_free_gb > 5 else "red")
    lines.append(
        f"  [bold]Disco[/bold] {hw.disk_path}  ·  "
        f"[{disk_color}]{hw.disk_free_gb:.1f} GB libres[/{disk_color}]  "
        f"/ {hw.disk_total_gb:.1f} GB"
    )

    # OS
    lines.append(f"  [bold]OS[/bold]    {hw.os_name}")

    # Veredicto rápido
    lines.append("")
    if hw.ram_free_gb >= 20:
        tier = "[green bold]ALTO[/green bold]  — modelos hasta ~16 GB funcionarán bien"
    elif hw.ram_free_gb >= 10:
        tier = "[yellow bold]MEDIO[/yellow bold]  — modelos hasta ~8 GB recomendados"
    elif hw.ram_free_gb >= 4:
        tier = "[orange1 bold]BAJO[/orange1 bold]  — solo modelos <3 GB seguros"
    else:
        tier = "[red bold]MUY BAJO[/red bold]  — RAM insuficiente para casi cualquier LLM"
    lines.append(f"  [bold]Tier:[/bold]  {tier}")

    if hw.disk_free_gb < 5:
        lines.append(f"  [red]⚠  Disco muy bajo ({hw.disk_free_gb:.1f} GB). Libera espacio antes de instalar modelos.[/red]")

    return lines
