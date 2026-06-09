"""Local translator registry shim for clean CI environments.

The historical release expects translator pieces to be discoverable through a
`registry` module plus `ir_types` / `protocol` helpers. This file provides the
minimum stable surface needed by the bootstrap and translator smoke tests when
the external ProgramData bundle is absent.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from ir_types import (
    IRConversation,
    IRMessage,
    PART_TYPE_EVIDENCE,
    PART_TYPE_PLAN,
    PART_TYPE_TEXT,
    PART_TYPE_TOOL_CALL,
    PART_TYPE_TOOL_RESULT,
    ROLE_ASSISTANT,
    ROLE_SYSTEM,
    ROLE_TOOL,
    ROLE_USER,
)


_TRANSLATOR_SPECS: list[dict[str, str]] = [
    {
        "piece_id": "translator.shared.base",
        "type": "translator",
        "scope": "shared",
        "version": "1.0",
        "model_family": "shared",
        "model_id": "base",
    },
    {
        "piece_id": "translator.openai.gpt-4o",
        "type": "translator",
        "scope": "cloud",
        "version": "1.0",
        "model_family": "openai",
        "model_id": "gpt-4o",
    },
    {
        "piece_id": "translator.anthropic.claude-3-5-sonnet",
        "type": "translator",
        "scope": "cloud",
        "version": "1.0",
        "model_family": "anthropic",
        "model_id": "claude-3-5-sonnet",
    },
    {
        "piece_id": "translator.ollama.llama3.2",
        "type": "translator",
        "scope": "local",
        "version": "1.0",
        "model_family": "ollama",
        "model_id": "llama3.2",
    },
    {
        "piece_id": "translator.ollama.granite3.2-8b",
        "type": "translator",
        "scope": "local",
        "version": "1.0",
        "model_family": "ollama",
        "model_id": "granite3.2-8b",
    },
]


def _part_to_dict(part: dict[str, Any] | Any) -> dict[str, Any]:
    if isinstance(part, dict):
        return dict(part)
    if hasattr(part, "to_dict"):
        try:
            return dict(part.to_dict())
        except Exception:
            pass
    return {"type": PART_TYPE_TEXT, "text": str(part)}


def _serialize_message(message: IRMessage | dict[str, Any]) -> dict[str, Any]:
    if hasattr(message, "to_dict"):
        raw = message.to_dict()
    elif isinstance(message, dict):
        raw = dict(message)
    else:
        raw = {"id": getattr(message, "id", ""), "role": getattr(message, "role", ""), "parts": getattr(message, "parts", [])}
    raw["parts"] = [_part_to_dict(part) for part in raw.get("parts", [])]
    return raw


def _text_from_parts(parts: list[dict[str, Any]]) -> str:
    chunks: list[str] = []
    for part in parts:
        ptype = part.get("type")
        if ptype == PART_TYPE_TEXT:
            chunks.append(str(part.get("text", "")))
        elif ptype in {PART_TYPE_PLAN, PART_TYPE_EVIDENCE, PART_TYPE_TOOL_CALL, PART_TYPE_TOOL_RESULT}:
            chunks.append(json.dumps(part, ensure_ascii=False))
    return " ".join(chunk for chunk in chunks if chunk).strip()


def _extract_tag(text: str, tag: str) -> dict[str, Any] | None:
    match = re.search(rf"<bago:{tag}>(.*?)</bago:{tag}>", text, re.S)
    if not match:
        return None
    payload = match.group(1).strip()
    try:
        return json.loads(payload)
    except Exception:
        return {"type": tag, "text": payload}


def _strip_tags(text: str) -> str:
    return re.sub(r"<bago:(?:plan|evidence|tool_call)>.*?</bago:(?:plan|evidence|tool_call)>", "", text, flags=re.S).strip()


def _response_text(response: Any) -> tuple[str, dict[str, Any] | None]:
    if not isinstance(response, dict):
        return (str(response), None)

    if "choices" in response:
        choice = (response.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        text = str(message.get("content", "") or "")
        tool_calls = message.get("tool_calls")
        tool_call = None
        if isinstance(tool_calls, list) and tool_calls:
            tool_call = tool_calls[0]
        return (text, tool_call)

    if "content" in response and isinstance(response["content"], list):
        text_parts = [item.get("text", "") for item in response["content"] if isinstance(item, dict) and item.get("type") == "text"]
        tool_call = next((item for item in response["content"] if isinstance(item, dict) and item.get("type") == "tool_use"), None)
        return (" ".join(str(text) for text in text_parts if text).strip(), tool_call)

    message = response.get("message")
    if isinstance(message, dict):
        text = str(message.get("content", "") or "")
        if "<bago:tool_call>" in text:
            return (text, _extract_tag(text, "tool_call"))
        return (text, None)

    return (json.dumps(response, ensure_ascii=False), None)


@dataclass
class _Encoder:
    family: str
    model_id: str

    def encode(self, conversation: IRConversation) -> dict[str, Any]:
        messages = [_serialize_message(message) for message in getattr(conversation, "messages", [])]
        if self.family == "ollama":
            last_message = messages[-1] if messages else {"role": ROLE_USER, "parts": []}
            return {"model": self.model_id, "message": last_message, "messages": messages}
        return {"model": self.model_id, "messages": messages}


@dataclass
class _Decoder:
    family: str
    model_id: str

    def decode(self, response: Any) -> IRConversation:
        text, tool_call = _response_text(response)
        parts: list[dict[str, Any]] = []
        visible_text = _strip_tags(text)
        if visible_text:
            parts.append({"type": PART_TYPE_TEXT, "text": visible_text})
        for tag in ("plan", "evidence"):
            payload = _extract_tag(text, tag)
            if isinstance(payload, dict):
                payload.setdefault("type", tag)
                parts.append(payload)
        if tool_call is not None:
            if isinstance(tool_call, dict) and "function" in tool_call:
                function = tool_call.get("function") or {}
                parts.append({
                    "type": PART_TYPE_TOOL_CALL,
                    "name": function.get("name", ""),
                    "args": _coerce_json(function.get("arguments", {})),
                })
            elif isinstance(tool_call, dict):
                if tool_call.get("type") == "tool_use":
                    parts.append({
                        "type": PART_TYPE_TOOL_CALL,
                        "name": tool_call.get("name", ""),
                        "args": _coerce_json(tool_call.get("input", {})),
                    })
                elif "name" in tool_call:
                    parts.append({
                        "type": PART_TYPE_TOOL_CALL,
                        "name": tool_call.get("name", ""),
                        "args": _coerce_json(tool_call.get("args", {})),
                    })
        if not parts:
            parts.append({"type": PART_TYPE_TEXT, "text": visible_text or ""})
        return IRConversation(
            messages=[IRMessage(id="decoded-1", role=ROLE_ASSISTANT, parts=parts)],
            model_hint=self.model_id,
        )


def _coerce_json(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


@dataclass
class TranslatorPiece:
    manifest: dict[str, Any]
    encode: _Encoder
    decode: _Decoder


def _make_piece(spec: dict[str, str]) -> TranslatorPiece:
    manifest = {
        **spec,
        "hash": f"sha256:{spec['piece_id'].replace('.', '-').replace('/', '-')}",
        "store_path": spec["piece_id"],
        "supports": {
            "roundtrip": True,
            "evidence": True,
            "tool_calls": spec["model_family"] != "shared",
        },
    }
    return TranslatorPiece(
        manifest=manifest,
        encode=_Encoder(spec["model_family"], spec["model_id"]),
        decode=_Decoder(spec["model_family"], spec["model_id"]),
    )


_PIECES = [_make_piece(spec) for spec in _TRANSLATOR_SPECS]
_PIECES_BY_ID = {piece.manifest["piece_id"]: piece for piece in _PIECES}


def list_translators() -> list[dict[str, Any]]:
    return [dict(piece.manifest) for piece in _PIECES]


def get_translator(piece_id: str) -> TranslatorPiece | None:
    return _PIECES_BY_ID.get(piece_id)
