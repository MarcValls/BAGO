#!/usr/bin/env python3
"""Create a governed, candidate-bound receipt for real provider evidence.

The command is deliberately non-mutating with respect to the repository: it
only reads Git and the two evidence bundles, then writes a receipt to the
explicit output directory.  A receipt is VERIFIED only when the checkout is
clean, start/end identity is equal, and both Codex and Copilot bundles carry
the same ``git_head`` and worktree fingerprint.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from bago_core.candidate_identity import fingerprint  # noqa: E402


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime(command: list[str]) -> str:
    executable = command[0]
    if os.name == "nt" and executable.lower() in {"node", "npm"}:
        executable += ".exe" if executable.lower() == "node" else ".cmd"
    if not shutil.which(executable):
        return "unavailable"
    try:
        result = subprocess.run([executable, *command[1:]], capture_output=True,
                                text=True, encoding="utf-8", errors="replace",
                                timeout=15)
    except (OSError, subprocess.SubprocessError):
        return "unavailable"
    return (result.stdout or result.stderr).strip() if result.returncode == 0 else "unavailable"


def _identity(repo: Path) -> dict[str, Any]:
    raw = fingerprint(repo)
    release_file = repo / "release_version.txt"
    release = release_file.read_text(encoding="utf-8").strip() if release_file.exists() else "unknown"
    return {
        "repo_root": str(raw["path"]),
        "framework_root": str(repo.resolve()),
        "workspace_root": str((repo / ".gabo").resolve()),
        "git_head": str(raw["sha"]),
        "git_branch": str(raw["branch"]),
        "git_dirty": bool(raw["dirty"]),
        "worktree_fingerprint": str(raw["worktree_sha256"]),
        "release_version": release,
        "os": {"system": platform.system(), "release": platform.release(), "machine": platform.machine()},
        "python": sys.version,
        "node": _runtime(["node", "--version"]),
        "npm": _runtime(["npm", "--version"]),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()



def _bundle_relative(path: str) -> str:
    return path.replace("\\", "/").lstrip("*/")


def _manifest_inventory(data: dict[str, Any]) -> set[str]:
    inventory: set[str] = set()
    files = data.get("files")
    if isinstance(files, list):
        for item in files:
            if isinstance(item, dict) and isinstance(item.get("path"), str):
                inventory.add(_bundle_relative(item["path"]))
            elif isinstance(item, str):
                inventory.add(_bundle_relative(item))
    artifacts = data.get("artifacts")
    if not inventory and isinstance(artifacts, list):
        inventory = {_bundle_relative(item) for item in artifacts if isinstance(item, str)}
    return inventory


def _parse_checksums(checksums_path: Path) -> tuple[dict[str, str], list[str]]:
    checksums: dict[str, str] = {}
    reasons: list[str] = []
    for line in checksums_path.read_text(encoding="utf-8").splitlines():
        parts = line.split(None, 1)
        if len(parts) != 2:
            reasons.append(f"línea de checksum inválida: {line!r}")
            continue
        expected, relative = parts
        checksums[_bundle_relative(relative)] = expected.lower()
    return checksums, reasons


def _reject_unignored_repo_output(repo: Path, output: Path) -> None:
    repo_root = Path(fingerprint(repo)["path"]).resolve()
    try:
        relative = output.resolve().relative_to(repo_root)
    except ValueError:
        return
    if relative == Path("."):
        raise ValueError("--output no puede apuntar a la raíz del repositorio")
    probe = relative.as_posix()
    result = subprocess.run(
        ["git", "check-ignore", "-q", probe],
        cwd=repo_root, capture_output=True,
    )
    if result.returncode != 0:
        raise ValueError(
            "--output dentro del repositorio debe estar cubierto por .gitignore para no invalidar el candidato"
        )


def _materialize_artifacts(output: Path, artifacts: list[dict[str, str]]) -> list[dict[str, str]]:
    materialized: list[dict[str, str]] = []
    for item in artifacts:
        provider = item["provider"]
        relative = _bundle_relative(item["bundle_path"])
        target = output / "providers" / provider / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(item["path"]), target)
        materialized.append({
            "path": str(target),
            "sha256": item["sha256"],
            "candidate_sha": item["candidate_sha"],
            "provider": provider,
        })
    return materialized


def _verify_bundle(path: Path, provider: str, identity: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    reasons: list[str] = []
    artifacts: list[dict[str, str]] = []
    manifest_path = path / "manifest.json"
    checksums_path = path / "checksums.sha256"
    data: dict[str, Any] = {}
    if not manifest_path.is_file() or not checksums_path.is_file():
        reasons.append("manifest.json y checksums.sha256 son obligatorios")
    else:
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            checksums, checksum_reasons = _parse_checksums(checksums_path)
            reasons.extend(checksum_reasons)
            inventory = _manifest_inventory(data)
            expected_inventory = set(inventory)
            expected_inventory.add("manifest.json")
            missing = sorted(expected_inventory - set(checksums))
            unexpected = sorted(set(checksums) - expected_inventory)
            if not inventory:
                reasons.append("el manifest no declara inventario de archivos")
            if missing:
                reasons.append(f"faltan checksums declarados: {', '.join(missing)}")
            if unexpected:
                reasons.append(f"checksums no declarados por el manifest: {', '.join(unexpected)}")
            for relative, expected in checksums.items():
                target = (path / relative).resolve()
                try:
                    target.relative_to(path.resolve())
                except ValueError:
                    reasons.append(f"checksum fuera del bundle: {relative}")
                    continue
                if not target.is_file() or _sha256(target) != expected.lower():
                    reasons.append(f"digest divergente: {relative}")
                else:
                    artifacts.append({
                        "path": str(target), "sha256": expected.lower(),
                        "candidate_sha": identity["git_head"], "provider": provider,
                        "bundle_path": relative,
                    })
        except (OSError, json.JSONDecodeError) as exc:
            reasons.append(f"bundle ilegible: {exc}")
    details = data.get("details", {}) if isinstance(data, dict) else {}
    candidate = details.get("candidate_identity", {}) if isinstance(details, dict) else {}
    if data.get("status") != "pass":
        reasons.append("status del bundle no es pass")
    checks = data.get("checks", []) if isinstance(data, dict) else []
    if details.get("provider") != provider:
        reasons.append(f"provider esperado {provider}, observado {details.get('provider')!r}")
    if not isinstance(checks, list) or not checks:
        reasons.append("el manifest debe declarar checks no vacíos")
    elif not all(isinstance(item, dict) and item.get("status") == "pass" for item in checks):
        reasons.append("el bundle contiene checks no pass")
    for field in ("git_head", "worktree_fingerprint"):
        if candidate.get(field) != identity[field]:
            reasons.append(f"{field} no coincide con el candidato actual")
    if candidate.get("git_dirty") is not False:
        reasons.append("el bundle no declara worktree limpio")
    artifacts.extend([
        {
            "path": str(checksums_path.resolve()), "sha256": _sha256(checksums_path),
            "candidate_sha": identity["git_head"], "provider": provider,
            "bundle_path": "checksums.sha256",
        },
    ] if manifest_path.is_file() and checksums_path.is_file() else [])
    result = "PASS" if not reasons else "BLOCKED"
    return {
        "check_id": f"provider-{provider}-candidate-bound",
        "layer": "integrations",
        "required": True,
        "claim": f"La evidencia real de {provider} pertenece al candidato Git exacto.",
        "command": ["python", "-m", "bago_core.evidence_cli", "--mode", "real", "--provider", provider],
        "started_at": _now(), "finished_at": _now(), "duration_ms": 0,
        "exit_code": 0 if result == "PASS" else None,
        "result": result, "reason": "ok" if not reasons else "; ".join(reasons),
        "evidence": artifacts, "evidence_valid": bool(not reasons and artifacts),
    }, artifacts


def build_receipt(repo: Path, bundles: dict[str, Path], output: Path, profile: str = "standard") -> Path:
    started = _now()
    start_identity = _identity(repo)
    _reject_unignored_repo_output(repo, output)
    checks: list[dict[str, Any]] = []
    artifacts: list[dict[str, str]] = []
    preflight_checks = [{"check_id": "clean-worktree", "result": "PASS" if not start_identity["git_dirty"] else "BLOCKED",
                         "reason": "El candidato Git está limpio." if not start_identity["git_dirty"] else "El worktree tiene cambios; no se puede gobernar el receipt."}]
    for provider, bundle in bundles.items():
        check, bundle_artifacts = _verify_bundle(bundle.resolve(), provider, start_identity)
        checks.append(check)
        artifacts.extend(bundle_artifacts)
    output.mkdir(parents=True, exist_ok=True)
    materialized_artifacts = _materialize_artifacts(output, artifacts)
    end_identity = _identity(repo)
    identity_equal = start_identity == end_identity
    reasons = []
    if not identity_equal:
        reasons.append("la identidad Git cambió durante la captura")
    if start_identity["git_dirty"] or end_identity["git_dirty"]:
        reasons.append("el worktree no está limpio")
    preflight_result = "PASS" if not reasons and all(c["result"] == "PASS" for c in checks) else ("BLOCKED" if reasons else "FAIL")
    totals = {key: sum(1 for item in checks if item["result"] == key) for key in ("PASS", "FAIL", "BLOCKED", "SKIPPED", "NOT_RUN")}
    verdict = "VERIFIED" if preflight_result == "PASS" and all(c["result"] == "PASS" for c in checks) else ("FAILED" if any(c["result"] == "FAIL" for c in checks) else "INCOMPLETE")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    run_id = f"VERIFY-{stamp}-{uuid.uuid4().hex[:8]}"
    receipt = {
        "schema_version": "bago.verify.run.v1", "run_id": run_id, "profile": profile,
        "started_at": started, "finished_at": _now(),
        "identity": {"start": start_identity, "end": end_identity},
        "integrity": {"status": "VALID" if identity_equal and not reasons else "INVALIDATED",
                       "identity_equal": identity_equal, "invalidating_reasons": reasons},
        "preflight": {"result": preflight_result, "checks": preflight_checks},
        "checks": checks,
        "summary": {"totals": totals, "required_totals": totals, "verdict": verdict},
        "artifacts": {"sha256sums": "SHA256SUMS", "entries": materialized_artifacts},
    }
    receipt_path = output / "receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    lines = [f"{item['sha256']}  {Path(item['path']).resolve().relative_to(output.resolve()).as_posix()}" for item in materialized_artifacts]
    (output / "SHA256SUMS").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8", newline="\n")
    final_identity = _identity(repo)
    if final_identity != end_identity:
        final_reasons = [*reasons, "la identidad Git cambió después de escribir el receipt"]
        receipt["identity"]["end"] = final_identity
        receipt["integrity"] = {
            "status": "INVALIDATED",
            "identity_equal": False,
            "invalidating_reasons": final_reasons,
        }
        receipt["preflight"]["result"] = "BLOCKED"
        receipt["summary"]["verdict"] = "INCOMPLETE"
        receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        verdict = "INCOMPLETE"
    print(json.dumps({"receipt": str(receipt_path), "verdict": verdict, "git_head": start_identity["git_head"], "worktree_fingerprint": start_identity["worktree_fingerprint"]}))
    return receipt_path


def _bundle_map_from_args(args: argparse.Namespace) -> dict[str, Path]:
    bundles: dict[str, Path] = {}
    for provider, bundle in (("codex", getattr(args, "codex_bundle", None)), ("copilot", getattr(args, "copilot_bundle", None))):
        if bundle is not None:
            bundles[provider] = bundle.resolve()
    for entry in getattr(args, "provider_bundle", []) or []:
        provider, sep, bundle = entry.partition("=")
        if not sep or not provider or not bundle:
            raise ValueError(f"Formato inválido para --provider-bundle: {entry!r}; usa PROVIDER=PATH")
        bundles[provider.strip()] = Path(bundle.strip()).resolve()
    if not bundles:
        raise ValueError("Debe indicar al menos un bundle real con --codex-bundle, --copilot-bundle o --provider-bundle")
    return bundles


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-bundle", type=Path, help="Ruta del bundle real de codex")
    parser.add_argument("--copilot-bundle", type=Path, help="Ruta del bundle real de copilot")
    parser.add_argument("--provider-bundle", action="append", default=[], metavar="PROVIDER=PATH",
                        help="Bundle real de cualquier proveedor, por ejemplo --provider-bundle ollama-cloud=/ruta/bundle")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--profile", choices=("quick", "standard", "release"), default="standard")
    args = parser.parse_args(argv)
    try:
        bundles = _bundle_map_from_args(args)
        receipt = build_receipt(args.repo.resolve(), bundles, args.output.resolve(), args.profile)
    except ValueError as exc:
        parser.error(str(exc))
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    return 0 if payload["summary"]["verdict"] == "VERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
