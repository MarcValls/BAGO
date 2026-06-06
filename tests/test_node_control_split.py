"""Tests for FASE 7 node_control.py split into state + connect sub-facades.

Cubre R10 (cobertura de tests para node_control_state.py y
node_control_connect.py) y R5 (no-duplicación de constantes entre
state y connect). El facade node_control.py solo reexporta.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from argparse import Namespace
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = ["python", "-m", "bago_core.launcher"]


def _run_node(*args: str) -> tuple[int, str, str]:
    result = subprocess.run(
        [*LAUNCHER, "node", *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.returncode, result.stdout, result.stderr


def _import_subfaccades():
    import bago_core.node_control as facade
    import bago_core.node_control_state as state
    import bago_core.node_control_connect as connect

    return facade, state, connect


# ---------------------------------------------------------------------------
# R0: el facade ya no contiene logica -- solo reexports.
# ---------------------------------------------------------------------------
def test_facade_is_thin() -> None:
    facade, state, connect = _import_subfaccades()
    # <250 lineas segun R3.
    facade_lines = len(Path(facade.__file__).read_text(encoding="utf-8").splitlines())
    assert facade_lines < 250, f"facade has {facade_lines} lines, expected <250"
    # run_modular_guard vive en state; el facade solo lo expone como alias
    # legacy ``_run_modular_guard`` (R9) -- el nombre ``run_modular_guard``
    # no se reexporta.
    assert getattr(facade, "_run_modular_guard", None) is not None
    assert getattr(facade, "run_modular_guard", None) is None
    # Los nombres de logica viven en state o connect, no en facade.
    for business_name in ("_load_state", "_persist_state"):
        # Esta permitido reexportar (estado: importado), pero la definicion
        # NO debe estar en el facade.
        assert getattr(facade, business_name, None) is not None, business_name
    # Definiciones de connect/disconnect viven en connect, no en facade.
    assert connect.connect.__module__ == "bago_core.node_control_connect"
    assert connect.disconnect.__module__ == "bago_core.node_control_connect"
    assert connect.set_mode.__module__ == "bago_core.node_control_connect"
    assert connect.export_bundle.__module__ == "bago_core.node_control_connect"


def test_ssot_mode_tables_in_policy() -> None:
    """R5: ``_MODE_SYNC`` y ``_MODE_VISIBILITY`` son SSoT de policy, no de connect.

    El connect side consume ``policy_dict_for_mode`` para construir la
    policy del connector; las tablas literales viven en
    ``node_control_policy`` y NO se duplican en ``node_control_connect``.
    """
    import bago_core.node_control_policy as policy
    import bago_core.node_control_connect as connect

    # Las tablas SSoT viven en policy (son _MODE_SYNC / _MODE_VISIBILITY).
    assert hasattr(policy, "_MODE_SYNC")
    assert hasattr(policy, "_MODE_VISIBILITY")
    assert policy.policy_dict_for_mode("connected") == {
        "can_execute": True,
        "can_modify": False,
        "sync_mode": "pull",
        "visibility": "visible",
    }
    assert policy.policy_dict_for_mode("writable overlay") == {
        "can_execute": True,
        "can_modify": True,
        "sync_mode": "overlay",
        "visibility": "overlay",
    }
    assert policy.policy_dict_for_mode("locked") == {
        "can_execute": False,
        "can_modify": False,
        "sync_mode": "deny",
        "visibility": "hidden",
    }
    # En connect, los literales NO deben existir: solo se importa
    # ``policy_dict_for_mode`` y se reusa. La regla R5 mira el codigo
    # ejecutable, no la docstring; comprobamos que NO se asignan los
    # literales (en ningun sitio del archivo, incluyendo comentarios).
    import ast
    tree = ast.parse(Path(connect.__file__).read_text(encoding="utf-8"))
    literal_ids: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    literal_ids.add(target.id)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            literal_ids.add(node.name)
    assert "_MODE_SYNC" not in literal_ids
    assert "_MODE_VISIBILITY" not in literal_ids
    assert "_policy_dict_for_mode" not in literal_ids


# ---------------------------------------------------------------------------
# R1/R2: state solo importa de store/policy/ssot; connect solo de state/policy/store.
# ---------------------------------------------------------------------------
def test_state_imports_clean() -> None:
    import bago_core.node_control_state as state
    src = Path(state.__file__).read_text(encoding="utf-8")
    # No debe importar de facade (R1: no ciclos)
    assert "from bago_core import node_control" not in src
    assert "from bago_core.node_control import" not in src
    # No debe importar de connect (state es solo lectura)
    assert "from bago_core.node_control_connect" not in src


def test_connect_imports_clean() -> None:
    import bago_core.node_control_connect as connect
    src = Path(connect.__file__).read_text(encoding="utf-8")
    # connect depende de state (write-through) y policy (find_*)
    assert "from bago_core.node_control_state" in src
    # No debe reimportar facade (sin ciclos)
    assert "from bago_core import node_control" not in src
    assert "from bago_core.node_control import" not in src


# ---------------------------------------------------------------------------
# Estado puro: status/bootstrap/list_pieces/matrix/validate en state module.
# ---------------------------------------------------------------------------
def test_state_module_exposes_pure_helpers() -> None:
    import bago_core.node_control_state as state
    for name in (
        "bootstrap", "status", "list_pieces", "list_connectors",
        "matrix", "evidence_tail", "preview_mutation", "validate", "run_modular_guard",
    ):
        assert callable(getattr(state, name)), name


def test_state_validate_against_tempdir() -> None:
    import bago_core.node_control_state as state
    with tempfile.TemporaryDirectory() as td:
        ok, payload = state.validate(td)
        assert ok is True, payload
        names = {c["name"] for c in payload["checks"]}
        assert "installations_present" in names
        assert "modular_guard" in names


# ---------------------------------------------------------------------------
# Live side-effects: connect/disconnect/set_mode/export_bundle en connect module.
# ---------------------------------------------------------------------------
def test_connect_module_exposes_mutators() -> None:
    import bago_core.node_control_connect as connect
    for name in ("connect", "disconnect", "set_mode", "export_bundle"):
        assert callable(getattr(connect, name)), name


def test_connect_set_mode_roundtrip_in_tempdir() -> None:
    import bago_core.node_control_connect as connect
    import bago_core.node_control_state as state
    with tempfile.TemporaryDirectory() as td:
        boot = state.bootstrap(td)
        installation = boot["state"]["installations"][0]
        piece = boot["state"]["pieces"][0]
        result = connect.connect(
            td, installation["installation_id"], piece["piece_id"], "shadow"
        )
        assert result["connector"]["mode"] == "shadow"
        # Set_mode with detached -> disconnect
        out = connect.set_mode(
            td, installation["installation_id"], piece["piece_id"], "detached"
        )
        assert out["connector"]["mode"] == "detached"
        # Set_mode back to connected
        out2 = connect.set_mode(
            td, installation["installation_id"], piece["piece_id"], "connected"
        )
        assert out2["connector"]["mode"] == "connected"


def test_preview_and_evidence_tail_in_tempdir() -> None:
    import bago_core.node_control_state as state
    with tempfile.TemporaryDirectory() as td:
        boot = state.bootstrap(td)
        installation = boot["state"]["installations"][0]
        piece = boot["state"]["pieces"][0]
        preview = state.preview_mutation(
            td, installation["installation_id"], piece["piece_id"], "overlay"
        )
        assert preview["ok"] is True
        assert preview["proposed"]["mode"] == "writable overlay"
        assert "enables_modification" in preview["warnings"]
        ok, _payload = state.validate(td)
        assert ok is True
        evidence = state.evidence_tail(td, 5)
        assert evidence["count"] >= 1
        assert evidence["entries"][0]["action"] == "validate"


def test_matrix_distinguishes_available_from_detached() -> None:
    import bago_core.node_control_state as state
    from bago_core.node_control_store import json_write
    with tempfile.TemporaryDirectory() as td:
        boot = state.bootstrap(td)
        paths = boot["paths"]
        state_data = boot["state"]
        removed = state_data["connectors"].pop()
        json_write(paths.connectors, state_data["connectors"])
        matrix = state.matrix(td)
        row = next(item for item in matrix["rows"] if item["piece_id"] == removed["piece_id"])
        cell = next(
            item for item in row["cells"]
            if item["installation_id"] == removed["installation_id"]
        )
        assert cell["created"] is False
        assert cell["state"] == "not-created"
        assert cell["mode"] == "available"


def test_export_bundle_in_tempdir() -> None:
    import bago_core.node_control_connect as connect
    with tempfile.TemporaryDirectory() as td:
        out_path = connect.export_bundle(td)
        assert out_path.exists()
        payload = json.loads(out_path.read_text(encoding="utf-8"))
        assert "state" in payload
        assert "installations" in payload["state"]
        assert "connectors" in payload["state"]


# ---------------------------------------------------------------------------
# CLI: node validate sigue funcionando end-to-end (R9 backwards compat).
# ---------------------------------------------------------------------------
def test_cli_status_json() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "bago_core.node_control", "status", "--json"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["installations"] >= 1
    assert payload["pieces"] >= 1


def test_launcher_node_status_json_matches_electron_command() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "bago_core.launcher", "node", "status", "--json"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["installations"] >= 1
    assert payload["pieces"] >= 1


def test_launcher_forwards_node_mutation_arguments() -> None:
    from bago_core import launcher
    args = Namespace(
        json=True,
        base_path=None,
        node_cmd="set-mode",
        installation="inst-1",
        piece="piece-1",
        mode="shadow",
        output="",
        limit=None,
        type="",
        scope="",
    )
    with mock.patch("bago_core.node_control.main", return_value=0) as delegated:
        assert launcher.cmd_node(args) == 0
    forwarded = delegated.call_args.args[0]
    assert "--installation" in forwarded
    assert forwarded[forwarded.index("--installation") + 1] == "inst-1"
    assert "--piece" in forwarded
    assert forwarded[forwarded.index("--piece") + 1] == "piece-1"
    assert "--mode" in forwarded
    assert forwarded[forwarded.index("--mode") + 1] == "shadow"


def test_launcher_node_mutation_roundtrip_in_tempdir() -> None:
    import bago_core.node_control_state as state
    with tempfile.TemporaryDirectory() as td:
        boot = state.bootstrap(td)
        installation = boot["state"]["installations"][0]["installation_id"]
        piece = boot["state"]["pieces"][0]["piece_id"]
        result = subprocess.run(
            [
                sys.executable, "-m", "bago_core.launcher", "node",
                "--base-path", td,
                "set-mode",
                "--installation", installation,
                "--piece", piece,
                "--mode", "shadow",
                "--json",
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["connector"]["mode"] == "shadow"


def test_cli_validate_passes() -> None:
    rc, out, _ = _run_node("validate")
    assert rc == 0, out
    assert "[OK] modular_guard" in out


def test_cli_matrix_renders() -> None:
    rc, out, _ = _run_node("matrix")
    assert rc == 0, out
    assert "BAGO MATRIX" in out
