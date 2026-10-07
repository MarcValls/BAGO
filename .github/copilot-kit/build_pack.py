"""Build a reviewed-source snapshot without activating any integration."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ALLOWED = {".py", ".md", ".json", ".mjs", ".cmd", ".ps1", ".psm1", ".toml",
           ".yaml", ".yml", ".txt", ".cjs", ".js", ".ts"}
SKIP = {"__pycache__", "node_modules", ".git", "state", "state.example",
        "evidence", "logs", "sessions", "context", "knowledge"}
GROUPS = {
    "01-copilot": [".github/agents", ".github/skills", ".github/prompts",
                   ".github/instructions", ".github/copilot-instructions.md"],
    "02-framework": [
        f"backend/.bago/{name}" for name in
        ("agents", "roles", "prompts", "workflows", "templates", "tools",
         "contracts", "core", "api", "chat", "providers", "integrations",
         "bin")
    ] + ["backend/.bago/tools.manifest.json"],
    "03-integrations-review": ["backend/.bago/mcp", "backend/.bago/extensions",
                               ".github/hooks", ".github/plugin",
                               "plugins/bago-github-admin"],
    "04-other-harnesses": [".codex/agents", ".codex/bago-workpack",
                           ".codex/bago-remediation", ".agents/skills",
                           ".pi/prompts", ".pi/extensions"],
    "05-continuity-reference": [".bago/bin"],
    "06-documentation": [".github/copilot-kit", "LICENSE"],
}
SECRET = re.compile(
    rb"(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,}|"
    rb"AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    rb"\r?\n[A-Za-z0-9+/=]{32,})"
)
SYNTHETIC_CANARY_VALUES = {
    b"AKIA" + b"FAKE123456789012",
    b"ghp_" + b"FAKEGitHubTokenValue123456789012345678",
}
LIVE_FILES = {
    "backend/.bago/node_control/installations.json",
    "backend/.bago/node_control/connectors.json",
    "backend/.bago/node_control/pieces.json",
    "backend/.bago/node_control/compatibility.json",
    "backend/.bago/node_control/evidence.jsonl",
}
LIVE_PREFIXES = {"backend/.bago/node_control", "backend/.bago/runtime", ".gabo/copilot"}

def is_live_source(relative: str) -> bool:
    return relative in LIVE_FILES or any(
        relative == prefix or relative.startswith(prefix + "/")
        for prefix in LIVE_PREFIXES
    )


def has_secret_pattern(data: bytes, source: str) -> bool:
    canary_source = source in {
        "backend/.bago/core/execution_adapters/canary.py",
        "backend/.bago/tools/bago_canary.py",
    }
    return any(not (canary_source and match.group() in SYNTHETIC_CANARY_VALUES)
               for match in SECRET.finditer(data))


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def meaning(path: str) -> str:
    name = path.lower()
    if any(word in name for word in ("verifier", "verify", "evidence", "validat")):
        return "Verificacion y evidencia"
    if any(word in name for word in ("audit", "scan", "check", "doctor", "detector")):
        return "Evaluacion y diagnostico"
    if any(word in name for word in ("worker", "file_write", "file_edit", "auto_heal", "remediation")):
        return "Intervencion"
    if any(word in name for word in ("/mcp/", "/extensions/", "/hooks/", "/plugins/", "/plugin/")):
        return "Integracion y transporte"
    if any(word in name for word in ("instructions", "/contracts/", "protocol", "rules")):
        return "Autoridad y limites"
    if any(word in name for word in ("explorer", "mapper", "inventory", "read_", "git_context")):
        return "Observacion y conocimiento"
    if any(word in name for word in ("/roles/", "router", "orchestrator", "factory", "preflight", "/workflows/")):
        return "Coordinacion y preparacion"
    if "/templates/" in name or "build_pack" in name:
        return "Produccion de artefactos"
    if "/bin/bago.py" in name or "/runtime/" in name:
        return "Continuidad y runtime"
    return "Soporte y procedimiento"


def description(path: Path, text: str) -> tuple[str, int]:
    if path.suffix == ".py":
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return "Fuente Python; sintaxis pendiente de revision", 1
        doc = ast.get_docstring(tree)
        if doc:
            return doc.splitlines()[0][:220], tree.body[0].lineno
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                return f"Fuente Python; simbolo {node.name} (comportamiento no ejecutado)", node.lineno
    for number, line in enumerate(text.splitlines(), 1):
        if line.startswith("description:"):
            return line.partition(":")[2].strip().strip("'\"")[:220], number
    for number, line in enumerate(text.splitlines(), 1):
        if line.startswith("# "):
            return line[2:][:220], number
    return f"Fuente {path.suffix}; contenido de referencia", 1


def select_sources() -> list[tuple[str, Path]]:
    selected = []
    for group, roots in GROUPS.items():
        for relative in roots:
            source = ROOT / relative
            if not source.exists():
                raise FileNotFoundError(relative)
            files = [source] if source.is_file() else sorted(source.rglob("*"))
            for path in files:
                rel = path.relative_to(ROOT)
                if any(part in SKIP for part in rel.parts) or not path.is_file():
                    continue
                if (path.suffix not in ALLOWED and path.name != "LICENSE") or ".bak" in path.name or path.name.startswith(".env"):
                    continue
                if is_live_source(rel.as_posix()):
                    continue
                if "runtime" in rel.parts and path.suffix != ".py":
                    continue
                if group == "06-documentation" and path.name not in {
                    "README.md", "INTEGRATION_PLAN.md", "build_pack.py", "test_build_pack.py", "LICENSE"
                }:
                    continue
                if any((ROOT.joinpath(*rel.parts[:n])).is_symlink()
                       or (ROOT.joinpath(*rel.parts[:n])).is_junction()
                       for n in range(1, len(rel.parts) + 1)):
                    raise ValueError(f"Filesystem link rejected: {rel}")
                if group == "06-documentation":
                    archive = f"{group}/{path.name}"
                else:
                    archive = f"{group}/source/{rel.as_posix()}"
                selected.append((archive, path))
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    sidecar = output.with_suffix(output.suffix + ".sha256")
    if output.exists() or sidecar.exists():
        raise FileExistsError("Output ZIP or checksum already exists; choose a new path")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()
    manifest = json.loads((ROOT / "backend/.bago/tools.manifest.json").read_text(encoding="utf-8"))
    declared = {entry["file"]: entry for entry in manifest["tools"].values()}
    tool_sources = {p.name: p for p in (ROOT / "backend/.bago/tools").glob("*.py")}
    records, payload = [], {}
    for archive, path in select_sources():
        data = path.read_bytes()
        if has_secret_pattern(data, path.relative_to(ROOT).as_posix()):
            raise ValueError(f"Secret-pattern barrier triggered: {path.relative_to(ROOT)}")
        text = data.decode("utf-8-sig")
        summary, line = description(path, text)
        relative = path.relative_to(ROOT).as_posix()
        records.append({
            "source": relative, "archive": archive, "sha256": digest(data),
            "bytes": len(data), "meaning": meaning(relative),
            "description": summary, "evidence_line": line,
            "certainty": "HECHO: fuente presente; descripcion orientativa",
            "runtime_status": "NOT_RUN",
            "tool_manifest_declared": path.name in declared if path.parent.name == "tools" else None,
        })
        payload[archive] = data
    drift = {
        "declared_count": len(declared), "python_source_count": len(tool_sources),
        "undeclared_sources": sorted(tool_sources.keys() - declared.keys()),
        "missing_sources": sorted(declared.keys() - tool_sources.keys()),
        "hash_mismatches": sorted(
            name for name, entry in declared.items()
            if name in tool_sources and entry.get("sha256") != digest(tool_sources[name].read_bytes())
        ),
    }
    metadata = {
        "contract": "bago.copilot-kit.snapshot.v1", "created_utc": datetime.now(timezone.utc).isoformat(),
        "head": head, "branch": branch, "source": "current worktree, not HEAD-only",
        "pack_status": "PREPARED", "runtime_integration": "NOT_RUN",
        "source_file_count": len(records), "tool_manifest_drift": drift,
        "exclusions": sorted(SKIP) + sorted(LIVE_FILES) + sorted(LIVE_PREFIXES) + [
            "credentials", "backups", "historical payloads", "unselected backend",
            "runtime artifacts other than Python sources"],
        "files": records,
    }
    json_bytes = (json.dumps(metadata, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    payload["INVENTORY.json"] = json_bytes
    payload["SOURCE_MANIFEST.json"] = json_bytes
    lines = [
        "# Inventario granular BAGO Copilot CLI", "",
        f"HEAD: `{head}`. Fuentes del worktree actual; integracion runtime: NOT_RUN.", "",
        f"Archivos fuente: {len(records)}. Herramientas: {len(declared)} declaradas / {len(tool_sources)} fuentes Python.",
        "", "## Discrepancias del manifiesto", "",
        f"No declaradas: {', '.join(drift['undeclared_sources'])}.",
        f"Ausentes: {', '.join(drift['missing_sources']) or 'ninguna'}.",
        f"Hashes distintos del manifiesto: {', '.join(drift['hash_mismatches']) or 'ninguno'}.",
        "", "## Fuentes por seccion y significado", "",
        "| Seccion | Significado | Fuente y linea | Descripcion orientativa |",
        "|---|---|---|---|",
    ]
    for record in records:
        summary = record["description"].replace("|", "\\|").replace("\r", " ").replace("\n", " ")
        lines.append(f"| {record['archive'].split('/')[0]} | {record['meaning']} | "
                     f"`{record['source']}:{record['evidence_line']}` | {summary} |")
    payload["INVENTORY.md"] = ("\n".join(lines) + "\n").encode("utf-8")
    payload["README.md"] = (
        "# BAGO Copilot Kit\n\n"
        "Snapshot de fuentes ordenadas, sin instalacion ni activacion automatica.\n\n"
        "1. Leer `06-documentation/INTEGRATION_PLAN.md`.\n"
        "2. Consultar `INVENTORY.md` e `INVENTORY.json` (significado y evidencia).\n"
        "3. Comparar hashes de `SOURCE_MANIFEST.json` antes de adoptar piezas.\n\n"
        "Las secciones 01-05 conservan rutas originales dentro de `source`.\n"
        "Hooks, MCP, extensiones y plugin permanecen en 03-integrations-review.\n"
        "No copiar estado activo, instalar todo el arbol ni habilitar bash-runner.\n"
        "No es una distribucion completa del backend BAGO.\n"
    ).encode("utf-8")
    # Recheck every selected source before publishing the immutable snapshot.
    for record in records:
        if digest((ROOT / record["source"]).read_bytes()) != record["sha256"]:
            raise RuntimeError(f"Source changed during build: {record['source']}")
    if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() != head:
        raise RuntimeError("HEAD changed during build")
    checks = {
        "scope": "packaging only; no source capabilities executed",
        "source_hashes_rechecked": True, "head_stable": True,
        "secret_pattern_barrier": "PASS (limited patterns, not security certification)",
        "no_runtime_state_selected": True, "automatic_activation": False,
        "source_files": len(records),
    }
    payload["PACK_CHECKS.json"] = (json.dumps(checks, indent=2) + "\n").encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(payload.items()):
            archive.writestr(f"BAGO-copilot-kit/{name}", data)
    with zipfile.ZipFile(output) as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"Corrupt ZIP entry: {bad}")
        for name, data in payload.items():
            if archive.read(f"BAGO-copilot-kit/{name}") != data:
                raise RuntimeError(f"ZIP content mismatch: {name}")
    checksum = digest(output.read_bytes())
    with sidecar.open("x", encoding="ascii") as stream:
        stream.write(f"{checksum}  {output.name}\n")
    catalog = ROOT / ".github/copilot-kit"
    (catalog / "INVENTORY.md").write_bytes(payload["INVENTORY.md"])
    (catalog / "INVENTORY.json").write_bytes(payload["INVENTORY.json"])
    print(json.dumps({"zip": str(output), "sha256": checksum, "files": len(payload),
                      "tool_manifest_drift": drift}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
