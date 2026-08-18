#!/usr/bin/env python3
"""

_CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo
context_compressor.py — BAGO 4.1.5 Hierarchical Layer Compression

Compresión por capas para downgrades de modelo:
- Las capas se enlazan formando bloques unificados.
- Cada nueva capa compacta: su propio contenido + el bloque anterior.
- Los mensajes marcados como "good" (documentados) sobreviven sin dilución.
- Los demás se resumen, perdiendo detalle progresivamente.

Arquitectura atómica:
  Layer → Block → Unified Block → ... → Final Compressed Context
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


@dataclass
class MessageNode:
    """Nodo individual de mensaje en una capa."""
    role: str
    content: str
    layer_id: int
    good: bool = False  # Si True, no se diluye en compresión
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "layer_id": self.layer_id,
            "good": self.good,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MessageNode":
        return cls(
            role=d["role"],
            content=d["content"],
            layer_id=d.get("layer_id", 0),
            good=d.get("good", False),
            metadata=d.get("metadata", {}),
        )


@dataclass
class Layer:
    """Una capa de interacción (user message + assistant response)."""
    layer_id: int
    user: MessageNode | None = None
    assistant: MessageNode | None = None
    system: MessageNode | None = None
    summary: str = ""  # Resumen generado de esta capa
    compressed: bool = False

    def token_estimate(self) -> int:
        """Estimación rápida de tokens (~4 chars por token)."""
        total = 0
        for node in (self.user, self.assistant, self.system):
            if node:
                total += len(node.content) // 4
        return total

    def to_dict(self) -> dict:
        return {
            "layer_id": self.layer_id,
            "user": self.user.to_dict() if self.user else None,
            "assistant": self.assistant.to_dict() if self.assistant else None,
            "system": self.system.to_dict() if self.system else None,
            "summary": self.summary,
            "compressed": self.compressed,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Layer":
        return cls(
            layer_id=d["layer_id"],
            user=MessageNode.from_dict(d["user"]) if d.get("user") else None,
            assistant=MessageNode.from_dict(d["assistant"]) if d.get("assistant") else None,
            system=MessageNode.from_dict(d["system"]) if d.get("system") else None,
            summary=d.get("summary", ""),
            compressed=d.get("compressed", False),
        )


class ContextCompressor:
    """Compresor jerárquico por capas."""

    def __init__(self, target_tokens: int = 4096, char_per_token: int = 4):
        self.target_tokens = target_tokens
        self.char_per_token = char_per_token

    def build_layers(self, history: list[dict]) -> list[Layer]:
        """Construye capas desde el historial OpenAI-like."""
        layers: list[Layer] = []
        current_layer: Layer | None = None
        layer_counter = 0

        for entry in history:
            role = entry.get("role", "")
            content = entry.get("content", "")
            good = entry.get("metadata", {}).get("good", False)

            if role == "system":
                # Los system prompts van en su propia capa 0
                if not layers:
                    layers.append(Layer(layer_id=0, system=MessageNode("system", content, 0, good)))
                else:
                    layers[0].system = MessageNode("system", content, 0, good)
                continue

            if role == "user":
                layer_counter += 1
                current_layer = Layer(layer_id=layer_counter, user=MessageNode("user", content, layer_counter, good))
                layers.append(current_layer)
            elif role == "assistant" and current_layer is not None:
                current_layer.assistant = MessageNode("assistant", content, layer_counter, good)

        return layers

    def summarize_layer(self, layer: Layer) -> str:
        """Genera un resumen de una capa. Si tiene mensajes 'good', se preservan."""
        parts: list[str] = []

        if layer.system and layer.system.good:
            parts.append(f"[SYS] {layer.system.content[:200]}")
        elif layer.system and not layer.compressed:
            parts.append(f"[SYS-instrucción base]")

        if layer.user and layer.user.good:
            parts.append(f"[USER-GOOD] {layer.user.content[:300]}")
        elif layer.user:
            parts.append(f"[USER] {self._extract_key_points(layer.user.content)}")

        if layer.assistant and layer.assistant.good:
            parts.append(f"[ASSISTANT-GOOD] {layer.assistant.content[:300]}")
        elif layer.assistant:
            parts.append(f"[ASSISTANT] {self._extract_key_points(layer.assistant.content)}")

        return " | ".join(parts) if parts else "[capa vacía]"

    def _extract_key_points(self, text: str, max_words: int = 15) -> str:
        """Extracción ultra-ligera de puntos clave."""
        words = text.split()
        if len(words) <= max_words:
            return text
        # Heurística: primera oración + última oración
        first_sentence = " ".join(words[:max_words])
        last_sentence = " ".join(words[-max_words:]) if len(words) > max_words * 2 else ""
        if last_sentence and last_sentence != first_sentence:
            return f"{first_sentence} ... {last_sentence}"
        return f"{first_sentence} ..."

    def compress_layers(self, layers: list[Layer]) -> list[Layer]:
        """
        Compresión por capas enlazadas:
        - Capa 1 → resumen (bloque A)
        - Capa 2 → resumen + bloque A → nuevo bloque unificado B
        - Capa 3 → resumen + bloque B → bloque C
        - Y así sucesivamente...
        """
        if not layers:
            return []

        compressed: list[Layer] = []
        unified_block = ""

        for i, layer in enumerate(layers):
            if layer.layer_id == 0:
                # Capa 0 (system) siempre se preserva íntegra o resumida
                if layer.system and layer.system.good:
                    compressed.append(layer)
                else:
                    layer.summary = self.summarize_layer(layer)
                    layer.compressed = True
                    compressed.append(layer)
                continue

            # Generar resumen de esta capa
            layer_summary = self.summarize_layer(layer)

            if unified_block:
                # Unificar: nuevo resumen + bloque anterior
                unified_block = f"{layer_summary} || PREV: {unified_block[:500]}"
            else:
                unified_block = layer_summary

            # Crear capa comprimida unificada
            compressed_layer = Layer(
                layer_id=layer.layer_id,
                user=MessageNode("user", f"[Capa {layer.layer_id} comprimida]", layer.layer_id),
                assistant=MessageNode("assistant", unified_block, layer.layer_id),
                compressed=True,
                summary=unified_block,
            )

            # Preservar mensajes 'good' de esta capa original
            for node in (layer.user, layer.assistant, layer.system):
                if node and node.good:
                    # Inyectar como mensaje adicional preservado
                    compressed_layer.assistant.content += f"\n\n[PRESERVED {node.role.upper()}]: {node.content}"

            compressed.append(compressed_layer)

        return compressed

    def to_history(self, layers: list[Layer]) -> list[dict]:
        """Convierte capas comprimidas de vuelta a formato historial."""
        history: list[dict] = []
        for layer in layers:
            if layer.system:
                history.append({"role": "system", "content": layer.system.content})
            if layer.user:
                history.append({"role": "user", "content": layer.user.content})
            if layer.assistant:
                history.append({"role": "assistant", "content": layer.assistant.content})
        return history

    def compact_for_downgrade(self, history: list[dict], target_tokens: int | None = None) -> list[dict]:
        """API principal: compacta historial completo para un modelo menor."""
        self.target_tokens = target_tokens or self.target_tokens
        layers = self.build_layers(history)
        compressed = self.compress_layers(layers)
        return self.to_history(compressed)


class LayerStore:
    """Persistencia de capas comprimidas en JSON Lines."""

    def __init__(self, base_dir: Path | str):
        self.base_dir = Path(base_dir) / ".bago" / "state" / "layers"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._file = self.base_dir / "layers.jsonl"

    def save_layers(self, layers: list[Layer], session_id: str) -> None:
        path = self.base_dir / f"{session_id}_layers.jsonl"
        with open(path, "w", encoding="utf-8") as fh:
            for layer in layers:
                fh.write(json.dumps(layer.to_dict(), ensure_ascii=False) + "\n")

    def load_layers(self, session_id: str) -> list[Layer]:
        path = self.base_dir / f"{session_id}_layers.jsonl"
        if not path.exists():
            return []
        layers = []
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    layers.append(Layer.from_dict(json.loads(line)))
        return layers

    def mark_good(self, session_id: str, layer_id: int, role: str) -> bool:
        """Marca un mensaje de una capa como 'good' (no diluible)."""
        layers = self.load_layers(session_id)
        for layer in layers:
            if layer.layer_id == layer_id:
                node = getattr(layer, role, None)
                if node:
                    node.good = True
                    self.save_layers(layers, session_id)
                    return True
        return False


# ── Quick test ────────────────────────────────────────────────────────

def _run_tests() -> int:
    # Test Layer building
    history = [
        {"role": "system", "content": "Eres un asistente útil.", "metadata": {"good": True}},
        {"role": "user", "content": "Explícame la teoría de la relatividad en detalle.", "metadata": {}},
        {"role": "assistant", "content": "La relatividad de Einstein establece que el espacio y el tiempo están interconectados... [texto largo]", "metadata": {}},
        {"role": "user", "content": "¿Y la relatividad general?", "metadata": {}},
        {"role": "assistant", "content": "La relatividad general extiende la especial incluyendo la gravedad como curvatura del espaciotiempo...", "metadata": {}},
    ]

    compressor = ContextCompressor(target_tokens=512)
    layers = compressor.build_layers(history)
    assert len(layers) == 3  # system (0), capa 1, capa 2
    assert layers[0].system is not None
    assert layers[1].user.content == "Explícame la teoría de la relatividad en detalle."

    # Test compression
    compressed = compressor.compress_layers(layers)
    assert len(compressed) == 3
    assert compressed[0].layer_id == 0  # system preserved
    assert compressed[1].compressed is True
    assert compressed[2].compressed is True

    # Test unified block chaining
    block_1 = compressed[1].summary
    block_2 = compressed[2].summary
    assert "PREV:" in block_2  # Capa 2 debe contener el bloque unificado de la 1

    # Test mark as good
    store = LayerStore(".")
    store.save_layers(layers, "test-session")
    ok = store.mark_good("test-session", 1, "user")
    assert ok
    loaded = store.load_layers("test-session")
    assert loaded[1].user.good is True

    # Test compact_for_downgrade API
    result = compressor.compact_for_downgrade(history)
    assert len(result) >= 3  # system + user + assistant mínimo

    print("context_compressor.py --test: ALL PASS")
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
