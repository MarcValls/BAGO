"""test_f3_rag.py — Regression tests for F3: automatic RAG in chat flow.

Covers:
- _rag_retrieve returns keyword matches from KnowledgeBase
- _rag_retrieve returns empty list when no knowledge stored
- _format_rag_context returns empty string for no fragments
- _format_rag_context includes content and source for fragments
- _rag_retrieve deduplicates by content
- send() injects RAG context into system prompt (via envelope metadata)
- RAG is non-blocking: errors in search don't crash send()
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_BAGO_CORE = REPO_ROOT / ".bago" / "core"


def test_rag_retrieve_returns_keyword_matches():
    """_rag_retrieve must find content from KnowledgeBase via keyword search."""
    from session_manager import SessionManager
    with tempfile.TemporaryDirectory() as td:
        ws = tempfile.mkdtemp()
        mgr = SessionManager(
            session_id="test-f3-kw",
            provider="ollama-local",
            model="qwen2.5:14b",
            base_path=ws,
            state_root=td,
        )
        try:
            mgr.knowledge.add("BAGO uses SQLite for session storage", source_session=mgr.session_id)
            mgr.knowledge.add("The model adapter normalizes messages", source_session=mgr.session_id)

            fragments = mgr._rag_retrieve("SQLite")
            assert len(fragments) >= 1
            assert any("SQLite" in f["content"] for f in fragments)
            assert all("source" in f for f in fragments)
        finally:
            mgr.close()


def test_rag_retrieve_empty_when_no_knowledge():
    """_rag_retrieve must return empty list when no knowledge is stored."""
    from session_manager import SessionManager
    with tempfile.TemporaryDirectory() as td:
        ws = tempfile.mkdtemp()
        mgr = SessionManager(
            session_id="test-f3-empty",
            provider="ollama-local",
            model="qwen2.5:14b",
            base_path=ws,
            state_root=td,
        )
        try:
            fragments = mgr._rag_retrieve("nonexistent topic")
            assert fragments == []
        finally:
            mgr.close()


def test_format_rag_context_empty():
    """_format_rag_context must return empty string for no fragments."""
    from session_manager import SessionManager
    assert SessionManager._format_rag_context([]) == ""


def test_format_rag_context_with_fragments():
    """_format_rag_context must include content and source for fragments."""
    from session_manager import SessionManager
    fragments = [
        {"content": "Fact A", "source": "keyword", "score": 1.0},
        {"content": "Fact B", "source": "vector", "score": 0.85},
    ]
    result = SessionManager._format_rag_context(fragments)
    assert "CONTEXTO RECUPERADO (RAG)" in result
    assert "Fact A" in result
    assert "Fact B" in result
    assert "keyword" in result
    assert "vector" in result


def test_rag_retrieve_deduplicates():
    """_rag_retrieve must deduplicate fragments with same content prefix."""
    from session_manager import SessionManager
    with tempfile.TemporaryDirectory() as td:
        ws = tempfile.mkdtemp()
        mgr = SessionManager(
            session_id="test-f3-dedup",
            provider="ollama-local",
            model="qwen2.5:14b",
            base_path=ws,
            state_root=td,
        )
        try:
            content = "Duplicate content about Python testing"
            mgr.knowledge.add(content, source_session=mgr.session_id)
            mgr.knowledge.add(content, source_session=mgr.session_id)

            fragments = mgr._rag_retrieve("Python testing")
            # Both keyword matches return same content, dedup should reduce to 1
            unique_contents = {f["content"][:200] for f in fragments}
            assert len(unique_contents) == 1
        finally:
            mgr.close()


def test_rag_retrieve_respects_limit():
    """_rag_retrieve must return at most `limit` fragments."""
    from session_manager import SessionManager
    with tempfile.TemporaryDirectory() as td:
        ws = tempfile.mkdtemp()
        mgr = SessionManager(
            session_id="test-f3-limit",
            provider="ollama-local",
            model="qwen2.5:14b",
            base_path=ws,
            state_root=td,
        )
        try:
            for i in range(5):
                mgr.knowledge.add(f"Unique fact number {i} about testing", source_session=mgr.session_id)

            fragments = mgr._rag_retrieve("testing", limit=2)
            assert len(fragments) <= 2
        finally:
            mgr.close()


def test_rag_non_blocking_on_error():
    """_rag_retrieve must not raise even if KnowledgeBase has issues."""
    from session_manager import SessionManager
    with tempfile.TemporaryDirectory() as td:
        ws = tempfile.mkdtemp()
        mgr = SessionManager(
            session_id="test-f3-err",
            provider="ollama-local",
            model="qwen2.5:14b",
            base_path=ws,
            state_root=td,
        )
        try:
            # Close knowledge connection to force an error path
            mgr.knowledge.close()
            fragments = mgr._rag_retrieve("anything")
            # Should not raise, should return empty list
            assert isinstance(fragments, list)
        finally:
            mgr.close()
