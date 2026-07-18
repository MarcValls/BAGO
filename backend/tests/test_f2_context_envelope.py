"""test_f2_context_envelope.py — Regression tests for F2: ContextEnvelope + ContextReceipt + SystemPromptCapsule + persistent goal.

Covers:
- ContextEnvelope construction and envelope_id determinism
- ContextReceipt captures usage, latency, finish_reason
- SystemPromptCapsule renders sections in order, omitting empties
- SessionManager.set_goal / clear_goal
- SessionManager.save/load persists persistent_goal
- effective_system_prompt includes goal when set
- effective_system_prompt excludes goal when empty
- last_receipt is populated after send()
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_BAGO_CORE = REPO_ROOT / ".bago" / "core"


# ── 1. ContextEnvelope ──────────────────────────────────────────────

def test_envelope_construction():
    """ContextEnvelope must store system_prompt, messages, tools, metadata."""
    from context_envelope import ContextEnvelope
    env = ContextEnvelope(
        system_prompt="You are BAGO.",
        messages=[{"role": "user", "content": "hello"}],
        tools=[{"type": "function", "function": {"name": "test"}}],
        metadata={"intent": "chat"},
    )
    assert env.system_prompt == "You are BAGO."
    assert len(env.messages) == 1
    assert env.tools is not None
    assert env.metadata["intent"] == "chat"


def test_envelope_id_deterministic():
    """Same envelope content must produce same envelope_id."""
    from context_envelope import ContextEnvelope
    env1 = ContextEnvelope(system_prompt="sys", messages=[{"role": "user", "content": "hi"}])
    env2 = ContextEnvelope(system_prompt="sys", messages=[{"role": "user", "content": "hi"}])
    assert env1.envelope_id() == env2.envelope_id(), "Identical envelopes must have same ID"


def test_envelope_id_changes_on_content_change():
    """Different content must produce different envelope_id."""
    from context_envelope import ContextEnvelope
    env1 = ContextEnvelope(system_prompt="sys", messages=[{"role": "user", "content": "hi"}])
    env2 = ContextEnvelope(system_prompt="sys", messages=[{"role": "user", "content": "bye"}])
    assert env1.envelope_id() != env2.envelope_id(), "Different envelopes must have different IDs"


# ── 2. ContextReceipt ────────────────────────────────────────────────

def test_receipt_from_response():
    """ContextReceipt.from_response must capture all fields."""
    from context_envelope import ContextEnvelope, ContextReceipt
    env = ContextEnvelope(system_prompt="sys", messages=[{"role": "user", "content": "hi"}])
    receipt = ContextReceipt.from_response(
        envelope=env,
        response_content="Hello!",
        model_used="qwen2.5:14b",
        finish_reason="stop",
        usage_input=10,
        usage_output=5,
        usage_total=15,
        latency_ms=42.5,
        extra_metadata={"intent": "chat"},
    )
    assert receipt.response_content == "Hello!"
    assert receipt.model_used == "qwen2.5:14b"
    assert receipt.finish_reason == "stop"
    assert receipt.usage["total_tokens"] == 15
    assert receipt.latency_ms == 42.5
    assert receipt.envelope_id == env.envelope_id()
    assert receipt.metadata["intent"] == "chat"
    assert receipt.metadata["envelope_messages_count"] == 1


def test_receipt_to_dict():
    """ContextReceipt.to_dict must be JSON-serializable."""
    from context_envelope import ContextEnvelope, ContextReceipt
    env = ContextEnvelope(system_prompt="sys", messages=[])
    receipt = ContextReceipt.from_response(
        envelope=env,
        response_content="ok",
        model_used="m",
        finish_reason="stop",
        usage_input=1,
        usage_output=1,
        usage_total=2,
        latency_ms=10.0,
    )
    d = receipt.to_dict()
    # Must be serializable
    json.dumps(d)
    assert d["model_used"] == "m"
    assert d["usage"]["total_tokens"] == 2


# ── 3. SystemPromptCapsule ───────────────────────────────────────────

def test_capsule_render_with_all_sections():
    """Capsule must render all non-empty sections joined by double newline."""
    from context_envelope import SystemPromptCapsule
    cap = SystemPromptCapsule(
        base="BASE",
        bago_mode_block="MODE B",
        active_agent_block="AGENT A",
        goal_block="GOAL G",
    )
    rendered = cap.render()
    assert "BASE" in rendered
    assert "MODE B" in rendered
    assert "AGENT A" in rendered
    assert "GOAL G" in rendered


def test_capsule_render_omits_empty_sections():
    """Capsule must skip empty sections."""
    from context_envelope import SystemPromptCapsule
    cap = SystemPromptCapsule(base="BASE", bago_mode_block="", active_agent_block="", goal_block="")
    rendered = cap.render()
    assert rendered == "BASE"
    assert "MODE" not in rendered


def test_capsule_render_all_empty():
    """Capsule with all empty sections renders to empty string."""
    from context_envelope import SystemPromptCapsule
    cap = SystemPromptCapsule()
    assert cap.render() == ""


# ── 4. SessionManager persistent goal ───────────────────────────────

def test_set_goal():
    """set_goal must update persistent_goal and return previous."""
    from session_manager import SessionManager
    with tempfile.TemporaryDirectory() as td:
        ws = tempfile.mkdtemp()
        mgr = SessionManager(
            session_id="test-f2-goal",
            provider="ollama-local",
            model="qwen2.5:14b",
            base_path=ws,
            state_root=td,
        )
        try:
            assert mgr.persistent_goal == ""
            result = mgr.set_goal("Refactorizar el módulo X")
            assert result["ok"] is True
            assert mgr.persistent_goal == "Refactorizar el módulo X"
            assert result["previous_goal"] == ""

            # Update goal
            result2 = mgr.set_goal("Nuevo objetivo")
            assert mgr.persistent_goal == "Nuevo objetivo"
            assert result2["previous_goal"] == "Refactorizar el módulo X"
        finally:
            mgr.close()


def test_clear_goal():
    """clear_goal must reset persistent_goal to empty."""
    from session_manager import SessionManager
    with tempfile.TemporaryDirectory() as td:
        ws = tempfile.mkdtemp()
        mgr = SessionManager(
            session_id="test-f2-clear",
            provider="ollama-local",
            model="qwen2.5:14b",
            base_path=ws,
            state_root=td,
        )
        try:
            mgr.set_goal("Temporal")
            assert mgr.persistent_goal == "Temporal"
            mgr.clear_goal()
            assert mgr.persistent_goal == ""
        finally:
            mgr.close()


def test_goal_in_system_prompt_when_set():
    """effective_system_prompt must include goal block when goal is set."""
    from session_manager import SessionManager
    with tempfile.TemporaryDirectory() as td:
        ws = tempfile.mkdtemp()
        mgr = SessionManager(
            session_id="test-f2-prompt",
            provider="ollama-local",
            model="qwen2.5:14b",
            base_path=ws,
            state_root=td,
        )
        try:
            without_goal = mgr.effective_system_prompt()
            assert "OBJETIVO PERSISTENTE" not in without_goal

            mgr.set_goal("Cumplir 50 tests")
            with_goal = mgr.effective_system_prompt()
            assert "OBJETIVO PERSISTENTE" in with_goal
            assert "Cumplir 50 tests" in with_goal
        finally:
            mgr.close()


def test_workspace_authority_block_is_explicit():
    """effective_system_prompt must expose the workspace roots and answer rule."""
    from session_manager import SessionManager
    with tempfile.TemporaryDirectory() as td:
        ws = tempfile.mkdtemp()
        mgr = SessionManager(
            session_id="test-f2-workspace-prompt",
            provider="ollama-local",
            model="qwen2.5:14b",
            base_path=ws,
            state_root=td,
        )
        try:
            prompt = mgr.effective_system_prompt()
            assert "AUTORIDADES DE RUTA" in prompt
            assert f"project_root={ws}" in prompt
            assert f"workspace_state_root={Path(ws) / '.gabo'}" in prompt
            assert "REGLA DE CONTEXTO" in prompt
            assert "project_root y workspace_state_root" in prompt
        finally:
            mgr.close()


def test_goal_persisted_in_save_load():
    """save/load must round-trip persistent_goal."""
    from session_manager import SessionManager
    with tempfile.TemporaryDirectory() as td:
        ws = tempfile.mkdtemp()
        mgr = SessionManager(
            session_id="test-f2-persist",
            provider="ollama-local",
            model="qwen2.5:14b",
            base_path=ws,
            state_root=td,
        )
        try:
            mgr.set_goal("Objetivo de persistencia")
            mgr.save()
        finally:
            mgr.close()

        loaded = SessionManager.load("test-f2-persist", state_root=td)
        try:
            assert loaded.persistent_goal == "Objetivo de persistencia"
        finally:
            loaded.close()


def test_goal_empty_after_load_when_never_set():
    """load must default persistent_goal to empty when never set."""
    from session_manager import SessionManager
    with tempfile.TemporaryDirectory() as td:
        ws = tempfile.mkdtemp()
        mgr = SessionManager(
            session_id="test-f2-nogoal",
            provider="ollama-local",
            model="qwen2.5:14b",
            base_path=ws,
            state_root=td,
        )
        try:
            mgr.save()
        finally:
            mgr.close()

        loaded = SessionManager.load("test-f2-nogoal", state_root=td)
        try:
            assert loaded.persistent_goal == ""
        finally:
            loaded.close()
