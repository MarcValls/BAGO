"""Contract boundary for the future non-mutating ``bago verify`` runner."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / ".bago" / "contracts" / "bago.verify.run.v1.schema.json"


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _conditional_for(schema: dict, property_name: str, expected: str) -> dict:
    for branch in schema.get("allOf", []):
        properties = branch.get("if", {}).get("properties", {})
        if properties.get(property_name, {}).get("properties", {}).get("status", {}).get("const") == expected:
            return branch
    raise AssertionError(f"Missing conditional for {property_name}.status={expected}")


def test_verify_run_schema_declares_the_immutable_identity_boundary() -> None:
    schema = _schema()
    assert schema["$id"].endswith("bago.verify.run.v1.schema.json")
    assert schema["properties"]["schema_version"]["const"] == "bago.verify.run.v1"
    assert {"run_id", "profile", "identity", "integrity", "checks", "summary", "artifacts"} <= set(schema["required"])

    identity = schema["$defs"]["identity"]
    assert {
        "repo_root", "framework_root", "workspace_root", "git_head", "git_branch", "git_dirty",
        "worktree_fingerprint", "release_version", "os", "python", "node", "npm",
    } <= set(identity["required"])
    assert identity["properties"]["git_dirty"]["type"] == "boolean"


def test_dirty_is_observed_but_not_an_integrity_invalidator_by_schema() -> None:
    schema = _schema()
    identity = schema["$defs"]["identity"]
    assert identity["properties"]["git_dirty"] == {"type": "boolean"}
    assert "git_dirty" not in json.dumps(schema["allOf"])


def test_invalidated_run_must_be_incomplete() -> None:
    schema = _schema()
    branch = _conditional_for(schema, "integrity", "INVALIDATED")
    assert branch["then"]["properties"]["summary"]["properties"]["verdict"]["const"] == "INCOMPLETE"


def test_check_results_and_evidence_rule_are_closed() -> None:
    schema = _schema()
    check = schema["$defs"]["check"]
    assert check["properties"]["result"]["enum"] == ["PASS", "FAIL", "BLOCKED", "SKIPPED", "NOT_RUN"]
    pass_rule = check["allOf"][0]["then"]["properties"]
    assert pass_rule["evidence_valid"]["const"] is True
    assert pass_rule["evidence"]["minItems"] == 1
    assert {"path", "sha256", "candidate_sha"} <= set(schema["$defs"]["evidence"]["required"])


def test_verdict_and_artifact_authority_are_separate_from_project_lifecycle() -> None:
    schema = _schema()
    assert schema["properties"]["summary"]["properties"]["verdict"]["enum"] == ["VERIFIED", "FAILED", "INCOMPLETE"]
    artifacts = schema["properties"]["artifacts"]
    assert artifacts["required"] == ["sha256sums", "entries"]
    assert artifacts["properties"]["sha256sums"]["const"] == "SHA256SUMS"
    assert "PROJECT_STATE" not in json.dumps(schema)
