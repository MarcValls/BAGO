from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from ir_types import IRConversation, IRMessage
from protocol import EvidenceSpec, Safety, SupportsSpec, Vocab


def _extract_text(payload: Any) -> str:
    if isinstance(payload, dict):
        if payload.get("choices"):
            try:
                return str(payload["choices"][0]["message"].get("content", "") or "")
            except Exception:
                pass
        if isinstance(payload.get("content"), list):
            for item in payload["content"]:
                if isinstance(item, dict) and item.get("type") == "text":
                    return str(item.get("text", "") or "")
        if payload.get("message") and isinstance(payload["message"], dict):
            return str(payload["message"].get("content", "") or "")
    return ""


def _extract_tool(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    if payload.get("choices"):
        try:
            tool_calls = payload["choices"][0]["message"].get("tool_calls") or []
            if tool_calls:
                call = tool_calls[0]
                function = call.get("function", {})
                return {
                    "type": "tool_call",
                    "name": function.get("name", ""),
                    "args": json.loads(function.get("arguments", "{}") or "{}"),
                }
        except Exception:
            return None
    if isinstance(payload.get("content"), list):
        for item in payload["content"]:
            if isinstance(item, dict) and item.get("type") == "tool_use":
                return {
                    "type": "tool_call",
                    "name": item.get("name", ""),
                    "args": item.get("input", {}) or {},
                }
    if payload.get("message") and isinstance(payload["message"], dict):
        text = str(payload["message"].get("content", "") or "")
        m = re.search(r"<bago:tool_call>(.*?)</bago:tool_call>", text)
        if m:
            try:
                data = json.loads(m.group(1))
            except Exception:
                data = {}
            return {"type": "tool_call", "name": data.get("name", ""), "args": data.get("args", {})}
    return None


@dataclass
class _TranslatorCodec:
    piece_id: str
    model_family: str
    model_id: str

    def encode(self, conversation: IRConversation) -> dict[str, Any]:
        return {
            "piece_id": self.piece_id,
            "model": self.model_id,
            "family": self.model_family,
            "messages": [m.to_dict() for m in conversation.messages],
            "model_hint": conversation.model_hint,
        }

    def decode(self, payload: Any) -> IRConversation:
        text = _extract_text(payload)
        text_only = re.sub(r"<bago:(plan|evidence|tool_call)>.*?</bago:\\1>", "", text)
        parts: list[dict[str, Any]] = []
        if text_only.strip():
            parts.append({"type": "text", "text": text_only.strip()})
        for tag in ("plan", "evidence"):
            m = re.search(rf"<bago:{tag}>(.*?)</bago:{tag}>", text)
            if m:
                try:
                    data = json.loads(m.group(1))
                except Exception:
                    data = {"type": tag, "text": m.group(1)}
                parts.append(data if isinstance(data, dict) else {"type": tag, "text": str(data)})
        tool = _extract_tool(payload)
        if tool:
            parts.append(tool)
        return IRConversation(messages=[IRMessage(id="assistant-0", role="assistant", parts=parts)])


@dataclass
class _TranslatorPiece:
    manifest: dict[str, Any]
    encode: _TranslatorCodec
    decode: _TranslatorCodec

    @property
    def piece_id(self) -> str:
        return self.manifest["piece_id"]


_PIECES = [
    {"piece_id": "translator.openai.gpt-4o", "model_family": "openai", "model_id": "gpt-4o"},
    {"piece_id": "translator.anthropic.claude-3-5-sonnet", "model_family": "anthropic", "model_id": "claude-3-5-sonnet"},
    {"piece_id": "translator.ollama.llama3.2", "model_family": "ollama", "model_id": "llama3.2:3b"},
    {"piece_id": "translator.gemini.gemini-2.0", "model_family": "gemini", "model_id": "gemini-2.0-flash"},
]

_REGISTRY = []
for item in _PIECES:
    codec = _TranslatorCodec(item["piece_id"], item["model_family"], item["model_id"])
    manifest = {
        **item,
        "version": "v1",
        "vocab": Vocab(),
        "safety": Safety(),
        "evidence": EvidenceSpec(),
        "supports": SupportsSpec(),
    }
    _REGISTRY.append(_TranslatorPiece(manifest=manifest, encode=codec, decode=codec))


def discover_translators() -> list[_TranslatorPiece]:
    return list(_REGISTRY)


def get_translator(piece_id: str) -> _TranslatorPiece | None:
    for piece in _REGISTRY:
        if piece.piece_id == piece_id:
            return piece
    return None


def list_translators() -> list[dict[str, Any]]:
    return [
        {
            "piece_id": piece.piece_id,
            "model_family": piece.manifest["model_family"],
            "model_id": piece.manifest["model_id"],
            "version": piece.manifest["version"],
            "store_path": "local-fallback",
        }
        for piece in _REGISTRY
    ]
