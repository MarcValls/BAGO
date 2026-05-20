"""bago.api.models.bagomodel — BAGOMODEL spec: perfil declarativo de routing.

Analogia: Ollama tiene Modelfile (FROM + PARAMETER + TEMPLATE + SYSTEM).
BAGO tiene BAGOMODEL (FROM + PARAMETER + SYSTEM + routing rules).

La diferencia: un BAGOMODEL no define un modelo de inferencia,
define un *perfil de routing* — que modelo usar, con que fallbacks,
quality guards y estrategia de escalado.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
import json


# ─── Parametros validos ──────────────────────────────────────────────────────

VALID_PARAMS = {
    "temperature":      float,
    "num_ctx":          int,
    "num_predict":      int,
    "top_k":            int,
    "top_p":            float,
    "min_p":            float,
    "repeat_penalty":   float,
    "repeat_last_n":    int,
    "seed":             int,
    "stop":             str,
    "quality_guard":     bool,
    "context_escalation": bool,
    "anti_repetition":   bool,
    "fallback":          str,
    "max_switches":      int,
    "best_for":          str,
}


@dataclass
class BagoModel:
    """Perfil de routing BAGO — equivalente a Modelfile de Ollama
    pero para orquestacion multi-provider."""

    name: str
    from_model: str                              # e.g. "qwen25-coder", "llama3.3:70b"
    system: str = ""
    parameters: dict = field(default_factory=dict)
    template: str = ""
    messages: list = field(default_factory=list)
    adapter: str = ""
    license: str = ""
    requires: str = ""

    # ── BAGO-specific ──
    fallback: Optional[str] = None               # "codex/gpt-5.4"
    quality_guard: bool = True
    context_escalation: bool = True
    anti_repetition: bool = True
    max_switches: int = 3
    best_for: str = ""

    def to_modelfile(self) -> str:
        """Serializa a formato BAGOMODEL (compatible con parser Ollama + extensiones)."""
        lines = [f"FROM {self.from_model}"]
        if self.system:
            lines.append(f'SYSTEM """{self.system}"""')
        for k, v in self.parameters.items():
            lines.append(f"PARAMETER {k} {v}")
        if self.template:
            lines.append(f'TEMPLATE """{self.template}"""')
        if self.fallback:
            lines.append(f"PARAMETER fallback {self.fallback}")
        if not self.quality_guard:
            lines.append("PARAMETER quality_guard false")
        if not self.context_escalation:
            lines.append("PARAMETER context_escalation false")
        if not self.anti_repetition:
            lines.append("PARAMETER anti_repetition false")
        if self.max_switches != 3:
            lines.append(f"PARAMETER max_switches {self.max_switches}")
        if self.best_for:
            lines.append(f"PARAMETER best_for {self.best_for}")
        for msg in self.messages:
            lines.append(f"MESSAGE {msg['role']} {msg['content']}")
        if self.adapter:
            lines.append(f"ADAPTER {self.adapter}")
        if self.license:
            lines.append(f'LICENSE """{self.license}"""')
        if self.requires:
            lines.append(f"REQUIRES {self.requires}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# ─── Parser ──────────────────────────────────────────────────────────────────

_BAGO_PARAMS = {"fallback", "quality_guard", "context_escalation",
                "anti_repetition", "max_switches", "best_for"}

_BOOL_MAP = {"true": True, "false": False, "1": True, "0": False}

_MULTILINE_KEYWORDS = ("SYSTEM", "TEMPLATE", "LICENSE")


def _parse_inline_or_multiline(kw: str, stripped: str) -> tuple:
    """Parse a SYSTEM/TEMPLATE/LICENSE line.

    Returns (value, is_multiline_start).
    - If the line has opening and closing triple-quotes on the same line,
      returns (content, False).
    - If the line starts multiline (opening triple-quotes only),
      returns (None, True).
    - If no triple-quotes, treats rest of line as value, returns (value, False).
    """
    rest = stripped[len(kw):].strip()

    if not rest:
        # Empty — start multiline
        return None, True

    # Check for triple-quote patterns
    triple = '"""'

    if rest.startswith(triple):
        # Find closing """
        end_idx = rest.find(triple, 3)
        if end_idx != -1:
            # Inline: SYSTEM """content"""
            content = rest[3:end_idx].strip()
            return content, False
        else:
            # Multiline start: SYSTEM """
            return None, True

    # No triple-quotes: SYSTEM some text
    return rest, False


def parse_bagomodel(text: str, name: str = "") -> BagoModel:
    """Parsea un BAGOMODEL desde texto (mismo formato que Modelfile + extensiones)."""
    model = BagoModel(name=name, from_model="")
    parameters = {}
    messages = []
    current_multiline = None
    multiline_buf = []

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if current_multiline:
            if stripped == '"""':
                content = "\n".join(multiline_buf)
                if current_multiline == "SYSTEM":
                    model.system = content
                elif current_multiline == "TEMPLATE":
                    model.template = content
                elif current_multiline == "LICENSE":
                    model.license = content
                current_multiline = None
                multiline_buf = []
            else:
                multiline_buf.append(line)
            continue

        if stripped.startswith("FROM "):
            model.from_model = stripped[5:].strip()
            continue

        # SYSTEM / TEMPLATE / LICENSE
        matched_kw = None
        for kw in _MULTILINE_KEYWORDS:
            if stripped.startswith(kw + " ") or stripped == kw:
                matched_kw = kw
                break

        if matched_kw:
            value, is_multiline = _parse_inline_or_multiline(matched_kw, stripped)
            if is_multiline:
                current_multiline = matched_kw
                multiline_buf = []
            else:
                # Inline value
                if matched_kw == "SYSTEM":
                    model.system = value or ""
                elif matched_kw == "TEMPLATE":
                    model.template = value or ""
                elif matched_kw == "LICENSE":
                    model.license = value or ""
            continue

        if stripped.startswith("PARAMETER "):
            rest = stripped[10:].strip()
            parts = rest.split(None, 1)
            if len(parts) == 2:
                pk, pv = parts
                if pk in _BAGO_PARAMS:
                    if pk == "fallback":
                        model.fallback = pv
                    elif pk in ("quality_guard", "context_escalation", "anti_repetition"):
                        setattr(model, pk, _BOOL_MAP.get(pv.lower(), pv))
                    elif pk == "max_switches":
                        model.max_switches = int(pv)
                    elif pk == "best_for":
                        model.best_for = pv
                else:
                    expected_type = VALID_PARAMS.get(pk)
                    if expected_type == int:
                        parameters[pk] = int(pv)
                    elif expected_type == float:
                        parameters[pk] = float(pv)
                    elif expected_type == bool:
                        parameters[pk] = _BOOL_MAP.get(pv.lower(), pv)
                    else:
                        parameters[pk] = pv
            continue

        if stripped.startswith("MESSAGE "):
            rest = stripped[8:].strip()
            role_end = rest.find(" ")
            if role_end > 0:
                role = rest[:role_end]
                content = rest[role_end+1:]
                messages.append({"role": role, "content": content})
            continue

        if stripped.startswith("ADAPTER "):
            model.adapter = stripped[8:].strip()
            continue

        if stripped.startswith("REQUIRES "):
            model.requires = stripped[9:].strip()
            continue

    model.parameters = parameters
    model.messages = messages
    return model


def load_bagomodel(path: Path, name: str = "") -> BagoModel:
    """Carga un BAGOMODEL desde archivo."""
    text = path.read_text(encoding="utf-8")
    if not name:
        name = path.stem
    return parse_bagomodel(text, name=name)


def save_bagomodel(model: BagoModel, path: Path) -> None:
    """Guarda un BAGOMODEL como archivo de texto."""
    path.write_text(model.to_modelfile(), encoding="utf-8")
