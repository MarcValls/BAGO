from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]

from directory_context import DirectoryContextEngine, DirectoryScanner  # noqa: E402
import session_manager  # noqa: E402


class _DummyAdapter:
    def supports_tools(self) -> bool:
        return False

    def supports_streaming(self) -> bool:
        return False

    def supports_embeddings(self) -> bool:
        return False


def test_directory_scanner_excludes_generated_and_workspace_state(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "src").mkdir()
    (project / "src" / "app.py").write_text("def target_func():\n    return 1\n", encoding="utf-8")
    (project / "node_modules").mkdir()
    (project / "node_modules" / "ignored.js").write_text("export const bad = 1\n", encoding="utf-8")
    (project / ".gabo").mkdir()
    (project / ".gabo" / "state.json").write_text("{}", encoding="utf-8")

    records = DirectoryScanner(project).scan()
    paths = {record.path for record in records}

    assert "src/app.py" in paths
    assert "node_modules/ignored.js" not in paths
    assert ".gabo/state.json" not in paths


def test_directory_scanner_includes_framework_core_when_workspace_is_bago(tmp_path):
    project = tmp_path / "bago"
    (project / ".bago" / "core").mkdir(parents=True)
    (project / ".bago" / "core" / "session_manager.py").write_text("class SessionManager:\n    pass\n", encoding="utf-8")

    records = DirectoryScanner(project).scan()
    paths = {record.path for record in records}

    assert ".bago/core/session_manager.py" in paths


def test_directory_context_indexes_python_and_react_symbols(tmp_path):
    project = tmp_path / "project"
    context_root = project / ".gabo" / "context"
    (project / "src").mkdir(parents=True)
    (project / "tests").mkdir()
    (project / "README.md").write_text("# Demo Repo\n", encoding="utf-8")
    (project / "src" / "service.py").write_text(
        "import json\n\n"
        "class Service:\n"
        "    def target_method(self):\n"
        "        return json.dumps({'ok': True})\n\n"
        "def target_func():\n"
        "    return Service().target_method()\n",
        encoding="utf-8",
    )
    (project / "src" / "App.jsx").write_text(
        "import React from 'react';\n"
        "export function App() {\n"
        "  return <main>Hello</main>;\n"
        "}\n"
        "export const useThing = () => {\n"
        "  return 'thing';\n"
        "};\n",
        encoding="utf-8",
    )
    (project / "tests" / "test_service.py").write_text("from src.service import target_func\n", encoding="utf-8")

    engine = DirectoryContextEngine(project, context_root)
    snapshot = engine.build()
    symbols = {item["qualified_name"]: item for item in snapshot["symbols"]}

    assert "target_func" in symbols
    assert "Service.target_method" in symbols
    assert symbols["App"]["kind"] == "react_component"
    assert symbols["useThing"]["kind"] == "hook"
    assert (context_root / "repository_map.json").exists()
    assert (context_root / "repository_map.md").exists()


def test_hybrid_retriever_prefers_exact_symbol_and_records_reason(tmp_path):
    project = tmp_path / "project"
    context_root = project / ".gabo" / "context"
    (project / "src").mkdir(parents=True)
    (project / "src" / "service.py").write_text(
        "def target_func():\n"
        "    value = 41\n"
        "    return value + 1\n",
        encoding="utf-8",
    )
    (project / "src" / "other.py").write_text("def unrelated():\n    return 0\n", encoding="utf-8")

    engine = DirectoryContextEngine(project, context_root)
    engine.build()
    fragments, working_set = engine.retrieve("modifica target_func")

    assert fragments
    assert fragments[0]["symbol"] == "target_func"
    assert "target_func" in fragments[0]["content"]
    assert any("exact_symbol:target_func" in reason for reason in fragments[0]["reason"])
    assert working_set["files"] == ["src/service.py"]
    assert working_set["evidence"][0]["reason"]


def test_directory_watcher_refreshes_changed_file_incrementally(tmp_path):
    project = tmp_path / "project"
    context_root = project / ".gabo" / "context"
    (project / "src").mkdir(parents=True)
    a = project / "src" / "a.py"
    b = project / "src" / "b.py"
    a.write_text("def alpha():\n    return 1\n", encoding="utf-8")
    b.write_text("def beta():\n    return 2\n", encoding="utf-8")

    engine = DirectoryContextEngine(project, context_root)
    before = engine.build()
    before_hashes = {item["path"]: item["sha256"] for item in before["files"] if item["kind"] == "file"}

    a.write_text("def alpha():\n    return 10\n", encoding="utf-8")
    event = engine.watcher.refresh_changed_file("src/a.py")
    after = engine.load_snapshot()
    after_hashes = {item["path"]: item["sha256"] for item in after["files"] if item["kind"] == "file"}

    assert event["ok"] is True
    assert event["changed"] is True
    assert before_hashes["src/a.py"] != after_hashes["src/a.py"]
    assert before_hashes["src/b.py"] == after_hashes["src/b.py"]
    assert (context_root / "events.jsonl").exists()


def test_session_context_envelope_carries_directory_context_reasons(tmp_path, monkeypatch):
    project = tmp_path / "project"
    (project / "src").mkdir(parents=True)
    (project / "src" / "service.py").write_text(
        "def target_func():\n"
        "    return 42\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        session_manager.SessionManager,
        "_init_adapter",
        lambda self: setattr(self, "_adapter", _DummyAdapter()) or {"corrected": False, "requested": self.model, "actual": self.model, "available": []},
    )

    mgr = session_manager.SessionManager(base_path=str(project), state_root=str(tmp_path / "state"))
    try:
        fragments, code_context = mgr._workspace_context_pack("lee target_func")
        budget = SimpleNamespace(
            output_reserve=128,
            alert_level="GREEN",
            to_dict=lambda: {"available_tokens": 1000, "tokens_reserved": 128},
        )
        envelope = mgr._build_context_envelope(
            system_prompt="system",
            user_message="lee target_func",
            intent="review",
            normalized=[{"role": "user", "content": "lee target_func"}],
            tools=None,
            budget=budget,
            code_task=None,
            rag_fragments=fragments,
            code_context=code_context,
            streaming=False,
        )
    finally:
        mgr.close()

    assert envelope.files_represented == ["src/service.py"]
    assert envelope.retrieved_fragments[0]["source"] == "directory_context"
    assert envelope.retrieved_fragments[0]["reason"]
    assert envelope.session_summary["authorized_root"] == str(mgr.workspace_mirror_root)
    assert envelope.session_summary["workspace_state_root"].endswith(".gabo")
