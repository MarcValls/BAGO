
import datetime
import importlib.util
import json
from pathlib import Path

from .constants import BAGO_SYSTEM, SESSIONS_DIR
from .providers import (
    best_model_for_provider,
    load_providers,
    load_routing,
    resolve_litellm,
    route_by_task,
)

class BagoSession:
    def __init__(self, provider, model_name, wire_name, creds):
        self.provider   = provider
        self.model_name = model_name
        self.wire_name  = wire_name
        self.history    = [{"role": "system", "content": BAGO_SYSTEM}]
        self.switches   = 0
        self.started_at = datetime.datetime.now()
        self.providers  = load_providers()
        self.routing    = load_routing()
        self.creds      = creds
        self.autoroute  = True   # routing + estrategia automaticos por defecto
        self.autonomous = False  # modo autonomo (sin confirmaciones)
        self.auto_confirm = "smart"  # always | smart | never
        self.auto_max_iter = 10
        self.temp_mode  = False  # sesion temporal (no escribe en disco automaticamente)
        self.orch_mode  = "standard"  # offline|eco|standard|full|auto
        self.plan_mode  = False  # modo plan: razona y propone antes de actuar
        self.brainstorm = False  # modo brainstorm: expande ideas sin restricciones
        self.sync_after = "continuar"  # continuar|repliegue|letargo
        self.last_route = {
            "mode": "auto",
            "provider": provider,
            "model": model_name,
            "reason": "inicio de sesión",
        }
        # Providers temporalmente excluidos del autoroute (e.g. Ollama caído)
        self.skip_providers: set = set()
        # Token counter: {provider: {model: {"in": int, "out": int, "calls": int}}}
        self.token_log: dict = {}

    # ── Token tracking ────────────────────────────────────────────────────────
    def record_tokens(self, provider: str, model: str, tokens_in: int, tokens_out: int):
        """Registra tokens de entrada/salida para proveedor y modelo."""
        p = self.token_log.setdefault(provider, {})
        m = p.setdefault(model, {"in": 0, "out": 0, "calls": 0})
        m["in"]    += max(0, tokens_in or 0)
        m["out"]   += max(0, tokens_out or 0)
        m["calls"] += 1

    def tokens_summary(self) -> str:
        """Resumen formateado de tokens usados en la sesión."""
        if not self.token_log:
            return "  (sin llamadas registradas aún)"
        lines = []
        total_in = total_out = total_calls = 0
        for prov, models in self.token_log.items():
            for mdl, t in models.items():
                ti, to, tc = t["in"], t["out"], t["calls"]
                lines.append(
                    f"  {prov}/{mdl:<28}  "
                    f"↑{ti:>7,} in   ↓{to:>7,} out   ×{tc} llamadas"
                )
                total_in    += ti
                total_out   += to
                total_calls += tc
        lines.append(
            f"  {'TOTAL':<34}  "
            f"↑{total_in:>7,} in   ↓{total_out:>7,} out   ×{total_calls} llamadas"
        )
        return "\n".join(lines)

    def _load_orchestrator(self):
        path = Path(__file__).resolve().parents[1] / "orchestrator.py"
        if not path.exists():
            return None
        spec = importlib.util.spec_from_file_location("bago_orchestrator_runtime", path)
        if not spec or not spec.loader:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    @property
    def litellm_info(self): return resolve_litellm(self.provider, self.wire_name)

    def _find_model(self, name):
        from .providers import _CODEX_MODEL_MAP, _COPILOT_MODEL_MAP
        shortcuts = {"copilot":"copilot","codex":"codex","ollama":"ollama-local",
                     "ollama-local":"ollama-local","ollama-cloud":"ollama-cloud","anthropic":"anthropic"}
        if name in shortcuts:
            r = best_model_for_provider(shortcuts[name], self.providers)
            if r: return r
        # Handle "provider/model" format (e.g. "copilot/gpt-4o")
        if "/" in name:
            pref, mname = name.split("/", 1)
            for pn, pd in self.providers.items():
                if pn == pref and mname in pd.get("models", {}):
                    return mname, pd["models"][mname].get("wire_name", mname), pn
            # Provider matched but model not in registry — try as-is
            for pn, pd in self.providers.items():
                if pn == pref:
                    return mname, mname, pn
        for pn, pd in self.providers.items():
            if name in pd.get("models", {}):
                return name, pd["models"][name].get("wire_name", name), pn
        # Nombres ficticios gpt-5.x / claude-* → buscar en provider disponible
        if name in _CODEX_MODEL_MAP:
            for pref in ("codex", "openai", "copilot"):
                if pref in self.providers:
                    return name, _CODEX_MODEL_MAP[name], pref
        if name in _COPILOT_MODEL_MAP:
            for pref in ("copilot",):
                if pref in self.providers:
                    return name, _COPILOT_MODEL_MAP[name], pref
        return None, None, None

    def switch_model(self, target, silent=False):
        name, wire, prov = self._find_model(target)
        if not name: return f"'{target}' no encontrado. Usa /models."
        old = self.model_name
        self.provider, self.model_name, self.wire_name = prov, name, wire
        self.switches += 1
        self.last_route = {"mode": "manual", "provider": prov, "model": name, "reason": f"switch manual desde {old}"}
        if silent: return None
        return f"Cambiado: {old} -> {name} ({prov}) | {len(self.history)-1} msgs mantenidos"

    def _resolve_generative_mode(self, user_input: str) -> str:
        """
        Cuando orch_mode == 'auto', elige dinamicamente el nivel generativo
        adecuado para este turno de la espiral segun complejidad del input
        y providers disponibles.

        Escala: offline < eco < standard < full
        """
        if self.orch_mode != "auto":
            return self.orch_mode

        active = self.creds.active_bago_providers()
        words  = len(user_input.split())

        # Indicadores de tarea compleja: codigo, archivos, analisis
        complex_kw = ("refactor", "implementa", "analiza", "debug", "explica",
                      "migra", "crea", "genera", "test", "arquitectura",
                      "implement", "analyze", "create", "generate", "refactor")
        is_complex = words > 60 or any(k in user_input.lower() for k in complex_kw)

        # Sin providers cloud disponibles → no puede usar full
        cloud_ok = any(p in active for p in ("copilot", "codex", "anthropic", "gemini", "openrouter"))

        if is_complex and cloud_ok:
            return "full"
        if is_complex:
            return "standard"
        if words < 10 and not is_complex:
            return "eco"
        return "standard"

    def auto_route(self, user_input):
        """Routing automatico via orquestador; fallback por keyword si falla."""
        effective_mode = self._resolve_generative_mode(user_input)
        orch = self._load_orchestrator()
        if orch:
            try:
                result = orch.orchestrate(user_input, effective_mode)
                model = result.get("model")
                provider = result.get("provider")
                reason = result.get("reason", "orquestador")
                if model and provider and model != self.model_name:
                    # No cambiar a un provider excluido temporalmente
                    if provider not in self.skip_providers:
                        wire = result.get("wire_name", model)
                        old = self.model_name
                        self.provider, self.model_name, self.wire_name = provider, model, wire
                        self.switches += 1
                        mode_tag = f"{self.orch_mode}→{effective_mode}" if self.orch_mode == "auto" else self.orch_mode
                        self.last_route = {"mode": "auto", "provider": provider, "model": model, "reason": reason}
                        return True, f"auto-orchestrator [{mode_tag}]: {old} -> {model} ({provider})"
                if model and provider and provider not in self.skip_providers:
                    self.last_route = {"mode": "auto", "provider": provider, "model": model, "reason": reason}
                    return False, f"auto-orchestrator mantiene {model} ({provider})"
            except Exception:
                pass

        """Routing por keyword: cambia al modelo mas adecuado para esta tarea."""
        name, wire, prov, kw = route_by_task(user_input, self.routing, self.providers, self.provider)
        if name and name != self.model_name:
            # Verificar que el provider tiene credenciales y no está excluido
            active = self.creds.active_bago_providers()
            if prov not in self.skip_providers and (prov in active or any(prov in a for a in active)):
                old = self.model_name
                self.provider, self.model_name, self.wire_name = prov, name, wire
                self.switches += 1
                self.last_route = {"mode": "auto", "provider": prov, "model": name, "reason": f"keyword:{kw}"}
                return True, f"auto-route [{kw}]: {old} -> {name}"
        self.last_route = {"mode": "auto", "provider": self.provider, "model": self.model_name, "reason": "sin cambio"}
        return False, None

    def save(self):
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        ts   = self.started_at.strftime("%Y-%m-%d_%H-%M-%S")
        path = SESSIONS_DIR / f"bago_chat_{ts}.json"
        path.write_text(json.dumps({
            "started_at": self.started_at.isoformat(), "provider": self.provider,
            "model": self.model_name, "switches": self.switches,
            "messages": len(self.history)-1, "history": self.history,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)

    def models_table(self):
        active = self.creds.active_bago_providers()
        lines = []
        for pn, pd in self.providers.items():
            avail = "✓" if pn in active else "○"
            lines.append(f"\n[{avail}] [{pn}]")
            for mn, md in pd.get("models", {}).items():
                act = " ← ACTIVO" if mn == self.model_name else ""
                lines.append(f"    {mn:<30} {md.get('best_for',''):<25} {md.get('cost','')}{act}")
        return "\n".join(lines)
