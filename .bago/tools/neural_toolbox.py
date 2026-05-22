#!/usr/bin/env python3
"""neural_toolbox.py — BAGO Neural Toolbox: asignación dinámica de herramientas.

Motor de activación neural que selecciona las herramientas correctas para
un contexto dado. Cada herramienta es un "neurona" con un perfil de capacidades.
El contexto de la tarea activa las neuronas más relevantes (dot-product).

Principio de atomización:
  - _encode_context()   → solo codifica texto → señal (función pura)
  - _score_tool()       → solo calcula dot-product (función pura)
  - _derive_profile()   → solo extrae perfil de metadatos del registry (función pura)
  - NeuralToolbox.activate()  → combina las anteriores, filtra y rankea
  - NeuralToolbox.feedback()  → solo actualiza pesos del tool indicado
  - run_dynamic_workflow()    → orquesta activate + execute + feedback (efectos secundarios aquí)

Uso:
    python3 neural_toolbox.py --context "revisar seguridad del código"
    python3 neural_toolbox.py --context "mi código tiene errores de estilo"
    python3 neural_toolbox.py --context "preparar para producción" --scope framework
    python3 neural_toolbox.py --context "algo falla en el sistema" --explain
    python3 neural_toolbox.py --run "auditoría de calidad completa"
    python3 neural_toolbox.py --test

Códigos: NTB-I001 (activación OK), NTB-W001 (sin tools activados), NTB-E001 (error)
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import NamedTuple

# ── Rutas ─────────────────────────────────────────────────────────────────────
TOOLS_DIR    = Path(__file__).resolve().parent
BAGO_ROOT    = TOOLS_DIR.parent
PROJECT_ROOT = BAGO_ROOT.parent
BAGO_SCRIPT  = PROJECT_ROOT / "bago"
WEIGHTS_FILE = BAGO_ROOT / "state" / "toolbox_weights.json"

# ── Dominios de capacidad ─────────────────────────────────────────────────────
# Cada dominio representa una capacidad funcional. Las herramientas son evaluadas
# en este espacio. El contexto del usuario es codificado en el mismo espacio.
DOMAINS = (
    "security",      # auditoría de seguridad, secretos, vulnerabilidades
    "quality",       # calidad de código, lint, estilo, naming
    "testing",       # tests, CI, cobertura, checks
    "structure",     # arquitectura, dependencias, complejidad, refactoring
    "workflow",      # flujos de trabajo, tareas, sprints, sesiones
    "database",      # estado, historial, base de datos, inventario
    "communication", # notificaciones, mensajería, output al usuario
    "performance",   # rendimiento, eficiencia, métricas, velocidad
    "debug",         # diagnóstico, sanación, código muerto, stale
    "documentation", # docs, README, docstrings, changelog
)

# ── Señales del contexto: keywords → dominio ──────────────────────────────────
# Cada keyword activa su dominio con la intensidad dada [0.0, 1.0]
_CONTEXT_SIGNALS: dict[str, list[tuple[str, float]]] = {
    # security
    "secret":       [("security", 1.0)],
    "secreto":      [("security", 1.0)],
    "password":     [("security", 1.0)],
    "contraseña":   [("security", 1.0)],
    "token":        [("security", 0.9)],
    "credential":   [("security", 1.0)],
    "credencial":   [("security", 1.0)],
    "vulnerable":   [("security", 0.9)],
    "vulnerab":     [("security", 0.9)],
    "cve":          [("security", 1.0)],
    "inject":       [("security", 0.8)],
    "hardcode":     [("security", 0.8)],
    "seguridad":    [("security", 0.9)],
    "security":     [("security", 0.9)],
    "audit":        [("security", 0.7), ("quality", 0.4)],
    "auditoria":    [("security", 0.7), ("quality", 0.4)],
    "auditoría":    [("security", 0.7), ("quality", 0.4)],
    # quality
    "calidad":      [("quality", 1.0)],
    "quality":      [("quality", 1.0)],
    "lint":         [("quality", 1.0)],
    "estilo":       [("quality", 0.9)],
    "style":        [("quality", 0.9)],
    "naming":       [("quality", 0.8)],
    "docstring":    [("quality", 0.7), ("documentation", 0.7)],
    "legibilidad":  [("quality", 0.8)],
    "limpio":       [("quality", 0.9)],
    "clean":        [("quality", 0.9)],
    "duplicado":    [("quality", 0.7)],
    "duplicate":    [("quality", 0.7)],
    # testing
    "test":         [("testing", 1.0)],
    "tests":        [("testing", 1.0)],
    "ci":           [("testing", 0.9)],
    "cobertura":    [("testing", 0.9)],
    "coverage":     [("testing", 0.9)],
    "check":        [("testing", 0.6)],
    "verificar":    [("testing", 0.7)],
    "validar":      [("testing", 0.7), ("workflow", 0.4)],
    "produccion":   [("testing", 0.8), ("workflow", 0.6)],
    "producción":   [("testing", 0.8), ("workflow", 0.6)],
    "merge":        [("testing", 0.7), ("workflow", 0.5)],
    "commit":       [("testing", 0.6), ("workflow", 0.4)],
    # structure
    "complex":      [("structure", 1.0)],
    "complej":      [("structure", 1.0)],
    "refactor":     [("structure", 0.9)],
    "dependenc":    [("structure", 0.8)],
    "arquitectura": [("structure", 0.9)],
    "architecture": [("structure", 0.9)],
    "modulo":       [("structure", 0.7)],
    "module":       [("structure", 0.7)],
    "dead":         [("structure", 0.6), ("debug", 0.7)],
    "muerto":       [("structure", 0.6), ("debug", 0.7)],
    # workflow
    "workflow":     [("workflow", 1.0)],
    "flujo":        [("workflow", 1.0)],
    "sprint":       [("workflow", 0.9)],
    "tarea":        [("workflow", 0.9)],
    "task":         [("workflow", 0.9)],
    "session":      [("workflow", 0.8)],
    "sesion":       [("workflow", 0.8)],
    "sesión":       [("workflow", 0.8)],
    "plan":         [("workflow", 0.7)],
    "planif":       [("workflow", 0.8)],
    # database / state
    "estado":       [("database", 0.9)],
    "state":        [("database", 0.9)],
    "historial":    [("database", 0.8)],
    "history":      [("database", 0.8)],
    "db":           [("database", 1.0)],
    "base de dato": [("database", 1.0)],
    "inventario":   [("database", 0.8)],
    # communication
    "notif":        [("communication", 1.0)],
    "telegram":     [("communication", 1.0)],
    "whatsapp":     [("communication", 1.0)],
    "mensaje":      [("communication", 0.9)],
    "message":      [("communication", 0.9)],
    "notify":       [("communication", 1.0)],
    "alert":        [("communication", 0.8)],
    # performance
    "rendim":       [("performance", 1.0)],
    "performance":  [("performance", 1.0)],
    "eficien":      [("performance", 0.9)],
    "metric":       [("performance", 0.8)],
    "rapido":       [("performance", 0.8)],
    "lento":        [("performance", 0.9)],
    "slow":         [("performance", 0.9)],
    "optim":        [("performance", 0.9)],
    # debug
    "diagnos":      [("debug", 1.0)],
    "doctor":       [("debug", 1.0)],
    "falla":        [("debug", 0.9)],
    "error":        [("debug", 0.8)],
    "heal":         [("debug", 0.9)],
    "sanea":        [("debug", 0.9)],
    "stale":        [("debug", 0.8)],
    "obsolet":      [("debug", 0.7)],
    "roto":         [("debug", 0.9)],
    "broken":       [("debug", 0.9)],
    # documentation
    "doc":          [("documentation", 1.0)],
    "docs":         [("documentation", 1.0)],
    "readme":       [("documentation", 1.0)],
    "changelog":    [("documentation", 0.9)],
    "docstring":    [("documentation", 0.8), ("quality", 0.5)],
}


# ── Mapeo layer/scope → dominios base ─────────────────────────────────────────
_LAYER_DOMAINS: dict[str, list[tuple[str, float]]] = {
    "calidad":       [("quality", 0.6), ("testing", 0.4)],
    "seguridad":     [("security", 0.7)],
    "workflow":      [("workflow", 0.7)],
    "core":          [("workflow", 0.4), ("debug", 0.3)],
    "comunicacion":  [("communication", 0.7)],
    "datos":         [("database", 0.6)],
    "avanzado":      [],
}


# ── ToolActivation: resultado de activar una herramienta ──────────────────────

class ToolActivation(NamedTuple):
    cmd:         str
    score:       float
    description: str
    layer:       str
    scope:       str
    reasons:     list[str]   # qué dominios lo activaron


# ── Funciones puras ───────────────────────────────────────────────────────────

def _encode_context(text: str) -> dict[str, float]:
    """Codifica el texto del contexto → señal de dominio.

    Función pura: no modifica estado, no hace I/O. Solo mapea texto a señales.
    """
    text_lower = text.lower()
    signal: dict[str, float] = {}
    for keyword, domain_weights in _CONTEXT_SIGNALS.items():
        if keyword in text_lower:
            for domain, weight in domain_weights:
                signal[domain] = max(signal.get(domain, 0.0), weight)
    return signal


def _derive_profile(cmd: str, description: str, layer: str, scope: str) -> dict[str, float]:
    """Deriva el perfil de capacidades de una herramienta desde sus metadatos del registry.

    Función pura: no modifica estado. Genera perfil desde descripción + layer.
    No duplica el registry — genera automáticamente desde la fuente de verdad.
    """
    profile: dict[str, float] = {}
    desc_lower = description.lower()

    # Señales de la descripción (misma lógica que _encode_context)
    for keyword, domain_weights in _CONTEXT_SIGNALS.items():
        if keyword in desc_lower:
            for domain, weight in domain_weights:
                # Herramientas: peso ligeramente reducido vs señal de usuario
                profile[domain] = max(profile.get(domain, 0.0), weight * 0.9)

    # Señales del layer (metadato del registry)
    for layer_key, layer_signal in _LAYER_DOMAINS.items():
        if layer_key in (layer or "").lower():
            for domain, weight in layer_signal:
                profile[domain] = max(profile.get(domain, 0.0), weight)

    # Si no hay señales, fallback genérico
    if not profile:
        profile["debug"] = 0.2  # herramienta de propósito general

    return profile


def _score_tool(signal: dict[str, float], profile: dict[str, float]) -> float:
    """Calcula la afinidad entre un contexto y el perfil de una herramienta.

    Función pura: similitud coseno aproximada. Retorna [0.0, 1.0].
    Normaliza por max(|signal|, |profile|) para penalizar herramientas con
    muy pocos dominios frente a señales ricas en dimensiones.
    """
    if not signal or not profile:
        return 0.0
    dot = sum(signal.get(d, 0.0) * w for d, w in profile.items())
    # Normalización: penaliza coverage parcial — herramientas con pocos dominios
    # no puntúan igual que las que cubren todo el espacio de señal
    signal_mag = sum(signal.values()) or 1.0
    profile_mag = sum(profile.values()) or 1.0
    return min(dot / max(signal_mag, profile_mag), 1.0)


def _activation_reasons(signal: dict[str, float], profile: dict[str, float]) -> list[str]:
    """Explica qué dominios contribuyeron a la activación de esta herramienta.

    Función pura: retorna lista de strings descriptivos.
    """
    reasons = []
    for domain, p_weight in sorted(profile.items(), key=lambda x: -x[1]):
        s_weight = signal.get(domain, 0.0)
        if s_weight > 0:
            reasons.append(f"{domain}({s_weight:.1f}×{p_weight:.1f}={s_weight*p_weight:.2f})")
    return reasons


# ── Persistencia de pesos aprendidos ─────────────────────────────────────────

def _load_weights() -> dict[str, dict[str, float]]:
    """Carga los pesos aprendidos desde disco. Retorna dict vacío si falla."""
    try:
        if WEIGHTS_FILE.exists():
            data = json.loads(WEIGHTS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _save_weights(weights: dict[str, dict[str, float]]) -> None:
    """Guarda los pesos aprendidos con escritura atómica (temp + rename)."""
    import tempfile, os
    WEIGHTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = WEIGHTS_FILE.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(weights, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(str(tmp), str(WEIGHTS_FILE))
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


def _apply_feedback(weights: dict, cmd: str, found_issues: bool,
                    signal: dict[str, float]) -> dict:
    """Actualiza los pesos de una herramienta basándose en su resultado.

    Función pura respecto al perfil derivado — solo modifica el dict `weights`.
    - found_issues=True → boost +0.1 (la herramienta fue útil en este contexto)
    - found_issues=False → penalización -0.05 (quizás fue innecesaria)
    Pesos acotados: [0.05, 1.5] para evitar colapso o explosión.
    """
    if not signal:
        return weights
    delta = 0.1 if found_issues else -0.05
    tool_w = weights.setdefault(cmd, {})
    for domain, s_weight in signal.items():
        if s_weight > 0.3:  # solo ajusta dominios relevantes en este contexto
            current = tool_w.get(domain, 1.0)
            tool_w[domain] = max(0.05, min(1.5, current + delta * s_weight))
    return weights


# ── NeuralToolbox ─────────────────────────────────────────────────────────────

class NeuralToolbox:
    """Motor de activación dinámica de herramientas BAGO.

    Transforma un texto de contexto en un conjunto de herramientas activadas,
    aplica filtros de scope/risk/deprecated, y aprende de los resultados.
    """

    def __init__(self) -> None:
        self._weights = _load_weights()
        self._last_signal: dict[str, float] = {}

    def _load_registry(self) -> dict:
        """Carga el registry de herramientas. Falla silenciosamente."""
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "_tool_registry", str(TOOLS_DIR / "tool_registry.py")
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod.REGISTRY
        except Exception:
            return {}

    def activate(
        self,
        context_text: str,
        scope_filter: str = "both",
        threshold: float = 0.25,
        top_n: int = 6,
        include_deprecated: bool = False,
    ) -> list[ToolActivation]:
        """Activa las herramientas más relevantes para el contexto dado.

        Pasos (cada uno es una función pura):
          1. _encode_context(context_text) → señal de dominio
          2. Para cada herramienta en registry:
             a. Filtrar scope, risk, deprecated
             b. _derive_profile() desde metadatos
             c. Aplicar pesos aprendidos
             d. _score_tool(señal, perfil) → puntuación
          3. Filtrar por threshold y ordenar por score desc
          4. Retornar top_n activaciones
        """
        signal = _encode_context(context_text)
        self._last_signal = signal

        if not signal:
            return []

        registry = self._load_registry()
        activations: list[ToolActivation] = []

        for cmd, entry in registry.items():
            # ── Filtros de scope ───────────────────────────────────────────
            entry_scope = getattr(entry, "scope", "both") or "both"
            if scope_filter == "framework" and entry_scope == "project":
                continue
            if scope_filter == "project" and entry_scope == "framework":
                continue

            # ── Filtros de riesgo y deprecated ────────────────────────────
            if getattr(entry, "risk", "safe") == "mutating":
                continue
            if not include_deprecated and getattr(entry, "deprecated", False):
                continue

            # ── Derivar perfil desde metadatos ────────────────────────────
            profile = _derive_profile(
                cmd=cmd,
                description=getattr(entry, "description", ""),
                layer=getattr(entry, "layer", ""),
                scope=entry_scope,
            )

            # ── Aplicar pesos aprendidos ───────────────────────────────────
            learned = self._weights.get(cmd, {})
            if learned:
                adjusted = {d: w * learned.get(d, 1.0) for d, w in profile.items()}
            else:
                adjusted = profile

            # ── Calcular activación ────────────────────────────────────────
            score = _score_tool(signal, adjusted)
            if score >= threshold:
                reasons = _activation_reasons(signal, adjusted)
                activations.append(ToolActivation(
                    cmd=cmd,
                    score=round(score, 4),
                    description=getattr(entry, "description", ""),
                    layer=getattr(entry, "layer", ""),
                    scope=entry_scope,
                    reasons=reasons,
                ))

        activations.sort(key=lambda a: a.score, reverse=True)
        return activations[:top_n]

    def feedback(self, tool_cmd: str, found_issues: bool) -> None:
        """Ajusta los pesos aprendidos de una herramienta según su resultado.

        Solo modifica los dominios relevantes en el último contexto procesado.
        Persiste los cambios de forma atómica.
        """
        self._weights = _apply_feedback(
            self._weights, tool_cmd, found_issues, self._last_signal
        )
        _save_weights(self._weights)

    def explain(self, context_text: str, top_n: int = 8) -> str:
        """Retorna una explicación legible de la activación para un contexto."""
        signal = _encode_context(context_text)
        if not signal:
            return "  [NTB-W001] Contexto sin señales reconocidas — usa palabras como: security, lint, test, workflow..."

        activations = self.activate(context_text, top_n=top_n)
        lines = [
            f"\n  🧠 Neural Toolbox — Activación para: '{context_text[:60]}'",
            f"  Señal detectada: {dict(sorted(signal.items(), key=lambda x: -x[1]))}",
            "",
        ]
        if not activations:
            lines.append("  [NTB-W001] Sin herramientas activadas (threshold demasiado alto?)")
        else:
            lines.append(f"  {'SCORE':>6}  {'CMD':<22}  {'RAZONES'}")
            lines.append(f"  {'─'*6}  {'─'*22}  {'─'*40}")
            for a in activations:
                reasons_str = ", ".join(a.reasons[:3]) or "—"
                lines.append(f"  {a.score:>6.3f}  {a.cmd:<22}  {reasons_str}")
        return "\n".join(lines)


# ── run_dynamic_workflow: orquestación completa ────────────────────────────────

def run_dynamic_workflow(
    context_text: str,
    scope_filter: str = "both",
    threshold: float = 0.25,
    top_n: int = 5,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict:
    """Orquesta un workflow dinámico: activar herramientas, ejecutar y aplicar feedback.

    Flujo:
      1. NeuralToolbox.activate() → herramientas candidatas (función pura)
      2. Para cada herramienta: subprocess bago <cmd> (efecto secundario aquí)
      3. NeuralToolbox.feedback() → actualizar pesos según resultado

    Retorna el mismo schema que orchestrator.run_workflow():
      {"workflow", "passed", "failed", "critical_failed", "steps"}
    """
    toolbox = NeuralToolbox()
    activations = toolbox.activate(context_text, scope_filter, threshold, top_n)

    _ts = lambda msg: print(f"  {time.strftime('%H:%M:%S')}  {msg}")

    print(f"\n  {'━'*56}")
    print(f"  🧠 BAGO Neural Workflow — Dinámica")
    print(f"  Contexto: '{context_text[:60]}'")
    print(f"  {'━'*56}")

    if not activations:
        print("  [NTB-W001] Sin herramientas activadas para este contexto.")
        return {"workflow": "dynamic", "passed": 0, "failed": 0,
                "critical_failed": False, "steps": []}

    print(f"  Activadas: {len(activations)} herramientas\n")
    for a in activations:
        _ts(f"  ⚡ {a.cmd:<22} score={a.score:.3f}  {a.description[:40]}")

    print()
    step_results = []

    for a in activations:
        print(f"\n  ▶ bago {a.cmd}   (score={a.score:.3f})")
        if dry_run:
            result = {"cmd": a.cmd, "rc": 0, "output": f"[dry-run] bago {a.cmd}",
                      "elapsed": 0.0, "ok": True}
        else:
            start = time.time()
            try:
                r = subprocess.run(
                    [str(BAGO_SCRIPT), a.cmd],
                    capture_output=True, text=True,
                    cwd=str(PROJECT_ROOT), timeout=90,
                    encoding="utf-8", errors="replace",
                )
                elapsed = time.time() - start
                result = {
                    "cmd": a.cmd, "rc": r.returncode,
                    "output": (r.stdout + r.stderr).strip()[:2000],
                    "elapsed": round(elapsed, 2),
                    "ok": r.returncode == 0,
                }
            except subprocess.TimeoutExpired:
                result = {"cmd": a.cmd, "rc": 1, "output": "TIMEOUT (90s)",
                          "elapsed": 90.0, "ok": False}
            except Exception as e:
                result = {"cmd": a.cmd, "rc": 1, "output": str(e),
                          "elapsed": 0.0, "ok": False}

        icon = "✅" if result["ok"] else "⚠️ "
        print(f"  {icon} {a.cmd:<22} ({result['elapsed']}s)")
        if verbose and result["output"]:
            for line in result["output"].splitlines()[-3:]:
                print(f"     {line}")

        # Feedback: la herramienta fue útil si encontró issues (rc != 0) o si pasó OK
        # "útil" = herramienta relevante = encontró algo O fue la primera verificación sin issues
        found_issues = result["rc"] != 0
        if not dry_run:
            toolbox.feedback(a.cmd, found_issues)

        step_results.append({**a._asdict(), **result, "critical": False})

    # Resumen
    passed = sum(1 for r in step_results if r.get("ok"))
    failed = len(step_results) - passed
    total_time = sum(r.get("elapsed", 0.0) for r in step_results)

    print(f"\n  {'━'*56}")
    print(f"  Neural Workflow — {passed}/{len(step_results)} herramientas OK  |  {total_time:.1f}s")
    print(f"  [NTB-I001] Pesos actualizados en {WEIGHTS_FILE.name}")
    print()

    return {
        "workflow": "dynamic",
        "context": context_text,
        "passed": passed,
        "failed": failed,
        "critical_failed": False,
        "steps": step_results,
    }


# ── Self-tests ────────────────────────────────────────────────────────────────

def _run_tests() -> int:
    results: list[tuple[str, bool, str]] = []

    # Test 1: _encode_context — señal de seguridad
    sig = _encode_context("revisar secretos y passwords hardcodeados")
    ok1 = sig.get("security", 0) >= 0.8
    results.append(("encode_context:security", ok1, f"security={sig.get('security', 0):.2f}"))

    # Test 2: _encode_context — señal de calidad
    sig2 = _encode_context("el código tiene problemas de calidad y lint")
    ok2 = sig2.get("quality", 0) >= 0.8
    results.append(("encode_context:quality", ok2, f"quality={sig2.get('quality', 0):.2f}"))

    # Test 3: _encode_context — sin señales
    sig3 = _encode_context("xyz abc 123 nonsense nada")
    ok3 = len(sig3) == 0
    results.append(("encode_context:empty", ok3, f"signals={len(sig3)}"))

    # Test 4: _score_tool — dot product correcto
    signal = {"security": 0.9, "quality": 0.3}
    profile = {"security": 0.8, "quality": 0.6}
    score = _score_tool(signal, profile)
    # Esperado: (0.9*0.8 + 0.3*0.6) / (0.8+0.6) = (0.72+0.18)/1.4 = 0.643
    ok4 = 0.6 < score < 0.7
    results.append(("score_tool:dot_product", ok4, f"score={score:.4f}"))

    # Test 5: _score_tool — vacíos
    ok5 = _score_tool({}, {"security": 0.9}) == 0.0
    results.append(("score_tool:empty_signal", ok5, ""))

    # Test 6: _derive_profile — genera señales desde descripción
    profile2 = _derive_profile("secret-scan", "Escanea secretos hardcodeados", "seguridad", "framework")
    ok6 = profile2.get("security", 0) > 0
    results.append(("derive_profile:security_tool", ok6, f"security={profile2.get('security', 0):.2f}"))

    # Test 7: _apply_feedback — boost aumenta peso
    weights: dict = {}
    signal7 = {"security": 0.9}
    weights = _apply_feedback(weights, "secret-scan", True, signal7)
    ok7 = weights.get("secret-scan", {}).get("security", 1.0) > 1.0
    results.append(("apply_feedback:boost", ok7, f"w={weights.get('secret-scan',{}).get('security',1.0):.3f}"))

    # Test 8: _apply_feedback — penalización reduce peso
    weights2: dict = {}
    weights2 = _apply_feedback(weights2, "lint", False, {"quality": 0.8})
    ok8 = weights2.get("lint", {}).get("quality", 1.0) < 1.0
    results.append(("apply_feedback:penalty", ok8, f"w={weights2.get('lint',{}).get('quality',1.0):.3f}"))

    # Test 9: NeuralToolbox.activate — retorna lista con threshold alto → vacía
    tb = NeuralToolbox()
    acts = tb.activate("xyz abc nonsense 123", threshold=0.9)
    ok9 = acts == []
    results.append(("toolbox:activate_no_signal", ok9, f"count={len(acts)}"))

    # Test 10: NeuralToolbox.explain — no crashea, retorna string
    explanation = tb.explain("revisar secretos y seguridad")
    ok10 = isinstance(explanation, str) and "Neural Toolbox" in explanation
    results.append(("toolbox:explain", ok10, f"len={len(explanation)}"))

    # Test 11: run_dynamic_workflow dry-run — retorna schema correcto
    result = run_dynamic_workflow("revisar seguridad", dry_run=True, top_n=2)
    ok11 = isinstance(result, dict) and "passed" in result and "steps" in result
    results.append(("run_dynamic_workflow:schema", ok11, f"passed={result.get('passed')} steps={len(result.get('steps',[]))}"))

    # Test 12: _activation_reasons — no crashea con entradas vacías
    reasons = _activation_reasons({}, {"security": 0.9})
    ok12 = reasons == []
    results.append(("activation_reasons:empty_signal", ok12, ""))

    passed_count = sum(1 for _, ok, _ in results if ok)
    failed_count = sum(1 for _, ok, _ in results if not ok)
    print(f"\n  neural_toolbox.py — Self-tests ({passed_count}/{len(results)} pasaron)\n")
    for name, ok, detail in results:
        icon = "✅" if ok else "❌"
        print(f"  {icon}  {name}  {detail}")
    return 0 if failed_count == 0 else 1


# ── CLI ───────────────────────────────────────────────────────────────────────

def main(argv=None):
    import argparse
    if argv is None:
        argv = sys.argv[1:]

    ap = argparse.ArgumentParser(
        description="BAGO Neural Toolbox — activación dinámica de herramientas"
    )
    ap.add_argument("--context",  "-c", help="Texto de contexto para activar herramientas")
    ap.add_argument("--run",      "-r", help="Activa y ejecuta herramientas para el contexto dado")
    ap.add_argument("--scope",    default="both", choices=["both", "framework", "project"])
    ap.add_argument("--threshold", type=float, default=0.25, help="Umbral de activación (0.0-1.0)")
    ap.add_argument("--top",      type=int, default=6, help="Máximo de herramientas a activar")
    ap.add_argument("--explain",  action="store_true", help="Explica las activaciones")
    ap.add_argument("--json",     action="store_true", help="Output JSON")
    ap.add_argument("--dry-run",  action="store_true", help="Muestra sin ejecutar")
    ap.add_argument("--verbose",  "-v", action="store_true")
    ap.add_argument("--test",     action="store_true", help="Ejecuta self-tests")
    args = ap.parse_args(argv)

    if args.test:
        return _run_tests()

    context = args.context or args.run
    if not context:
        ap.print_help()
        return 0

    toolbox = NeuralToolbox()

    if args.explain:
        print(toolbox.explain(context, top_n=args.top))
        return 0

    if args.run and not args.dry_run:
        result = run_dynamic_workflow(
            context, scope_filter=args.scope,
            threshold=args.threshold, top_n=args.top,
            dry_run=False, verbose=args.verbose,
        )
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        return 1 if result["failed"] > result["passed"] else 0

    # Solo mostrar activaciones
    activations = toolbox.activate(context, scope_filter=args.scope,
                                   threshold=args.threshold, top_n=args.top)

    if args.json:
        print(json.dumps([a._asdict() for a in activations], indent=2, ensure_ascii=False))
        return 0

    if not activations:
        print("  [NTB-W001] Sin herramientas activadas. Prueba con un umbral más bajo: --threshold 0.1")
        return 0

    print(f"\n  🧠 Neural Toolbox — '{context[:60]}'")
    print(f"  {'─'*60}")
    print(f"  {'SCORE':>6}  {'CMD':<22}  {'DESCRIPCIÓN'}")
    print(f"  {'─'*6}  {'─'*22}  {'─'*35}")
    for a in activations:
        print(f"  {a.score:>6.3f}  {a.cmd:<22}  {a.description[:40]}")
        if args.verbose:
            print(f"         layer={a.layer} scope={a.scope}")
            if a.reasons:
                print(f"         → {', '.join(a.reasons[:3])}")
    print()

    if args.dry_run:
        result = run_dynamic_workflow(context, scope_filter=args.scope,
                                      threshold=args.threshold, top_n=args.top, dry_run=True)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

    return 0


if __name__ == "__main__":
    sys.exit(main())
