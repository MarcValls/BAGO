"""Injective, Windows-safe path components for PI execution artifacts."""
from __future__ import annotations

import base64
import re


_DIRECT_COMPONENT = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
_WINDOWS_DEVICE = re.compile(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])\Z", re.IGNORECASE)


def artifact_component(identity: str) -> str:
    value = str(identity or "")
    if not value or len(value) > 128 or not value.isascii() or not re.fullmatch(r"[A-Za-z0-9._:-]+", value):
        raise ValueError("PI artifact identity is invalid")
    if _DIRECT_COMPONENT.fullmatch(value) and not _WINDOWS_DEVICE.fullmatch(value):
        return value
    encoded = base64.urlsafe_b64encode(value.encode("ascii")).decode("ascii").rstrip("=")
    return f"id-{encoded}"
