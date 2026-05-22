#!/usr/bin/env python3
"""prompt_adapter.py — Adaptador de prompts por familia de modelo.

Transforma prompts genéricos (rol + tarea + contexto) al formato óptimo
de cada familia: OpenAI, Anthropic, Google, Meta/Open Source.

Uso:
    from prompt_adapter import PromptAdapter
    pa = PromptAdapter()
    adapted = pa.adapt_prompt("claude-3-5-sonnet", system="Eres un legal", user="Resume el contrato...")
    # adapted = {"system": ..., "user": ..., "assistant_prefix": "<answer>", "json_mode_hint": ...}
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


class PromptAdapter:
    """Adapta prompts genéricos al dialecto de prompting de cada modelo."""

    _CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "prompt_templates.json"

    def __init__(self, config_path: Path | None = None):
        self._cfg_path = config_path or self._CONFIG_PATH
        self._templates: dict = {}
        self._family_map: dict = {}
        self._load()

    def _load(self) -> None:
        try:
            if self._cfg_path.exists():
                data = json.loads(self._cfg_path.read_text(encoding="utf-8"))
                self._templates = data.get("families", {})
                self._family_map = data.get("model_to_family", {})
        except Exception as exc:
            self._templates = {}
            self._family_map = {}
            print(f"[prompt_adapter] WARN: {exc}")

    # ── Resolución de familia ────────────────────────────────────────────────

    def family(self, model: str) -> str:
        """Devuelve la familia ('openai', 'anthropic', 'google', 'meta') de un modelo."""
        # Exact match
        if model in self._family_map:
            return self._family_map[model]
        # Prefix match (e.g., 'gpt-4o' matches 'gpt-4o-mini')
        for key, fam in sorted(self._family_map.items(), key=lambda x: -len(x[0])):
            if model.lower().startswith(key.lower()):
                return fam
        # Heurísticas por palabra clave
        low = model.lower()
        if "gpt" in low or "o1" in low or "o3" in low:
            return "openai"
        if "claude" in low:
            return "anthropic"
        if "gemini" in low:
            return "google"
        if any(x in low for x in ("llama", "mistral", "qwen", "deepseek", "mixtral")):
            return "meta"
        return "openai"  # default seguro

    def family_config(self, model: str) -> dict:
        """Devuelve el dict de configuración de la familia del modelo."""
        fam = self.family(model)
        return self._templates.get(fam, {})

    # ── Transformaciones ────────────────────────────────────────────────────

    def adapt_prompt(self, model: str, system: str = "", user: str = "",
                     context: str = "", task: str = "") -> dict[str, Any]:
        """Adapta un prompt genérico al formato óptimo del modelo.

        Retorna dict con:
            system: str | None
            user: str
            assistant_prefix: str | None
            json_mode_hint: str
            delimiter_style: str
        """
        cfg = self.family_config(model)
        fam = self.family(model)

        # Derivar tarea y contexto si no se pasan explícitamente
        task = task or user
        ctx = context or ""

        # System prompt handling
        system_out = None
        if cfg.get("system_prompt_enabled") and cfg.get("system_prompt_powerful"):
            system_out = system
        elif cfg.get("system_prompt_enabled") and not cfg.get("system_prompt_powerful"):
            # Para familias donde system es débil, lo inyectamos en user
            if system:
                ctx = f"{system}\n\n{ctx}".strip()
            system_out = None
        else:
            system_out = None
            if system:
                ctx = f"{system}\n\n{ctx}".strip()

        # Construir user según familia
        delimiters = cfg.get("preferred_delimiters", {})
        wrapper = cfg.get("role_wrapper", "{rol}. {reglas}\n{tarea}\n{contexto}")

        if fam == "anthropic":
            user_out = self._build_anthropic(system, task, ctx, delimiters)
        elif fam == "google":
            user_out = self._build_google(system, task, ctx, delimiters)
        elif fam == "meta":
            user_out = self._build_meta(system, task, ctx, delimiters, wrapper)
        else:  # openai default
            user_out = self._build_openai(system, task, ctx, delimiters)

        return {
            "system": system_out,
            "user": user_out,
            "assistant_prefix": cfg.get("assistant_prefix"),
            "json_mode_hint": cfg.get("json_mode", ""),
            "delimiter_style": fam,
            "family": fam,
        }

    def _build_openai(self, system: str, task: str, context: str, delimiters: dict) -> str:
        parts = []
        if context:
            delim = delimiters.get("context", "### Contexto\n{context}")
            parts.append(delim.format(context=context))
        if task:
            parts.append(task)
        return "\n\n".join(parts)

    def _build_anthropic(self, system: str, task: str, context: str, delimiters: dict) -> str:
        parts = []
        # Instrucciones encapsuladas (system ya se inyectó en ctx en adapt_prompt)
        instructions = task
        inst_delim = delimiters.get("instructions", "<instructions>{instructions}</instructions>")
        parts.append(inst_delim.format(instructions=instructions))
        # Documento/contexto
        if context:
            doc_delim = delimiters.get("document", "<document>{document}</document>")
            parts.append(doc_delim.format(document=context))
        return "\n\n".join(parts)

    def _build_google(self, system: str, task: str, context: str, delimiters: dict) -> str:
        parts = []
        if system:
            parts.append(f"Rol: {system}")
        if context:
            ctx_delim = delimiters.get("context", "**Contexto**\n{context}")
            parts.append(ctx_delim.format(context=context))
        if task:
            task_delim = delimiters.get("task", "**Tarea**\n{task}")
            parts.append(task_delim.format(task=task))
        return "\n\n".join(parts)

    def _build_meta(self, system: str, task: str, context: str, delimiters: dict, wrapper: str) -> str:
        # Meta/Llama: repetir tarea al final, instrucción al principio
        parts = []
        if context:
            ctx_delim = delimiters.get("context", "### Contexto\n{context}")
            parts.append(ctx_delim.format(context=context))
        if task:
            parts.append(task)
        # Repetición de tarea al final (clave para modelos open source)
        if task:
            parts.append(f"Recuerda la tarea: {task}")
        return "\n\n".join(parts)

    # ── Few-shot ─────────────────────────────────────────────────────────────

    def adapt_few_shot(self, model: str, examples: list[dict]) -> str:
        """Formatea ejemplos few-shot según la familia del modelo.

        examples: [{"input": ..., "output": ...}, ...]
        """
        cfg = self.family_config(model)
        fam = self.family(model)
        fmt = cfg.get("few_shot_format", "bloques de texto plano")

        if fam == "anthropic" or "XML" in fmt:
            out = []
            for ex in examples:
                out.append(f"<example>")
                out.append(f"  <input>{ex.get('input', '')}</input>")
                out.append(f"  <output>{ex.get('output', '')}</output>")
                out.append(f"</example>")
            return "\n".join(out)
        elif fam == "meta" or "estricto" in fmt:
            out = []
            for i, ex in enumerate(examples, 1):
                out.append(f"### Ejemplo {i}")
                out.append(f"Entrada: {ex.get('input', '')}")
                out.append(f"Salida: {ex.get('output', '')}")
                out.append("---")
            return "\n".join(out)
        else:  # openai / google
            out = []
            for i, ex in enumerate(examples, 1):
                out.append(f"**Ejemplo {i}**")
                out.append(f"Input: {ex.get('input', '')}")
                out.append(f"Output: {ex.get('output', '')}")
                out.append("")
            return "\n".join(out)

    # ── JSON mode ────────────────────────────────────────────────────────────

    def json_instruction(self, model: str) -> str:
        """Devuelve la instrucción de JSON mode óptima para la familia."""
        cfg = self.family_config(model)
        return cfg.get("json_mode", "Responde en JSON válido.")

    def chain_of_thought_instruction(self, model: str) -> str:
        """Devuelve la instrucción de CoT óptima para la familia."""
        cfg = self.family_config(model)
        return cfg.get("chain_of_thought", "Razona paso a paso.")

    # ── Delimitadores utilitarios ────────────────────────────────────────────

    def wrap_context(self, model: str, text: str, ctype: str = "context") -> str:
        """Envuelve texto con delimitadores apropiados para la familia."""
        cfg = self.family_config(model)
        dels = cfg.get("preferred_delimiters", {})
        pattern = dels.get(ctype, "{text}")
        return pattern.format(text=text)

    # ── Info ─────────────────────────────────────────────────────────────────

    def list_families(self) -> list[str]:
        return list(self._templates.keys())

    def list_models(self) -> list[str]:
        return list(self._family_map.keys())

    def info(self, model: str) -> dict:
        """Devuelve toda la info de cómo tratar un modelo específico."""
        fam = self.family(model)
        cfg = self.family_config(model)
        return {
            "model": model,
            "family": fam,
            "family_name": cfg.get("name", fam),
            "system_prompt_recommended": cfg.get("system_prompt_powerful", False),
            "markdown_preferred": cfg.get("markdown_lover", False),
            "json_instruction": self.json_instruction(model),
            "cot_instruction": self.chain_of_thought_instruction(model),
            "assistant_prefix": cfg.get("assistant_prefix"),
            "notes": cfg.get("notes", ""),
        }


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Prompt Adapter CLI")
    parser.add_argument("model", help="Nombre del modelo (ej: claude-3-5-sonnet)")
    parser.add_argument("--system", default="", help="System prompt / rol")
    parser.add_argument("--user", default="", help="User prompt / tarea")
    parser.add_argument("--context", default="", help="Contexto adicional")
    parser.add_argument("--json", action="store_true", help="Añadir instrucción JSON")
    parser.add_argument("--cot", action="store_true", help="Añadir instrucción CoT")
    parser.add_argument("--info", action="store_true", help="Mostrar info del modelo")
    parser.add_argument("--family", action="store_true", help="Mostrar solo la familia")
    args = parser.parse_args()

    pa = PromptAdapter()

    if args.family:
        print(pa.family(args.model))
        raise SystemExit(0)

    if args.info:
        import json as _json
        print(_json.dumps(pa.info(args.model), indent=2, ensure_ascii=False))
        raise SystemExit(0)

    adapted = pa.adapt_prompt(args.model, system=args.system, user=args.user, context=args.context)
    out = [f"### {k}\n{v}" for k, v in adapted.items() if v is not None and v != ""]
    if args.json:
        out.append(f"### json_mode_hint\n{pa.json_instruction(args.model)}")
    if args.cot:
        out.append(f"### chain_of_thought\n{pa.chain_of_thought_instruction(args.model)}")
    print("\n\n".join(out))
