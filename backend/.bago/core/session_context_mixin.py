#!/usr/bin/env python3
"""Facade mixin that composes the modularized session context helpers."""
from __future__ import annotations

from session_context_workspace_mixin import SessionContextWorkspaceMixin
from session_context_envelope_mixin import SessionContextEnvelopeMixin
from session_context_policy_mixin import SessionContextPolicyMixin


class SessionContextMixin(
    SessionContextWorkspaceMixin,
    SessionContextEnvelopeMixin,
    SessionContextPolicyMixin,
):
    """Mixin: system prompt construction, RAG retrieval, BC policy, auto-evolve."""
    pass
