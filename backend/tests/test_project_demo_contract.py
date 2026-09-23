from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


API = Path(__file__).resolve().parents[1] / ".bago" / "api"
sys.path.insert(0, str(API))
SPEC = importlib.util.spec_from_file_location("handlers_project_demo_test", API / "handlers_project.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def _capture(monkeypatch, tmp_path: Path):
    auth = importlib.import_module("authorization_boundary")
    serializers = importlib.import_module("api_serializers")
    responses: list[tuple[int, dict]] = []
    manager = SimpleNamespace(
        session_id="project-demo-session",
        project_root=tmp_path.resolve(),
    )
    handler = SimpleNamespace(headers={"X-Bago-Channel": "ui-react"})
    monkeypatch.setattr(MODULE, "_mgr", lambda _handler: manager)
    authorization_root = tmp_path.parent / f".{tmp_path.name}-authorization"
    monkeypatch.setattr(auth, "state_root", lambda: authorization_root)
    monkeypatch.setattr(
        serializers,
        "send_json",
        lambda _handler, status, payload: responses.append((status, payload)),
    )
    return handler, responses


def _approve_demo(monkeypatch, tmp_path: Path, root: Path):
    handler, responses = _capture(monkeypatch, tmp_path)
    common = {
        "root": str(root),
        "interaction_id": "project-demo-interaction",
    }
    MODULE.handle_project_demo(handler, {**common, "authorization_action": "challenge"})
    challenge = responses[-1][1]["authorization"]["challenge"]
    assert not root.exists()

    MODULE.handle_project_demo(handler, {
        **common,
        "authorization_action": "approve",
        "challenge_id": challenge["challenge_id"],
        "user_decision": "approve",
    })
    permit = responses[-1][1]["authorization"]["permit"]["token"]
    assert not root.exists()
    return handler, responses, common, permit


def test_demo_project_has_no_side_effect_before_approval_and_executes_afterward(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "BAGO-Demo"
    handler, responses, common, permit = _approve_demo(monkeypatch, tmp_path, root)

    MODULE.handle_project_demo(handler, {
        **common,
        "authorization_action": "execute",
        "authorization_permit": permit,
    })

    assert responses[-1][0] == 201
    assert responses[-1][1]["data"]["template"] == "bago-demo-v1"
    assert responses[-1][1]["receipt"]["effect_id"] == "project.write"
    assert (root / "package.json").is_file()
    assert (root / "src" / "app.js").read_text(encoding="utf-8").strip()


def test_demo_project_rejects_target_tamper_before_first_gateway_write(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "BAGO-Demo"
    handler, responses, common, permit = _approve_demo(monkeypatch, tmp_path, root)
    root.mkdir()
    keep = root / "keep.txt"
    keep.write_text("user data", encoding="utf-8")

    MODULE.handle_project_demo(handler, {
        **common,
        "authorization_action": "execute",
        "authorization_permit": permit,
    })

    assert responses[-1][0] == 409
    assert responses[-1][1]["code"] == "authorization_operation_mismatch"
    assert keep.read_text(encoding="utf-8") == "user data"
    assert not (root / "package.json").exists()


def _execute_project_action(monkeypatch, tmp_path: Path, action: str) -> tuple[list[tuple[int, dict]], Path]:
    handler, responses = _capture(monkeypatch, tmp_path)
    root = tmp_path.resolve()
    common = {
        "root": str(root),
        "interaction_id": f"project-{action}-interaction",
    }
    endpoint = getattr(MODULE, f"handle_project_{action}")
    before = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))
    endpoint(handler, {**common, "authorization_action": "challenge"})
    challenge = responses[-1][1]["authorization"]["challenge"]
    assert sorted(path.relative_to(root).as_posix() for path in root.rglob("*")) == before
    endpoint(handler, {
        **common,
        "authorization_action": "approve",
        "challenge_id": challenge["challenge_id"],
        "user_decision": "approve",
    })
    permit = responses[-1][1]["authorization"]["permit"]["token"]
    assert sorted(path.relative_to(root).as_posix() for path in root.rglob("*")) == before
    endpoint(handler, {
        **common,
        "authorization_action": "execute",
        "authorization_permit": permit,
    })
    return responses, root


def test_project_init_http_runtime_executes_through_gateway(monkeypatch, tmp_path: Path) -> None:
    responses, root = _execute_project_action(monkeypatch, tmp_path, "init")

    assert responses[-1][0] == 200
    assert responses[-1][1]["receipt"]["effect_id"] == "project.write"
    assert (root / ".bago" / "pack.json").is_file()


def test_project_link_http_runtime_executes_through_gateway(monkeypatch, tmp_path: Path) -> None:
    project_memory = importlib.import_module("project_memory")
    project_memory.init_project(tmp_path)
    responses, root = _execute_project_action(monkeypatch, tmp_path, "link")

    assert responses[-1][0] == 200
    assert responses[-1][1]["receipt"]["operation"] == "link"
    assert (root / ".bago" / "link.json").is_file()


def test_project_seed_http_runtime_executes_through_gateway(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# demo\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("def main():\n    return 1\n", encoding="utf-8")
    responses, root = _execute_project_action(monkeypatch, tmp_path, "seed")

    assert responses[-1][0] == 200
    assert responses[-1][1]["receipt"]["operation"] == "seed"
    assert (root / ".gabo" / "seed.meta.json").is_file()
