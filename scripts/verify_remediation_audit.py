#!/usr/bin/env python3
"""Independently verify a BAGO remediation evidence bundle.

The verification report is written next to the ZIP, never inside it, so the
package hash remains immutable and can be checked by a third party.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MANIFEST = "MANIFEST.sha256.json"
SESSION_PATTERNS = ("pi-session-", "session-export", "session_export")


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(data: bytes, name: str) -> dict[str, Any]:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"JSON inválido: {name}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"objeto JSON requerido: {name}")
    return value


def verify_sidecar(package: Path) -> str:
    sidecar = package.with_suffix(package.suffix + ".sha256")
    if not sidecar.is_file():
        raise ValueError(f"sidecar ausente: {sidecar}")
    parts = sidecar.read_text(encoding="utf-8").strip().split()
    digest = sha_file(package)
    if len(parts) != 2 or parts[0].casefold() != digest or parts[1] != package.name:
        raise ValueError("el sidecar SHA-256 no coincide con el ZIP")
    return digest


def verify_manifest(archive: zipfile.ZipFile) -> dict[str, bytes]:
    names = archive.namelist()
    if len(names) != len(set(names)) or MANIFEST not in names:
        raise ValueError("manifest ausente o entradas ZIP duplicadas")
    for name in names:
        normalized = name.replace("\\", "/").casefold()
        if name.startswith("/") or ".." in Path(name).parts:
            raise ValueError(f"ruta ZIP insegura: {name}")
        if normalized.endswith(".html") and any(token in normalized for token in SESSION_PATTERNS):
            raise ValueError(f"exportación de sesión prohibida: {name}")
    manifest = load_json(archive.read(MANIFEST), MANIFEST)
    rows = manifest.get("files")
    if not isinstance(rows, list):
        raise ValueError("lista files ausente en manifest")
    expected_names = set(names) - {MANIFEST}
    listed: dict[str, bytes] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("fila inválida en manifest")
        name = str(row.get("path", ""))
        if name in listed or name not in expected_names:
            raise ValueError(f"entrada de manifest duplicada o inexistente: {name}")
        data = archive.read(name)
        if row.get("size") != len(data) or str(row.get("sha256", "")).casefold() != sha_bytes(data):
            raise ValueError(f"hash/tamaño no coincide: {name}")
        listed[name] = data
    if set(listed) != expected_names:
        missing = sorted(expected_names - set(listed))
        raise ValueError(f"entradas no cubiertas por manifest: {missing}")
    return listed


def verify_provenance(files: dict[str, bytes]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for label in ("bago", "gestor"):
        name = f"audit/{label}-provenance.json"
        payload = load_json(files[name], name)
        for field in ("baseline_sha", "candidate_sha"):
            if len(str(payload.get(field, ""))) != 40:
                raise ValueError(f"{name}: {field} no es SHA completo")
        if payload.get("dirty") is not False:
            raise ValueError(f"{name}: candidato sucio")
        if not payload.get("branch") or not payload.get("remote_status"):
            raise ValueError(f"{name}: identidad incompleta")
        result[label] = payload
    source = load_json(files["audit/source-audit/provenance.json"], "source audit provenance")
    if source.get("session_html") != "excluded" or source.get("normalized_patch_apply_check") != "PASS":
        raise ValueError("la procedencia del audit original no demuestra saneamiento/aplicación")
    raw_name = "audit/source-audit/original-git-diff.patch"
    lf_name = "audit/source-audit/original-git-diff.lf.patch"
    if source.get("original_patch_raw_sha256") != sha_bytes(files[raw_name]):
        raise ValueError("hash del patch original no coincide")
    if source.get("normalized_patch_sha256") != sha_bytes(files[lf_name]):
        raise ValueError("hash del patch LF original no coincide")
    return result


def verify_gate_receipts(files: dict[str, bytes], provenance: dict[str, dict[str, Any]]) -> list[str]:
    contract = load_json(files["audit/bundle-contract.json"], "bundle contract")
    required = contract.get("required_gates")
    if not isinstance(required, list) or not required or len(required) != len(set(required)):
        raise ValueError("registro de gates requerido ausente o inválido")
    validated: list[str] = []
    known_candidates = {
        str(Path(data["path_at_capture"]).resolve()).casefold(): data["candidate_sha"]
        for data in provenance.values()
    }
    prefix = "audit/raw-gate-logs/"
    for gate in required:
        name = f"{prefix}{gate}.json"
        payload = load_json(files[name], name)
        if payload.get("contract") != "bago.gate-evidence.v1" or payload.get("exit_code") != 0:
            raise ValueError(f"gate no satisfactorio: {gate}")
        if payload.get("candidate_stable") is not True:
            raise ValueError(f"candidato inestable durante gate: {gate}")
        before = payload.get("candidate_repositories_before")
        after = payload.get("candidate_repositories_after")
        if not isinstance(before, dict) or before != after or not before:
            raise ValueError(f"repositorios del gate no son estables: {gate}")
        for repo_path, candidate in after.items():
            if not isinstance(candidate, dict) or candidate.get("dirty") is not False:
                raise ValueError(f"repositorio sucio en gate {gate}: {repo_path}")
            expected_sha = known_candidates.get(str(Path(repo_path).resolve()).casefold())
            if not expected_sha or candidate.get("sha") != expected_sha:
                raise ValueError(f"SHA/repositorio no ligado al paquete en gate {gate}: {repo_path}")
        runtime = payload.get("runtime")
        if not isinstance(runtime, dict) or not all(runtime.get(key) for key in ("python", "python_executable", "platform")):
            raise ValueError(f"runtime incompleto: {gate}")
        if not payload.get("command") or not payload.get("started_at") or not payload.get("finished_at"):
            raise ValueError(f"comando/timestamps ausentes: {gate}")
        for stream in ("stdout", "stderr"):
            log_name = f"{prefix}{payload.get(stream, '')}"
            if log_name not in files or payload.get(f"{stream}_sha256") != sha_bytes(files[log_name]):
                raise ValueError(f"log {stream} no coincide: {gate}")
        validated.append(str(gate))
    return validated


def apply_patch(baseline: Path, patch: Path) -> None:
    result = subprocess.run(["git", "apply", "--check", str(patch)], cwd=baseline, capture_output=True)
    if result.returncode != 0:
        raise ValueError(result.stderr.decode("utf-8", "replace") or f"patch no aplicable: {patch.name}")


def verify_patches(package: Path) -> list[str]:
    checked: list[str] = []
    with tempfile.TemporaryDirectory(prefix="bago-audit-verify-") as td:
        target = Path(td)
        with zipfile.ZipFile(package) as archive:
            archive.extractall(target)
        pairs = (
            ("bago-baseline-git", "audit/bago-git-diff.patch"),
            ("gestor-baseline-git", "audit/gestor-git-diff.patch"),
            ("bago-baseline-git", "audit/source-audit/original-git-diff.lf.patch"),
        )
        for baseline, relative_patch in pairs:
            apply_patch(target / baseline, target / relative_patch)
            checked.append(relative_patch)
    return checked


def verify(package: Path) -> dict[str, Any]:
    package_sha = verify_sidecar(package)
    with zipfile.ZipFile(package) as archive:
        files = verify_manifest(archive)
    provenance = verify_provenance(files)
    gates = verify_gate_receipts(files, provenance)
    patches = verify_patches(package)
    return {
        "contract": "bago.third-party-remediation-verification.v1",
        "package": package.name,
        "package_sha256": package_sha,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "manifest_entries": len(files),
        "gates": gates,
        "patches": patches,
        "session_exports": "excluded",
        "result": "PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", nargs="?", default="output/BAGO-remediation-audit.zip")
    parser.add_argument("--report", default="")
    args = parser.parse_args()
    package = Path(args.package).resolve()
    report = Path(args.report).resolve() if args.report else package.with_suffix(package.suffix + ".verification.json")
    try:
        result = verify(package)
    except (KeyError, OSError, ValueError, zipfile.BadZipFile) as exc:
        print(json.dumps({"result": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({**result, "report": str(report)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
