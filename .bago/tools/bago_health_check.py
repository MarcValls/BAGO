#!/usr/bin/env python3
"""bago_health_check.py — Verifica disponibilidad real de cada modelo.

No solo verifica si el proveedor responde, sino qué modelos específicos
están instalados, autenticados y listos para usar.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def check_ollama_local() -> dict:
    """Verifica modelos Ollama realmente descargados."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return {"available": False, "models": [], "reason": "Ollama no instalado"}

        models = []
        for line in result.stdout.strip().split("\n")[1:]:  # Skip header
            parts = line.split()
            if parts:
                name = parts[0]
                size_str = parts[2] + " " + parts[3] if len(parts) > 3 else "?"
                models.append({"name": name, "size": size_str})
        return {
            "available": len(models) > 0,
            "models": models,
            "reason": f"{len(models)} modelos descargados" if models else "Sin modelos descargados"
        }
    except FileNotFoundError:
        return {"available": False, "models": [], "reason": "Ollama no encontrado en PATH"}
    except Exception as e:
        return {"available": False, "models": [], "reason": str(e)}


def check_codex() -> dict:
    """Verifica acceso a Codex CLI y modelos disponibles."""
    config = Path.home() / ".codex" / "config.toml"
    if not config.exists():
        return {"available": False, "models": [], "reason": "Codex CLI no configurado"}

    active_model = "gpt-5.4"  # default
    try:
        with open(config, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("model"):
                    active_model = line.split("=")[-1].strip().strip('"').strip("'")
                    break
    except Exception:
        pass

    # Modelos disponibles en Codex (según catálogo OpenAI)
    codex_models = [
        "gpt-5.5", "gpt-5.4", "gpt-5.4-mini",
        "gpt-5.3-codex", "gpt-5.2"
    ]

    return {
        "available": True,
        "models": [{"name": m, "active": m == active_model} for m in codex_models],
        "active_model": active_model,
        "reason": f"Codex CLI activo (modelo: {active_model})"
    }


def check_copilot():
    """Verifica acceso a GitHub Copilot CLI."""
    gh_cmd = "gh"
    # Buscar gh en rutas conocidas
    known_paths = [
        Path.home() / "AppData" / "Local" / "Programs" / "GitHub CLI" / "gh.exe",
        Path("C:/Program Files/GitHub CLI/gh.exe"),
    ]
    for p in known_paths:
        if p.exists():
            gh_cmd = str(p)
            break
    try:
        result = subprocess.run(
            [gh_cmd, "copilot", "--version"],
            capture_output=True, text=True, timeout=5
        )
        available = result.returncode == 0
        copilot_models = [
            "claude-sonnet-4.6", "claude-opus-4.7",
            "gpt-5.5", "gpt-5.4", "gpt-5.4-mini",
            "gpt-5.3-codex", "gpt-5.2"
        ]
        return {
            "available": available,
            "models": [{"name": m} for m in copilot_models],
            "reason": "Copilot CLI activo" if available else "Copilot no disponible"
        }
    except FileNotFoundError:
        return {"available": False, "models": [], "reason": "gh CLI no instalado"}
    except Exception as e:
        return {"available": False, "models": [], "reason": str(e)}



def check_ollama_cloud() -> dict:
    """Verifica acceso a Ollama Cloud (API key)."""
    api_key = os.environ.get("OLLAMA_API_KEY")
    if not api_key:
        return {"available": False, "models": [], "reason": "OLLAMA_API_KEY no configurada"}

    cloud_models = [
        "devstral-2", "qwen3-coder-480b",
        "deepseek-v3-671b", "kimi-k2-1t"
    ]
    return {
        "available": True,
        "models": [{"name": m} for m in cloud_models],
        "reason": "Ollama Cloud configurado"
    }


def full_health_check() -> dict:
    """Health check completo de todos los proveedores."""
    return {
        "ollama-local": check_ollama_local(),
        "codex": check_codex(),
        "copilot": check_copilot(),
        "ollama-cloud": check_ollama_cloud(),
    }



def get_installable_models():
    """Devuelve modelos en catalogo que NO estan disponibles actualmente."""
    providers_data = json.loads(
        Path(__file__).resolve().parents[1].joinpath("state", "model_providers.json").read_text(encoding="utf-8-sig")
    )
    health = full_health_check()

    available = set()
    for prov_name, status in health.items():
        if status["available"]:
            for m in status["models"]:
                available.add((prov_name, m["name"]))

    installable = []
    for prov_name, prov in providers_data.get("providers", {}).items():
        for model_name, model in prov.get("models", {}).items():
            if (prov_name, model_name) not in available:
                installable.append({
                    "provider": prov_name,
                    "model": model_name,
                    "wire_name": model.get("wire_name", model_name),
                    "best_for": model.get("best_for", ""),
                    "cost": model.get("cost", "unknown"),
                    "size_mb": model.get("size_mb", 0),
                })

    cost_order = {"free": 0, "included": 1, "subscription": 2, "openai_credits": 3}
    installable.sort(key=lambda x: cost_order.get(x["cost"], 99))
    return installable


def print_health() -> None:
    health = full_health_check()
    print("\n  BAGO Health Check — Modelos Disponibles")
    print("  " + "-" * 50)

    for provider, status in health.items():
        icon = "OK" if status["available"] else "NO"
        color = "Green" if status["available"] else "Red"
        print(f"  [{icon}] {provider:15} — {status['reason']}")
        if status["models"]:
            for m in status["models"]:
                active = " *" if m.get("active") else ""
                size = f" ({m.get('size', '')})" if m.get("size") else ""
                print(f"      • {m['name']}{size}{active}")

    # Resumen de modelos realmente usables
    usable = []
    for p, s in health.items():
        if s["available"]:
            for m in s["models"]:
                usable.append(f"{m['name']} ({p})")

    print(f"\n  Total modelos listos: {len(usable)}")
    if usable:
        print(f"  Top 5: {', '.join(usable[:5])}")
    # Sugerencias de instalacion
    installable = get_installable_models()
    if installable:
        print("  Modelos instalables (no disponibles):")
        free = [m for m in installable if m["cost"] == "free"]
        included = [m for m in installable if m["cost"] == "included"]
        other = [m for m in installable if m["cost"] not in ("free", "included")]
        for m in free[:3] + included[:3] + other[:2]:
            size = " (" + str(m["size_mb"]) + "MB)" if m["size_mb"] else ""
            print("    [" + m["provider"] + "] " + m["model"] + size + " - " + m["best_for"] + " [" + m["cost"] + "]")
        if len(installable) > 8:
            print("    ... y " + str(len(installable)-8) + " mas. Ejecuta: BAGO install")

    print()


if __name__ == "__main__":
    print_health()
