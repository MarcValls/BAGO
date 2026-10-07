from __future__ import annotations

import json

from bago_core.launcher import main


def _run(root, *args):
    return main(["--base-path", str(root), "layer", "--root", str(root), *args])


def test_layer_cli_stale_rebase_and_receipt(tmp_path, capsys):
    assert _run(tmp_path, "init", "demo", "--content", '{"value":"canon"}') == 0
    assert _run(tmp_path, "propose", "demo", "FIX-A", "--payload", '{"value":"a"}') == 0
    assert _run(tmp_path, "authorize", "demo", "FIX-A") == 0
    assert _run(tmp_path, "apply", "demo", "FIX-A") == 0
    assert _run(tmp_path, "propose", "demo", "FIX-C", "--parent-id", "FIX-A", "--payload", '{"value":"c"}') == 0
    assert _run(tmp_path, "authorize", "demo", "FIX-C") == 0
    assert _run(tmp_path, "propose", "demo", "FIX-B", "--payload", '{"value":"b"}') == 0
    assert _run(tmp_path, "authorize", "demo", "FIX-B") == 0
    assert _run(tmp_path, "apply", "demo", "FIX-B") == 0
    assert _run(tmp_path, "apply", "demo", "FIX-C") == 2
    stale = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert stale["status"] == "STALE_PARENT"
    assert _run(tmp_path, "rebase", "demo", "FIX-C", "FIX-C-R1") == 0
    assert _run(tmp_path, "authorize", "demo", "FIX-C-R1") == 0
    assert _run(tmp_path, "apply", "demo", "FIX-C-R1") == 0
    receipt = json.loads(capsys.readouterr().out.strip().splitlines()[-1])["receipt"]
    assert receipt["status"] == "APPLIED"
    assert receipt["receipt_id"].startswith("sha256:")
    assert _run(tmp_path, "show", "demo") == 0
    state = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert state["head_id"] == "FIX-C-R1"
    assert state["layers"]["FIX-C"]["state"] == "STALE"


def test_layer_cli_projection_requires_explicit_write_and_exact_head(tmp_path, capsys):
    assert _run(tmp_path, "init", "projection", "--content", '{"value":"canon"}') == 0
    assert _run(tmp_path, "propose", "projection", "FIX-A", "--payload", '{"value":"a"}') == 0
    assert _run(tmp_path, "authorize", "projection", "FIX-A") == 0
    assert _run(tmp_path, "apply", "projection", "FIX-A") == 0
    state = json.loads((tmp_path / ".bago" / "layers" / "state.json").read_text(encoding="utf-8"))
    head_digest = state["artifacts"]["projection"]["head_digest"]
    assert _run(tmp_path, "project", "projection", "view.json", "--expected-head-digest", head_digest) == 0
    preview = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert preview["status"] == "PREVIEW"
    assert not (tmp_path / ".bago" / "layers" / "projections" / "view.json").exists()
    assert _run(tmp_path, "project", "projection", "view.json", "--expected-head-digest", "bad", "--allow-write") == 2
    stale = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert stale["status"] == "STALE_PARENT"
    import argparse
    import importlib
    cmd_layer_module = importlib.import_module("bago_core.commands.cmd_layer")

    def fake_execute(request, *, confirmation_text, manager):
        path = tmp_path / ".bago" / "layers" / "projections" / "view.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.loads(request.arguments["content"]) and request.arguments["content"], encoding="utf-8")
        assert request.effect_id == "state.write"
        assert request.source_surface == "cli.layer.project"
        return {"ok": True, "receipt": {"effect_id": request.effect_id}}

    monkeypatch = __import__("pytest").MonkeyPatch()
    monkeypatch.setattr(cmd_layer_module.cli_execution, "execute_cli_effect", fake_execute)
    assert cmd_layer_module.cmd_layer(argparse.Namespace(
        root=str(tmp_path), layer_cmd="project", artifact_id="projection", target="view.json",
        expected_head_digest=head_digest, allow_write=True,
    )) == 0
    result = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert result["status"] == "APPLIED"
    assert result["receipt"]["operation"] == "EXPORT_PROJECTION"
    assert json.loads((tmp_path / ".bago" / "layers" / "projections" / "view.json").read_text(encoding="utf-8"))["content"]["value"] == "a"
    monkeypatch.undo()
