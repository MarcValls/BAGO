#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""prompt_router.py — Router de prompts basado en metricas de senal.

El prompt es un router WiFi. Se adapta segun la calidad de la senal del contexto:
  - Banda: 2.4g (amplio/lento, mucho contexto) vs 5g (estrecho/rapido, enfocado)
  - Canal: identity | context | specialization | routing — que contenido transmite
  - Hz: frecuencia de actualizacion del prompt
  - Interferencia: tokens irrelevantes que distorsionan
  - Desacoplamiento: el prompt ya no se alinea con la tarea real
"""
from __future__ import annotations

import json
import re
from pathlib import Path


class SignalMetrics:
    """Metricas de calidad de senal del contexto."""

    def __init__(
        self,
        context_depth: int,
        token_pressure: float,
        coherence_score: float,
        drift_detected: bool,
        noise_level: float,
        task_urgency: int,
        last_cycle_success: bool,
    ):
        self.context_depth = context_depth
        self.token_pressure = token_pressure
        self.coherence_score = coherence_score
        self.drift_detected = drift_detected
        self.noise_level = noise_level
        self.task_urgency = task_urgency
        self.last_cycle_success = last_cycle_success

    def band(self) -> str:
        if self.drift_detected or self.noise_level > 0.4:
            return "2.4g"
        if self.token_pressure > 0.85:
            return "5g"
        if self.coherence_score > 0.8 and self.task_urgency >= 4:
            return "5g"
        return "2.4g"

    def channel(self) -> str:
        if self.drift_detected:
            return "identity"
        if self.noise_level > 0.3:
            return "routing"
        if self.coherence_score < 0.5:
            return "context"
        if self.task_urgency >= 4:
            return "specialization"
        return "context"

    def hz(self) -> int:
        if self.drift_detected:
            return 1
        if self.coherence_score > 0.9 and self.last_cycle_success:
            return 5
        if self.token_pressure > 0.8:
            return 2
        return 3

    def interference(self) -> float:
        return self.noise_level + max(0, self.token_pressure - 0.7)

    def as_dict(self) -> dict:
        return {
            "band": self.band(),
            "channel": self.channel(),
            "hz": self.hz(),
            "interference": round(self.interference(), 3),
            "context_depth": self.context_depth,
            "token_pressure": round(self.token_pressure, 3),
            "coherence_score": round(self.coherence_score, 3),
            "drift_detected": self.drift_detected,
            "noise_level": round(self.noise_level, 3),
            "task_urgency": self.task_urgency,
            "last_cycle_success": self.last_cycle_success,
        }


class PromptRouter:
    """Adapta el prompt como un router WiFi segun la calidad de senal."""

    def __init__(self, bago_root: str | Path):
        self.root = Path(bago_root).resolve()
        self.artifacts_dir = self.root / ".bago" / "artifacts"
        self.roles_dir = self.root / ".bago" / "roles"
        self.artifact_index = self._load_index()

    def _load_index(self) -> dict:
        p = self.artifacts_dir / "index.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        return {"artifacts": {}}

    def _load_artifact(self, ref: str) -> dict | None:
        meta = self.artifact_index.get("artifacts", {}).get(ref)
        if not meta:
            return None
        src = self.artifacts_dir / meta.get("source", "")
        if not src.exists():
            return None
        return json.loads(src.read_text(encoding="utf-8"))

    def _load_role_embed(self, role_id: str) -> dict | None:
        for p in self.roles_dir.rglob("*.embed.json"):
            data = json.loads(p.read_text(encoding="utf-8"))
            if data.get("role_id") == role_id:
                return data
        return None

    def _eval_conditions(self, artifacts, cycle, radius, task_type):
        allowed = re.compile(r"^[\w\s._\-+<>=!&|('):,\[\]]+$")
        ctx = {"cycle": cycle, "radius": radius, "task_type": task_type}
        selected = []
        for art in artifacts:
            cond = art.get("condition", "")
            if not cond:
                selected.append(art)
                continue
            if not allowed.match(cond):
                continue
            try:
                if eval(cond, {"__builtins__": {}}, ctx):
                    selected.append(art)
            except Exception:
                pass
        return selected

    def scan_signal(self, role_id, cycle, radius, task_type, raw_prompt="", token_budget=4000):
        embed = self._load_role_embed(role_id)
        context_depth = min(cycle, 10)
        used_tokens = len(raw_prompt.split()) if raw_prompt else 200
        token_pressure = used_tokens / max(token_budget, 1)
        coherence_score = 0.7
        if task_type and task_type.lower() in raw_prompt.lower():
            coherence_score = 0.95
        elif not task_type:
            coherence_score = 0.5
        drift_detected = False
        if embed:
            behaviors = embed.get("behaviors", {})
            drift_patterns = behaviors.get("drift_patterns", [])
            for pattern in drift_patterns:
                if pattern.lower() in raw_prompt.lower():
                    drift_detected = True
                    break
        noise_level = 0.2
        if embed:
            refs = [a.get("ref", "") for a in embed.get("artifacts", [])]
            matches = sum(1 for r in refs if r.split(":")[-1] in raw_prompt)
            noise_level = 1.0 - (matches / max(len(refs), 1))
            noise_level = max(0.0, min(1.0, noise_level))
        task_urgency = 2
        if task_type in ("critical", "security", "governance"):
            task_urgency = 5
        elif task_type in ("architecture", "design"):
            task_urgency = 4
        elif task_type in ("validation", "audit"):
            task_urgency = 3
        last_cycle_success = coherence_score > 0.7 and not drift_detected
        return SignalMetrics(
            context_depth=context_depth,
            token_pressure=token_pressure,
            coherence_score=coherence_score,
            drift_detected=drift_detected,
            noise_level=noise_level,
            task_urgency=task_urgency,
            last_cycle_success=last_cycle_success,
        )

    def route(self, role_id, signal, cycle=1, radius=1.0, task_type=""):
        embed = self._load_role_embed(role_id)
        if not embed:
            return {"error": f"Embed no encontrado: {role_id}"}
        pool = self._eval_conditions(embed.get("artifacts", []), cycle, radius, task_type)
        band = signal.band()
        channel = signal.channel()
        hz = signal.hz()
        interference = signal.interference()
        if band == "5g":
            identity = [a for a in pool if a.get("layer") == "identity" and a.get("priority", 99) <= 1]
            specialization = [a for a in pool if a.get("layer") == "specialization"][:1]
            routed = identity + specialization
        else:
            routed = pool
        channel_filter = {
            "identity": lambda a: a.get("layer") in ("identity",) or a.get("inject_at") == "head",
            "context": lambda a: a.get("layer") in ("identity", "context"),
            "specialization": lambda a: a.get("layer") in ("identity", "context", "specialization"),
            "routing": lambda a: True,
        }.get(channel, lambda a: True)
        routed = [a for a in routed if channel_filter(a)]
        if interference > 0.5:
            routed = [a for a in routed if a.get("priority", 99) <= 2]
        if signal.drift_detected:
            routed = [a for a in routed if a.get("inject_at") != "tail"]
        identity_parts = []
        context_parts = []
        spec_parts = []
        commands_parts = []
        for art in routed:
            ref = art.get("ref", "")
            data = self._load_artifact(ref)
            if not data:
                continue
            fmt = art.get("format")
            content = data.get("content", "")
            rendered = self._format_artifact(ref, content, fmt)
            inject = art.get("inject_at", "body")
            if inject == "head":
                identity_parts.append(rendered)
            elif inject == "body":
                layer = art.get("layer", "context")
                if layer == "specialization":
                    spec_parts.append(rendered)
                else:
                    context_parts.append(rendered)
            elif inject == "tail":
                spec_parts.append(rendered)
            elif inject == "commands":
                commands_parts.append(rendered)
        template = embed.get("prompt_template", {})
        bindings = embed.get("dynamic_bindings", {})
        bindings["base_identity"] = "\n".join(identity_parts) if identity_parts else ""
        bindings["context_artifacts"] = "\n".join(context_parts) if context_parts else ""
        bindings["specialized_artifacts"] = "\n".join(spec_parts) if spec_parts else ""
        bindings["commands_block"] = "\n".join(commands_parts) if commands_parts else ""
        bindings["cycle"] = cycle
        bindings["radius"] = radius
        bindings["task_type"] = task_type
        bindings["band"] = band
        bindings["channel"] = channel
        bindings["hz"] = hz
        bindings["interference"] = round(interference, 3)
        prompt = self._render_template(template, bindings)
        if channel == "routing" or interference > 0.3:
            prompt += self._build_routing_layer(signal, routed)
        return {
            "prompt": prompt,
            "signal": signal.as_dict(),
            "routed_artifacts": len(routed),
            "band": band,
            "channel": channel,
            "hz": hz,
        }

    def _format_artifact(self, ref, content, fmt):
        if fmt == "inline_shell":
            return f"```shell\n# {ref}\n{content}\n```"
        if ref.startswith("description:"):
            return f"\n{content}\n"
        if ref.startswith("snippet:"):
            lang = ref.split(":")[1].split("/")[0] if "/" in ref else ""
            return f"```{lang}\n# {ref}\n{content}\n```"
        if ref.startswith("command:"):
            shell = ref.split(":")[1].split("/")[0] if "/" in ref else "bash"
            return f"```{shell}\n# {ref}\n{content}\n```"
        return content

    def _render_template(self, template, bindings):
        head = template.get("head", "")
        body = template.get("body", "")
        tail = template.get("tail", "")
        for key, val in bindings.items():
            head = head.replace("{" + key + "}", str(val))
            body = body.replace("{" + key + "}", str(val))
            tail = tail.replace("{" + key + "}", str(val))
        return f"{head}{body}{tail}".strip()

    def _build_routing_layer(self, signal, routed):
        lines = [
            "",
            "--- CAPA DE ROUTING (adaptacion dinamica) ---",
            f"Banda: {signal.band()} | Canal: {signal.channel()} | Hz: {signal.hz()}",
            f"Interferencia: {round(signal.interference(), 3)} | Coherencia: {signal.coherence_score}",
        ]
        if signal.drift_detected:
            lines.append("⚠️  DESACOPLAMIENTO DETECTADO: reanclando a identidad base.")
        if signal.noise_level > 0.3:
            lines.append("⚠️  RUIDO ELEVADO: filtrando artefactos no esenciales.")
        if signal.token_pressure > 0.8:
            lines.append("⚠️  PRESION DE TOKENS ALTA: modo 5g activado, reduciendo contexto.")
        lines.append("")
        lines.append("Instrucciones de routing:")
        for i, art in enumerate(routed, 1):
            ref = art.get("ref", "")
            layer = art.get("layer", "?")
            lines.append(f"  {i}. [{layer}] {ref}")
        lines.append("")
        lines.append("Reglas adaptativas:")
        lines.append("  - Si la senal cae (coherencia < 0.5), vuelve al canal identity.")
        lines.append("  - Si hay desacoplamiento, ignora tail y prioriza head.")
        lines.append("  - En 5g, responde rapido y enfocado; en 2.4g, construye acumulativamente.")
        lines.append("  - Si la interferencia sube, reduce artefactos de baja prioridad.")
        lines.append("")
        return "\n".join(lines)


def main():
    import sys
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    import argparse
    parser = argparse.ArgumentParser(description="Prompt Router — routing por senal")
    parser.add_argument("--role", required=True)
    parser.add_argument("--cycle", type=int, default=1)
    parser.add_argument("--radius", type=float, default=1.0)
    parser.add_argument("--task-type", default="")
    parser.add_argument("--raw-prompt", default="")
    parser.add_argument("--budget", type=int, default=4000)
    parser.add_argument("--bago-root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    router = PromptRouter(args.bago_root)
    signal = router.scan_signal(args.role, args.cycle, args.radius, args.task_type, args.raw_prompt, args.budget)
    result = router.route(args.role, signal, args.cycle, args.radius, args.task_type)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Banda: {result['band']} | Canal: {result['channel']} | Hz: {result['hz']}")
        print(f"Artefactos ruteados: {result['routed_artifacts']}")
        print("")
        print(result["prompt"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
