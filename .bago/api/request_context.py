"""request_context.py \u2014 shared per-request state for legacy chat/command/switch.

BagoAPIHandler carries per-request state in instance attributes
(session_mgr, shadow, headers, _channel, etc.). When the legacy
chat/command/switch handlers migrate out of bridge.py they need a
portable substitute that doesn't rely on `self`.

RequestContext bundles everything a single legacy handler needs:

  - mgr / engine / shadow        : the 3 wired backends
  - handler                       : the BaseHTTPRequestHandler
  - channel()                     : the X-Bago-Channel / body.channel shortcut
  - send_json(status, dict)       : Qwen-framed JSON response
  - record_shadow(**kwargs)       : ControlShadow.log_event wrapper
  - json_safe(value)              : dataclass/Path/enum-safe serializer
  - read_body(max_bytes)          : JSON body parser
  - timed_call(fn)                : runs fn() and returns (result, elapsed_ms)

All stateless: every handler creates one fresh RequestContext per
request and discards it when done. This is the explicit migration
target for /chat, /command, /switch so the legacy handlers can move
to handlers_chat.py / handlers_command.py / handlers_switch.py
without losing their existing semantics.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from api_serializers import json_safe, read_body as _read_body, send_json


@dataclass
class RequestContext:
    handler: Any
    session_mgr: Any = None
    switch_engine: Any = None
    shadow: Any = None
    chat_timeout_s: float = 30.0

    def channel(self, body: Optional[dict] = None) -> str:
        hdr = ""
        try:
            hdr = self.handler.headers.get("X-Bago-Channel", "")
        except Exception:
            hdr = ""
        body_ch = str((body or {}).get("channel") or "")
        return body_ch or hdr or "api"

    def send_json(self, status: int, data: dict[str, Any]) -> None:
        send_json(self.handler, status, data)

    def read_body(self, max_bytes: int = 1024 * 1024) -> dict[str, Any]:
        return _read_body(self.handler, max_bytes)

    def json_safe(self, value: Any) -> Any:
        return json_safe(value)

    def record_shadow(
        self,
        *,
        action_kind: str,
        channel: str,
        payload: dict[str, Any],
        pre_state: dict[str, Any],
        post_state: dict[str, Any],
        result: dict[str, Any],
        elapsed_ms: float,
    ) -> None:
        if self.shadow is None or self.session_mgr is None:
            return
        try:
            self.shadow.log_event(
                mgr=self.session_mgr,
                channel=channel,
                action_kind=action_kind,
                payload=payload,
                pre_state=pre_state,
                post_state=post_state,
                result=result,
                elapsed_ms=elapsed_ms,
            )
        except Exception:
            return

    def timed_call(self, fn: Callable[[], Any]) -> tuple[Any, float]:
        started = time.time()
        result = fn()
        return result, (time.time() - started) * 1000


def build_context(handler: Any) -> RequestContext:
    return RequestContext(
        handler=handler,
        session_mgr=getattr(handler, "session_mgr", None),
        switch_engine=getattr(handler, "switch_engine", None),
        shadow=getattr(handler, "shadow", None),
        chat_timeout_s=float(getattr(handler, "chat_timeout_s", 30.0) or 30.0),
    )
