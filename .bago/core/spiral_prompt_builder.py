#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""spiral_prompt_builder.py — Constructor de prompts en espiral progresiva.

Cada rol lleva un .embed.json que declara artefactos indexados con condiciones.
El builder evalua el estado de la espiral (cycle, radius, task_type) y monta
el prompt capa por capa, de menos a mas, infinitamente escalable.
"""
from __future__ import annotations

import ast
import json
import re
import textwrap
from pathlib import Path
from typing import Any


class SafeExpr:
    """Evaluador de expresiones condicionales seguras para artefactos.

    Rechaza cualquier construccion que no sea comparacion, operador booleano
    o aritmetica basica sobre variables del contexto.
    """

    @staticmethod
    def eval(condition: str, context: dict) -> bool:
        if not condition:
            return True
        try:
            tree = ast.parse(condition, mode="eval")
        except SyntaxError:
            return False

        allowed_nodes = {
            ast.Expression,
            ast.BinOp, ast.BoolOp, ast.Compare, ast.UnaryOp,
            ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
            ast.And, ast.Or, ast.Not,
            ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
            ast.In, ast.NotIn,
            ast.Name, ast.Constant, ast.Load,
        }
        # Compatibilidad con Python < 3.8
        if hasattr(ast, "Num"):
            allowed_nodes.add(ast.Num)
        if hasattr(ast, "Str"):
            allowed_nodes.add(ast.Str)

        for node in ast.walk(tree):
            if type(node) not in allowed_nodes:
                return False

        compiled = compile(tree, "<condition>", "eval")
        try:
            return bool(eval(compiled, {"__builtins__": {}}, context))
        except Exception:
            return False


class SpiralPromptBuilder:
    """Construye prompts en espiral para roles con codigo embebido indexado."""

    def __init__(self, bago_root: str | Path):
        self.root = Path(bago_root).resolve()
        self.artifacts_dir = self.root / ".bago" / "artifacts"
        self.roles_dir = self.root / ".bago" / "roles"
        self.artifact_index = self._load_artifact_index()

    def _load_artifact_index(self) -> dict:
        index_path = self.artifacts_dir / "index.json"
        if index_path.exists():
            return json.loads(index_path.read_text(encoding="utf-8"))
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
        for embed_path in self.roles_dir.rglob("*.embed.json"):
            data = json.loads(embed_path.read_text(encoding="utf-8"))
            if data.get("role_id") == role_id:
                return data
        return None

    def _eval_artifact_conditions(
        self, artifacts: list[dict], cycle: int, radius: float, task_type: str
    ) -> list[dict]:
        context = {"cycle": cycle, "radius": radius, "task_type": task_type}
        selected = []
        for art in artifacts:
            cond = art.get("condition", "")
            if SafeExpr.eval(cond, context):
                selected.append(art)
        layer_order = {"identity": 0, "context": 1, "specialization": 2}
        selected.sort(key=lambda a: (a.get("priority", 99), layer_order.get(a.get("layer", ""), 99)))
        return selected

    def _render_prompt_template(self, template: dict, bindings: dict) -> str:
        head = template.get("head", "")
        body = template.get("body", "")
        tail = template.get("tail", "")
        for key, val in bindings.items():
            placeholder = "{" + key + "}"
            head = head.replace(placeholder, str(val))
            body = body.replace(placeholder, str(val))
            tail = tail.replace(placeholder, str(val))
        return f"{head}{body}{tail}"

    def _format_artifact(self, ref: str, data: dict, fmt: str | None) -> str:
        content = data.get("content", "")
        if fmt == "inline_shell":
            return f"```shell\n# {ref}\n{content}\n```"
        if data.get("format") == "markdown" or ref.startswith("description:"):
            return f"\n{content}\n"
        if ref.startswith("snippet:"):
            lang = data.get("language", "")
            return f"```{lang}\n# {ref}\n{content}\n```"
        if ref.startswith("command:"):
            shell = data.get("shell", "bash")
            return f"```{shell}\n# {ref}\n{content}\n```"
        return content

    def build(
        self,
        role_id: str,
        cycle: int,
        radius: float,
        task_type: str = "",
        history_summary: str = "",
    ) -> str:
        embed = self._load_role_embed(role_id)
        if not embed:
            return f"[ERROR] No embed encontrado para {role_id}"
        artifacts_meta = embed.get("artifacts", [])
        template = embed.get("prompt_template", {})
        bindings = embed.get("dynamic_bindings", {})
        selected = self._eval_artifact_conditions(artifacts_meta, cycle, radius, task_type)
        identity_parts = []
        context_parts = []
        spec_parts = []
        commands_parts = []
        for art in selected:
            ref = art.get("ref", "")
            data = self._load_artifact(ref)
            if not data:
                continue
            fmt = art.get("format")
            rendered = self._format_artifact(ref, data, fmt)
            inject = art.get("inject_at", "body")
            if inject == "head":
                identity_parts.append(rendered)
            elif inject == "body":
                layer = art.get("layer", "context")
                if layer == "identity":
                    identity_parts.append(rendered)
                elif layer == "specialization":
                    spec_parts.append(rendered)
                else:
                    context_parts.append(rendered)
            elif inject == "tail":
                spec_parts.append(rendered)
            elif inject == "commands":
                commands_parts.append(rendered)
        base_identity = "\n".join(identity_parts) if identity_parts else ""
        context_artifacts = "\n".join(context_parts) if context_parts else ""
        specialized_artifacts = "\n".join(spec_parts) if spec_parts else ""
        commands_block = "\n".join(commands_parts) if commands_parts else ""
        artifact_list = ", ".join(a.get("ref", "") for a in selected)
        render_bindings = {
            **bindings,
            "base_identity": base_identity,
            "context_artifacts": context_artifacts,
            "specialized_artifacts": specialized_artifacts,
            "commands_block": commands_block,
            "cycle": cycle,
            "radius": radius,
            "task_type": task_type,
            "history_summary": history_summary,
            "artifact_list": artifact_list,
        }
        prompt = self._render_prompt_template(template, render_bindings)
        if commands_block:
            prompt += f"\n\n[COMANDOS DE APOYO]\n{commands_block}\n"
        return textwrap.dedent(prompt).strip()

    def build_for_spiral_state(self, role_id: str, spiral_state: dict) -> str:
        cycle = spiral_state.get("cycles_completed", 0) + 1
        radius = spiral_state.get("current_radius", 1.0)
        task_type = spiral_state.get("last_task_type", "")
        return self.build(role_id, cycle=cycle, radius=radius, task_type=task_type)

    def list_available_artifacts(self) -> list[str]:
        return sorted(self.artifact_index.get("artifacts", {}).keys())

    def list_role_embeds(self) -> list[dict]:
        results = []
        for p in self.roles_dir.rglob("*.embed.json"):
            data = json.loads(p.read_text(encoding="utf-8"))
            results.append({
                "role_id": data.get("role_id"),
                "file": str(p.relative_to(self.root)),
                "version": data.get("version"),
            })
        return results


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Spiral Prompt Builder")
    parser.add_argument("--role", required=True)
    parser.add_argument("--cycle", type=int, default=1)
    parser.add_argument("--radius", type=float, default=1.0)
    parser.add_argument("--task-type", default="")
    parser.add_argument("--history", default="")
    parser.add_argument("--bago-root", default=".")
    parser.add_argument("--list-artifacts", action="store_true")
    parser.add_argument("--list-embeds", action="store_true")
    args = parser.parse_args()
    builder = SpiralPromptBuilder(args.bago_root)
    if args.list_artifacts:
        for a in builder.list_available_artifacts():
            print(a)
        return 0
    if args.list_embeds:
        for e in builder.list_role_embeds():
            print(f"{e['role_id']}  (v{e.get('version', '?')})  [{e['file']}]")
        return 0
    prompt = builder.build(
        role_id=args.role,
        cycle=args.cycle,
        radius=args.radius,
        task_type=args.task_type,
        history_summary=args.history,
    )
    print(prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
