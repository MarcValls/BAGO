from __future__ import annotations

import argparse
import json
from pathlib import Path

from bago_core.layered_artifact_engine import LayerError, LayerStore
from bago_core import cli_execution
from execution_request import build_execution_request


def _store(args: argparse.Namespace) -> LayerStore:
    root = Path(getattr(args, "root", "") or Path.cwd()) / ".bago" / "layers"
    return LayerStore(root)


def _payload(value: str) -> dict:
    data = json.loads(value)
    if not isinstance(data, dict):
        raise ValueError("payload must be a JSON object")
    return data


def cmd_layer(args: argparse.Namespace) -> int:
    try:
        store = _store(args)
        action = getattr(args, "layer_cmd", None)
        if action == "init":
            result = store.init_artifact(args.artifact_id, args.root_id, _payload(args.content))
        elif action == "propose":
            result = store.propose(args.artifact_id, args.layer_id, args.operation, _payload(args.payload), args.parent_id, args.parent_digest)
        elif action == "authorize":
            result = store.authorize(args.artifact_id, args.layer_id)
        elif action == "apply":
            result = store.apply(args.artifact_id, args.layer_id)
            result = {"status": result.status, "layer_id": result.layer_id, "receipt": result.receipt}
        elif action == "rebase":
            result = store.rebase(args.artifact_id, args.source_layer_id, args.new_layer_id)
        elif action == "show":
            result = store.show(args.artifact_id)
        elif action == "project":
            artifact = store.show(args.artifact_id)
            expected = args.expected_head_digest or artifact["head_digest"]
            writer = None
            if args.allow_write:
                def writer(path: Path, content: str):
                    request = build_execution_request(
                        effect_id="state.write",
                        actor_kind="user",
                        principal_id="interactive-local-user",
                        session_id=f"layer-projection:{args.artifact_id}",
                        source_surface="cli.layer.project",
                        target={"path": str(path), "allowed_root": str(store.root / "projections"), "operation": "replace_text"},
                        arguments={"content": content},
                        scope="session",
                        world_state_authority=Path(args.root or Path.cwd()),
                    )
                    return cli_execution.execute_cli_effect(
                        request,
                        confirmation_text=f"Proyectar snapshot LAE de {args.artifact_id} en {path}",
                        manager=Path(args.root or Path.cwd()),
                    )
            result = store.project(args.artifact_id, args.target, expected, allow_write=args.allow_write, writer=writer)
        else:
            raise ValueError("layer command required")
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=lambda value: value.__dict__))
        return 0 if not isinstance(result, dict) or result.get("status") not in {"STALE_PARENT", "NOT_AUTHORIZED"} else 2
    except (LayerError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=False))
        return 2
