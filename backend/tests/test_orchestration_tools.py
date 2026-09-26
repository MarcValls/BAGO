from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


TOOLS = Path(__file__).resolve().parents[1] / ".bago" / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


@pytest.fixture
def toolsmith(tmp_path):
    module = importlib.import_module("toolsmith")
    module.configure_paths(str(tmp_path))
    yield module
    module.configure_paths()


@pytest.fixture
def skill_engine(tmp_path):
    module = importlib.import_module("skill_engine")
    module.configure_paths(str(tmp_path))
    yield module
    module.configure_paths()


@pytest.fixture
def spiral_agent(tmp_path):
    module = importlib.import_module("spiral_agent")
    module.configure_paths(str(tmp_path))
    yield module
    module.configure_paths()


@pytest.fixture
def orchestrator_v4(tmp_path):
    module = importlib.import_module("orchestrator_v4")
    module.configure_paths(str(tmp_path))
    yield module
    module.configure_paths()


def test_toolsmith_assign_and_sprint_persist_to_configured_root(toolsmith, tmp_path):
    toolsmith.save_json(toolsmith.CATALOG_PATH, {
        "groups": {"analysis": ["inspector"], "build": ["builder"]},
        "tools": {"inspector": {"purpose": "inspect", "category": "analysis"}},
        "composites": {"analysis-stack": {"groups": ["analysis"]}},
        "task_routing": [{"keywords": ["debug"], "agent": "copilot", "composite": "analysis-stack"}],
        "agent_defaults": {"copilot": {"groups": ["analysis"]}, "codex": {"groups": ["build"]}},
    })

    toolbox = toolsmith.assign_toolbox("debug failing build", sprint="sprint-1")
    paths = toolsmith.assign_sprint("sprint-2", ["debug auth", "build release"])

    assert toolbox.agent == "copilot"
    assert [item.name for item in toolbox.tools] == ["inspector"]
    assert (tmp_path / ".bago/state/toolboxes/copilot-sprint-1.json").is_file()
    assert len(paths) == 2 and all(path.is_file() for path in paths)


def test_toolsmith_path_configuration_is_read_only(toolsmith, tmp_path):
    assert toolsmith._load_catalog() == {}
    assert not (tmp_path / ".bago").exists()


def test_toolsmith_toolbox_directory_is_materialized_by_state_writer(toolsmith, tmp_path, monkeypatch):
    writer = toolsmith.save_json
    observed = []

    def delegated_write(path, payload, indent=2):
        assert not Path(path).parent.exists()
        observed.append((Path(path), payload))
        return writer(path, payload, indent=indent)

    monkeypatch.setattr(toolsmith, "save_json", delegated_write)
    toolbox = toolsmith.assign_toolbox("inspect a workspace", sprint="sprint-gateway")

    expected = tmp_path / ".bago/state/toolboxes/copilot-sprint-gateway.json"
    assert observed and observed[0][0] == expected
    assert expected.is_file()
    assert toolbox.sprint == "sprint-gateway"


def test_skill_engine_run_persists_skill_state_in_configured_root(skill_engine, tmp_path):
    skill_engine.save_json(skill_engine.REGISTRY_FILE, {
        "probe": {"phase": 2, "steps": [0, 3, 4, 5, 8, 9, 10, 11], "category": "test"}
    })

    result = skill_engine.run_skill("probe")
    state = skill_engine._load_skill_state("probe")

    assert result.to_dict()["skill_id"] == "probe"
    assert len(state["cycles"]) == 1
    assert result.state_vector["phase"] == 2
    assert (tmp_path / ".bago/state/skills/probe_gradient.json").is_file()


def test_skill_engine_path_resolution_does_not_create_state(skill_engine, tmp_path):
    assert skill_engine._load_skill_state("absent")["cycles"] == []
    assert not (tmp_path / ".bago").exists()


def test_spiral_agent_run_records_skill_and_agent_state(spiral_agent, tmp_path):
    spiral_agent.save_json(spiral_agent.SKILL_REGISTRY, {
        "probe": {"phase": 1, "steps": [0, 3, 4, 5, 8, 9, 10, 11], "category": "test"}
    })
    assert spiral_agent._cmd_spawn(["alpha", "--phase", "3", "--skills", "probe"]) == 0

    agent = spiral_agent.agent_from_registry("alpha")
    result = agent.run()

    assert isinstance(result, spiral_agent.AgentResult)
    assert result.state_vector["last_step"] in spiral_agent.STEP_NAMES
    assert spiral_agent.load_json(spiral_agent.AGENTS_STATE_DIR / "alpha" / "state.json", {}).get("cycles") == 1
    assert any(item["id"] == "alpha" for item in spiral_agent.list_agents())
    assert (tmp_path / ".bago/state/agents/alpha/episodic.json").is_file()


@pytest.mark.parametrize("module_name", ["toolsmith", "skill_engine", "spiral_agent", "orchestrator_v4"])
def test_orchestration_tools_do_not_expose_destructive_selftest_cli(module_name, tmp_path):
    module = importlib.import_module(module_name)
    with pytest.raises(SystemExit) as raised:
        module.main(["--root", str(tmp_path), "--test"])
    assert raised.value.code == 2
    assert not (tmp_path / ".bago/state/_selftests").exists()


def test_orchestrator_v4_lifecycle_persists_only_under_configured_root(orchestrator_v4, tmp_path):
    module = orchestrator_v4
    brief = module.create_brief(task="Fix the broken API endpoint")
    assert module._brief_path(brief.id).is_file()
    assert brief.domain == "Backend"

    assigned = module.assign_brief(brief.id, agent="backend")
    assert assigned.status == "assigned" and assigned.agent == "backend"

    handoff = module.create_handoff(
        brief_id=brief.id,
        to_domain="Frontend",
        summary="Backend contract definido",
        state="completo",
    )
    updated = module._load_brief(brief.id)
    assert handoff.to_domain == "Frontend"
    assert updated.domain == "Frontend" and len(updated.handoffs) == 1

    updated.status = "in_progress"
    module._save_brief(updated)
    revision = module.review_brief(brief.id, notes="revisión focal")
    assert revision.result in {"approved", "changes_required"}
    if revision.result == "approved":
        assert module.close_brief(brief.id).status == "closed"

    assert module._list_briefs()
    assert all(path.is_file() for path in (tmp_path / ".bago/state/orchestrator").glob("*.json"))


def test_orchestrator_v4_cli_json_create_and_list(orchestrator_v4, tmp_path, capsys):
    module = orchestrator_v4

    assert module.main(["--root", str(tmp_path), "--json", "create", "--task", "CLI JSON task"]) == 0
    created = __import__("json").loads(capsys.readouterr().out)
    assert created["id"]

    assert module.main(["--root", str(tmp_path), "list"]) == 0
