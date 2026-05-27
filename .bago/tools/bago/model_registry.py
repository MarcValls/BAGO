"""Normalizacion de IDs de modelos y reporte de accesibilidad por proveedor."""

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

from dataclasses import dataclass
from typing import Iterable

from rich import box
from rich.panel import Panel
from rich.table import Table

from .provider_health import scan_provider_health


@dataclass(frozen=True)
class LocalModelEntry:
    model_id: str
    label: str
    ollama_tag: str
    size_gb: float
    min_ram_gb: int
    best_for: str
    aliases: tuple[str, ...] = ()


LOCAL_MODELS: dict[str, LocalModelEntry] = {
    "qwen25-coder": LocalModelEntry(
        model_id="qwen25-coder",
        label="Qwen 2.5 Coder 7B",
        ollama_tag="qwen2.5-coder:7b",
        size_gb=4.7,
        min_ram_gb=8,
        best_for="Codigo, debugging, analisis de repos",
        aliases=("qwen2.5-coder", "qwen2.5-coder:7b", "qwen25 coder", "qwen coder"),
    ),
    "phi3-mini": LocalModelEntry(
        model_id="phi3-mini",
        label="Phi-3 Mini 3.8B",
        ollama_tag="phi3:mini",
        size_gb=2.3,
        min_ram_gb=4,
        best_for="Razonamiento rapido y tareas ligeras",
        aliases=("phi3:mini", "phi-3-mini", "phi 3 mini", "phi3 mini"),
    ),
    "llama32-3b": LocalModelEntry(
        model_id="llama32-3b",
        label="Llama 3.2 3B",
        ollama_tag="llama3.2:3b",
        size_gb=2.0,
        min_ram_gb=4,
        best_for="Uso general, instrucciones, resmenes",
        aliases=("llama3.2:3b", "llama3.2-3b", "llama 3.2 3b"),
    ),
    "deepseek-coder": LocalModelEntry(
        model_id="deepseek-coder",
        label="DeepSeek Coder 6.7B",
        ollama_tag="deepseek-coder:6.7b",
        size_gb=4.1,
        min_ram_gb=8,
        best_for="Code completion y alternativa a Qwen",
        aliases=("deepseek-coder:6.7b", "deepseek coder", "deepseek coder 6.7b"),
    ),
    "granite3.2": LocalModelEntry(
        model_id="granite3.2",
        label="IBM Granite 3.2 8B",
        ollama_tag="granite3.2:8b",
        size_gb=4.9,
        min_ram_gb=8,
        best_for="Codigo, RAG y razonamiento empresarial",
        aliases=("granite3.2:8b", "granite 3.2 8b", "ibm granite 3.2 8b", "granite"),
    ),
    "llama32": LocalModelEntry(
        model_id="llama32",
        label="Llama 3.2 (latest)",
        ollama_tag="llama3.2:latest",
        size_gb=1.9,
        min_ram_gb=4,
        best_for="Instrucciones, resmenes, uso general",
        aliases=("llama3.2", "llama3.2:latest", "llama 3.2", "llama32 latest"),
    ),
    "llama32-1b": LocalModelEntry(
        model_id="llama32-1b",
        label="Llama 3.2 1B",
        ollama_tag="llama3.2:1b",
        size_gb=1.3,
        min_ram_gb=2,
        best_for="Clasificacion rapida y tareas muy ligeras",
        aliases=("llama3.2:1b", "llama3.2-1b", "llama 3.2 1b"),
    ),
    "qwen25-mini": LocalModelEntry(
        model_id="qwen25-mini",
        label="Qwen 2.5 0.5B",
        ollama_tag="qwen2.5:0.5b",
        size_gb=0.4,
        min_ram_gb=1,
        best_for="Ultra-rapido y confirmaciones simples",
        aliases=("qwen2.5:0.5b", "qwen2.5-mini", "qwen 2.5 0.5b"),
    ),
    "smollm2": LocalModelEntry(
        model_id="smollm2",
        label="SmolLM2 1.7B",
        ollama_tag="smollm2:1.7b",
        size_gb=1.1,
        min_ram_gb=2,
        best_for="Tasks simples, edge y maquinas muy limitadas",
        aliases=("smollm2:1.7b", "smollm2 1.7b", "smollm2 1.7", "smollm2"),
    ),
}


_MODEL_REF_TO_ID: dict[str, str] = {}
_MODEL_REF_COMPACT_TO_ID: dict[str, str] = {}


def _compact(text: str) -> str:
    return "".join(ch for ch in text.lower().strip() if ch.isalnum())


def _register(ref: str, model_id: str) -> None:
    ref = ref.strip().lower()
    if ref:
        _MODEL_REF_TO_ID[ref] = model_id
        _MODEL_REF_COMPACT_TO_ID[_compact(ref)] = model_id


for _mid, _entry in LOCAL_MODELS.items():
    _register(_mid, _mid)
    _register(_entry.label, _mid)
    _register(_entry.ollama_tag, _mid)
    for _alias in _entry.aliases:
        _register(_alias, _mid)


def normalize_local_model_id(model_ref: str | None) -> str | None:
    if not model_ref:
        return None
    raw = model_ref.strip()
    if not raw:
        return None
    low = raw.lower()
    if low in _MODEL_REF_TO_ID:
        return _MODEL_REF_TO_ID[low]
    compact = _compact(raw)
    return _MODEL_REF_COMPACT_TO_ID.get(compact)


def local_model_tag(model_ref: str | None) -> str | None:
    model_id = normalize_local_model_id(model_ref)
    if not model_id:
        return None
    return LOCAL_MODELS[model_id].ollama_tag


def iter_local_models() -> Iterable[LocalModelEntry]:
    return LOCAL_MODELS.values()


def _provider_models_from_health(provider_name: str, health: dict, providers: dict) -> tuple[list[str], str]:
    models = list(health.get("models") or [])
    if models:
        return models, "scan"

    configured = list((providers.get(provider_name, {}) or {}).get("models", {}).keys())
    if configured:
        return configured, "config"

    return [], "none"


def print_accessible_models_report(session, timeout: int = 4) -> int:
    """Imprime un mapa de modelos accesibles por proveedor activo."""
    from .ui import console

    health = scan_provider_health(session.creds, session.providers, timeout=timeout)
    rows: list[tuple[str, str, str, str]] = []

    for provider_name in sorted(health.keys()):
        h = health.get(provider_name, {})
        ok = bool(h.get("ok"))
        models, source = _provider_models_from_health(provider_name, h, session.providers)
        status = "OK" if ok else "NO"
        detail = h.get("detail", "sin detalle")
        configured = list((session.providers.get(provider_name, {}) or {}).get("models", {}).keys())
        if ok and models:
            preview = ", ".join(models[:8])
            if len(models) > 8:
                preview += f" +{len(models) - 8} mas"
        elif not ok and configured:
            preview = f"sin modelos accesibles (configurados: {', '.join(configured[:8])}{'...' if len(configured) > 8 else ''})"
        else:
            preview = "sin modelos accesibles"
        if not ok and configured:
            detail = f"{detail} | catalogo configurado: {len(configured)}"
        rows.append((provider_name, status, source, preview))
        console.print(
            Panel(
                f"[bold]Estado:[/bold] {status}\n"
                f"[bold]Detalle:[/bold] {detail}\n"
                f"[bold]Modelos:[/bold] {preview}",
                title=f"[bold]{provider_name}[/bold]",
                box=box.ROUNDED,
                expand=False,
            )
        )

    if not rows:
        console.print(Panel("Sin providers activos.", title="Modelos accesibles", box=box.ROUNDED))
        return 0

    table = Table(title="Mapa de accesibilidad", box=box.SIMPLE)
    table.add_column("Provider", style="cyan", no_wrap=True)
    table.add_column("Estado", style="green")
    table.add_column("Origen", style="yellow")
    table.add_column("Modelos accesibles", style="white")
    for provider_name, status, source, preview in rows:
        table.add_row(provider_name, status, source, preview)
    console.print(table)
    return 0


def main(argv: list[str] | None = None) -> int:
    from .providers import load_providers

    class _MiniCreds:
        def is_provider_enabled(self, _prov: str) -> bool:
            return True

    class _MiniSession:
        def __init__(self):
            self.creds = _MiniCreds()
            self.providers = load_providers()

    args = list(argv if argv is not None else sys.argv[1:])
    action = (args[0].lower() if args else "detect").strip()

    if action in ("-h", "--help", "help"):
        print("Uso:")
        print("  python -m bago.model_registry detect")
        print("  python -m bago.model_registry accessible")
        print("  python -m bago.model_registry scan")
        return 0

    if action in ("detect", "accessible", "scan", "list"):
        session = _MiniSession()
        return print_accessible_models_report(session, timeout=2)

    print(f"Comando desconocido: {action}")
    return 1
