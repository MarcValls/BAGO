from __future__ import annotations

import importlib

from bago_core.parsers import build_parser
from bago_core.commands import cmd_tools


def test_c11_autopilot_stops_at_twenty_and_keeps_remainder_pending():
    from bago_core.resolver import add_piece_paths

    add_piece_paths("core.package", "chat.package")
    commands = importlib.import_module("commands")
    from plan_engine import PlanEngine

    engine = PlanEngine()

    class Manager:
        plan_engine = engine

        def __init__(self):
            self.calls = 0

        def send(self, _prompt):
            self.calls += 1
            if self.calls == 1:
                return "\n".join(f"{index}. Execute capability step number {index}" for index in range(1, 26))
            return "step response"

    manager = Manager()
    result = commands.cmd_autopilot(manager, None, ["bounded task"])

    assert manager.calls == 21  # one plan request plus twenty execution requests
    assert sum(step.status == "done" for step in result["plan"].steps) == 20
    assert sum(step.status == "pending" for step in result["plan"].steps) == 5
    assert result["plan"].status == "stopped"
    assert "quedan 5 pasos pendientes" in result["message"]


def test_c12_persistent_agent_lifecycle_uses_one_registry(tmp_path, monkeypatch, capsys):
    from bago_core.resolver import add_piece_paths

    add_piece_paths("tools.package")
    spiral = importlib.import_module("spiral_agent")
    monkeypatch.setattr(cmd_tools, "_load_tool_module", lambda *_args: spiral)
    parser = build_parser("test", str(tmp_path), "", "")

    def run_cli(*argv):
        return cmd_tools.cmd_agent(parser.parse_args(["agent", "--root", str(tmp_path), *argv]))

    assert run_cli("spawn", "cap-probe") == 0
    assert run_cli("list") == 0
    assert "cap-probe" in capsys.readouterr().out
    assert run_cli("run", "cap-probe") == 0
    registry = spiral.load_json(tmp_path / ".bago/state/agents_registry.json", {})
    assert registry["cap-probe"]["active"] is True
    state = spiral.load_json(tmp_path / ".bago/state/agents/cap-probe/state.json", {})
    assert state["cycles"] == 1
    assert run_cli("kill", "cap-probe") == 0
    assert spiral.agent_from_registry("cap-probe") is None


def test_c12_agent_pack_routes_to_portable_catalog(tmp_path, monkeypatch):
    calls = []

    class Kit:
        @staticmethod
        def main(argv):
            calls.append(argv)
            return 0

    from bago_core import resolver

    monkeypatch.setattr(resolver, "load_module_from_path", lambda *_args: Kit)
    parser = build_parser("test", str(tmp_path), "", "")
    args = parser.parse_args(["agent", "pack", "list", "--json"])

    assert cmd_tools.cmd_agent(args) == 0
    assert calls == [["list", "--json"]]
