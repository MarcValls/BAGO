from __future__ import annotations

from unittest.mock import Mock

from tool_registry import ToolCall, ToolRegistry, ToolResult


def test_model_tool_schema_excludes_mutating_and_unclassified_tools() -> None:
    registry = ToolRegistry()
    names = {item["function"]["name"] for item in registry.to_openai()}

    assert "file-read" in names
    assert "file-edit" not in names
    assert "file-write" not in names
    assert "project-scaffold" not in names
    assert "issues-take" not in names
    assert "auto-heal" not in names


def test_mutating_model_tool_is_blocked_before_subprocess() -> None:
    registry = ToolRegistry()
    registry.execute_call = Mock()

    result = registry.execute_model_call(
        ToolCall(call_id="call-1", name="file-write", arguments={"path": "note.txt", "content": "x"})
    )

    assert result.ok is False
    assert result.blocked is True
    assert result.block_reason == "model_tool_effect_unbound"
    registry.execute_call.assert_not_called()


def test_normalized_read_only_model_tool_reaches_registry_execution() -> None:
    registry = ToolRegistry()
    expected = ToolResult(call_id="call-1", name="file-read", content="ok")
    registry.execute_call = Mock(return_value=expected)
    call = ToolCall(call_id="call-1", name="file-read", arguments={"path": "note.txt"})

    assert registry.execute_model_call(call) is expected
    registry.execute_call.assert_called_once_with(call)
