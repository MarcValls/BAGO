#!/usr/bin/env python3
"""

_CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo
evidence_bundle.py — BAGO 4.1.5 Contract Evidence Generator

Genera bundles de evidencia verificables para los contratos v4.
El modo simulated usa un adapter mock, pero ejecuta el runtime real
de SessionManager, comandos REPL, persistencia y KnowledgeBase.
El modo real usa el provider/configuración activos y exige respuesta viva.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BAGO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BAGO_ROOT / ".bago" / "core"))
sys.path.insert(0, str(BAGO_ROOT / ".bago" / "chat"))

from commands import execute
from provider_adapter import HealthStatus, ModelInfo, ProviderAdapter, ProviderResponse, TokenUsage
from session_manager import ADAPTER_REGISTRY, SessionManager
from switch_engine import SwitchEngine


@dataclass(frozen=True)
class ObjectiveProfile:
    objective_id: str
    title: str
    summary: str
    user_prompt: str
    plan_task: str
    knowledge_entry: str
    knowledge_query: str
    real_prompt: str


PROFILES: dict[str, ObjectiveProfile] = {
    "community-knowledge": ObjectiveProfile(
        objective_id="community-knowledge",
        title="Asistencia comunitaria basada en conocimiento abierto",
        summary=(
            "Demuestra que BAGO v4 puede asistir al usuario de forma directa "
            "con una respuesta útil y de forma indirecta preservando conocimiento, "
            "planificación y estado reproducible."
        ),
        user_prompt=(
            "Resume en dos frases como BAGO v4 puede ayudar a una comunidad abierta "
            "a convertir conocimiento disperso en acciones útiles para el usuario."
        ),
        plan_task=(
            "publicar una mejora pequena y verificable de conocimiento comunitario "
            "para que otro usuario la pueda reutilizar"
        ),
        knowledge_entry=(
            "BAGO v4 debe convertir una conversacion util en conocimiento recuperable "
            "y en un artefacto verificable para la comunidad."
        ),
        knowledge_query="conocimiento recuperable",
        real_prompt=(
            "En dos frases, explica como puedes asistir a un usuario mientras dejas "
            "una huella reutilizable para la comunidad."
        ),
    ),
}


class ContractMockAdapter(ProviderAdapter):
    """Adapter local para generar evidencia simulada usando el runtime real."""

    MODEL_ID = "contract-assistant-v1"

    def __init__(self, config: dict | None = None):
        super().__init__("mock-contract", config)

    def chat(
        self,
        messages: list[dict],
        model: str,
        *,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
        tools: list[dict] | None = None,
    ) -> ProviderResponse:
        last_user = ""
        for message in reversed(messages):
            if message.get("role") == "user":
                last_user = str(message.get("content", ""))
                break

        content = self._respond(last_user)
        tokens_in = max(len(last_user) // 4, 1)
        tokens_out = max(len(content) // 4, 1)
        return ProviderResponse(
            content=content,
            model_used=model or self.MODEL_ID,
            provider=self.provider_name,
            finish_reason="stop",
            usage=TokenUsage(
                input_tokens=tokens_in,
                output_tokens=tokens_out,
                total_tokens=tokens_in + tokens_out,
            ),
        )

    def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(
                model_id=self.MODEL_ID,
                wire_name=self.MODEL_ID,
                provider=self.provider_name,
                context_tokens=32768,
                max_output_tokens=4096,
                best_for="contract_validation",
                cost="free/local",
            )
        ]

    def health_check(self, timeout: float = 5.0) -> HealthStatus:
        return HealthStatus(
            ok=True,
            provider=self.provider_name,
            detail="Mock contract runtime ready",
            latency_ms=1.0,
            models_available=1,
        )

    def is_configured(self) -> bool:
        return True

    def supports_tools(self) -> bool:
        return False

    def supports_streaming(self) -> bool:
        return True

    @staticmethod
    def _respond(prompt: str) -> str:
        normalized = prompt.lower().strip()
        if normalized.startswith("genera un plan paso a paso conciso"):
            return "\n".join([
                "1. Definir una necesidad concreta que ayude al usuario.",
                "2. Convertir la necesidad en una mejora pequena y verificable.",
                "3. Registrar el aprendizaje como conocimiento recuperable.",
                "4. Guardar la sesion y publicar la evidencia reutilizable.",
            ])
        if normalized.startswith("ejecuta este paso del plan:"):
            return "Paso ejecutado en modo simulado con trazabilidad reproducible."
        return (
            "BAGO v4 puede responder a una necesidad concreta del usuario y, al mismo tiempo, "
            "guardar el aprendizaje como conocimiento reutilizable para la comunidad. "
            "La evidencia valida que la ayuda ofrecida puede repetirse y auditarse."
        )


@contextmanager
def _registered_mock_adapter():
    previous = ADAPTER_REGISTRY.get("mock-contract")
    ADAPTER_REGISTRY["mock-contract"] = ContractMockAdapter
    try:
        yield
    finally:
        if previous is None:
            ADAPTER_REGISTRY.pop("mock-contract", None)
        else:
            ADAPTER_REGISTRY["mock-contract"] = previous


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_if_exists(source: Path, target: Path) -> None:
    if source.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _sanitize_result(result: dict[str, Any]) -> dict[str, Any]:
    clean = {
        "ok": bool(result.get("ok")),
        "message": str(result.get("message", "")),
    }
    if "action" in result:
        clean["action"] = result["action"]
    return clean


def _prepare_output_dir(output_dir: Path, overwrite: bool) -> None:
    if output_dir.exists():
        if not overwrite:
            raise FileExistsError(f"El directorio ya existe: {output_dir}")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def _copy_session_artifacts(base_path: Path, session_id: str, output_dir: Path) -> list[str]:
    state_dir = base_path / ".bago" / "state" / "sessions"
    session_dir = state_dir / session_id
    copied: list[str] = []

    for name in ("context.jsonl", "timeline.jsonl", "tokens.json", "meta.json"):
        source = session_dir / name
        target = output_dir / "session" / name
        if source.exists():
            _copy_if_exists(source, target)
            copied.append(str(target.relative_to(output_dir)).replace("/", "\\"))

    session_meta = state_dir / f"{session_id}.json"
    if session_meta.exists():
        target = output_dir / "session" / "session.json"
        _copy_if_exists(session_meta, target)
        copied.append(str(target.relative_to(output_dir)).replace("/", "\\"))

    return copied


def _collect_file_digests(output_dir: Path) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for path in sorted(output_dir.rglob("*")):
        if path.is_file():
            relative = str(path.relative_to(output_dir)).replace("/", "\\")
            files.append({
                "path": relative,
                "sha256": _sha256(path),
                "size_bytes": path.stat().st_size,
            })
    return files


def _write_checksums(output_dir: Path, files: list[dict[str, Any]]) -> None:
    lines = [f"{entry['sha256']} *{entry['path']}" for entry in files if entry["path"] != "checksums.sha256"]
    _write_text(output_dir / "checksums.sha256", "\n".join(lines) + ("\n" if lines else ""))


def _build_report(
    *,
    mode: str,
    profile: ObjectiveProfile,
    provider: str,
    model: str,
    session_id: str,
    checks: list[dict[str, str]],
    commands: dict[str, dict[str, Any]],
    response_text: str,
    plan_text: str,
    output_dir: Path,
) -> str:
    lines = [
        f"# Bundle de evidencia — {profile.title}",
        "",
        f"- **Modo:** `{mode}`",
        f"- **Objetivo:** `{profile.objective_id}`",
        f"- **Provider/modelo:** `{provider}/{model}`",
        f"- **Session ID:** `{session_id}`",
        f"- **Generado en:** `{output_dir}`",
        "",
        "## Resultado directo al usuario",
        "",
        response_text.strip(),
        "",
    ]
    if plan_text:
        lines.extend([
            "## Plan generado",
            "",
            "```text",
            plan_text.strip(),
            "```",
            "",
        ])

    lines.extend([
        "## Comprobaciones demostrables",
        "",
    ])
    for check in checks:
        lines.append(f"- **{check['id']}**: {check['status']} — {check['detail']}")

    lines.extend([
        "",
        "## Comandos capturados",
        "",
    ])
    for name, result in commands.items():
        lines.extend([
            f"### {name}",
            "",
            "```text",
            result.get("message", "").strip(),
            "```",
            "",
        ])

    return "\n".join(lines).rstrip() + "\n"


def _validation_commands(mode: str, objective: str, output_dir: Path, provider: str, model: str) -> list[str]:
    commands = [
        "python test_e2e.py",
        "python bago_core\\cli.py evidence --test",
    ]
    if mode == "simulated":
        commands.append(
            f'python bago_core\\cli.py evidence --mode simulated --objective {objective} --output "{output_dir}" --overwrite'
        )
    else:
        commands.append(
            f'python bago_core\\cli.py evidence --mode real --provider {provider} --model "{model}" --output "{output_dir}" --overwrite'
        )
    return commands


def _generate_bundle_with_manager(
    *,
    mgr: SessionManager,
    mode: str,
    profile: ObjectiveProfile,
    output_dir: Path,
    workspace_path: Path,
) -> Path:
    engine = SwitchEngine(mgr.adapters)

    direct_response = mgr.send(profile.user_prompt if mode == "simulated" else profile.real_prompt)
    if not direct_response.strip():
        raise RuntimeError("La respuesta del provider esta vacia.")

    status_result = _sanitize_result(execute("/status", mgr, engine))
    memory_add_result = _sanitize_result(execute(f"/memory add {profile.knowledge_entry}", mgr, engine))
    memory_search_result = _sanitize_result(execute(f"/memory search {profile.knowledge_query}", mgr, engine))
    save_result: dict[str, Any] | None = None

    plan_text = ""
    if mode == "simulated":
        plan_result = execute(f"/plan {profile.plan_task}", mgr, engine)
        plan_view = _sanitize_result(plan_result)
        commands = {
            "/status": status_result,
            "/plan": plan_view,
            "/memory add": memory_add_result,
            "/memory search": memory_search_result,
        }
        plan_text = plan_view["message"]
        good_result = _sanitize_result(execute("/good", mgr, engine))
        commands["/good"] = good_result
    else:
        commands = {
            "/status": status_result,
            "/memory add": memory_add_result,
            "/memory search": memory_search_result,
        }

    save_result = _sanitize_result(execute("/save", mgr, engine))
    commands["/save"] = save_result

    recent_memories = mgr.knowledge.list_recent(limit=5)
    exported_memory = [
        item for item in recent_memories
        if profile.knowledge_query.lower() in item["content"].lower()
        or profile.knowledge_entry.lower() in item["content"].lower()
    ]

    _write_json(output_dir / "objective.json", {
        "objective_id": profile.objective_id,
        "title": profile.title,
        "summary": profile.summary,
        "mode": mode,
        "recorded_at": _now_iso(),
    })
    _write_text(output_dir / "assistant_response.txt", direct_response.strip() + "\n")
    if plan_text:
        _write_text(output_dir / "plan.txt", plan_text.strip() + "\n")
    _write_json(output_dir / "commands" / "results.json", commands)
    _write_json(output_dir / "knowledge" / "recent_memories.json", exported_memory)

    copied_artifacts = _copy_session_artifacts(workspace_path, mgr.session_id, output_dir)

    checks: list[dict[str, str]] = [
        {
            "id": "session-runtime",
            "status": "pass" if copied_artifacts else "fail",
            "detail": "La sesion genero artefactos persistentes en context.jsonl/timeline/tokens/meta.",
        },
        {
            "id": "direct-assistance",
            "status": "pass" if direct_response.strip() else "fail",
            "detail": "Existe una respuesta util al objetivo planteado por el usuario.",
        },
        {
            "id": "knowledge-persistence",
            "status": "pass" if exported_memory else "fail",
            "detail": "La evidencia incluye conocimiento recuperable derivado de la sesion.",
        },
        {
            "id": "session-save",
            "status": "pass" if (output_dir / "session" / "session.json").exists() else "fail",
            "detail": "La sesion se guardo en disco con metadatos de continuidad.",
        },
    ]
    if mode == "simulated":
        checks.append({
            "id": "plan-generation",
            "status": "pass" if plan_text.strip() else "fail",
            "detail": "El runtime genero un plan reutilizable desde el parser REPL real.",
        })
    else:
        checks.insert(0, {
            "id": "live-provider-health",
            "status": "pass" if mgr.status()["health"]["ok"] else "fail",
            "detail": "El provider real respondio con salud positiva antes de cerrar el bundle.",
        })

    manifest = {
        "bundle_id": f"bago.v4.evidence.{mode}.{profile.objective_id}",
        "contract_version": "4.1.5",
        "related_to": [
            "docs\\contracts\\bago_v4_runtime_contract.json",
            "docs\\contracts\\bago_v4_repl_contract.md",
            "docs\\contracts\\bago_v4_evidence_contract.md",
            "docs\\contracts\\bago_v4_knowledge_contract.md",
            "docs\\contracts\\bago_v4_governance_contract.md",
            "docs\\contracts\\bago_v4_engineering_contract.md",
        ],
        "summary": profile.summary,
        "details": {
            "mode": mode,
            "provider": mgr.provider,
            "model": mgr.model,
            "session_id": mgr.session_id,
            "state_root": ".bago\\state",
        },
        "status": "pass" if all(item["status"] == "pass" for item in checks) else "fail",
        "recorded_at": _now_iso(),
        "validation_commands": _validation_commands(mode, profile.objective_id, output_dir, mgr.provider, mgr.model),
        "checks": checks,
        "artifacts": copied_artifacts + [
            "assistant_response.txt",
            "commands\\results.json",
            "knowledge\\recent_memories.json",
            "objective.json",
        ] + (["plan.txt"] if plan_text else []),
    }

    _write_json(output_dir / "manifest.json", manifest)
    _write_text(
        output_dir / "report.md",
        _build_report(
            mode=mode,
            profile=profile,
            provider=mgr.provider,
            model=mgr.model,
            session_id=mgr.session_id,
            checks=checks,
            commands=commands,
            response_text=direct_response,
            plan_text=plan_text,
            output_dir=output_dir,
        ),
    )

    files = _collect_file_digests(output_dir)
    _write_checksums(output_dir, files)
    files = _collect_file_digests(output_dir)

    manifest["files"] = files
    _write_json(output_dir / "manifest.json", manifest)
    return output_dir / "manifest.json"


def generate_bundle(
    *,
    mode: str,
    objective: str,
    output_dir: Path,
    provider: str,
    model: str,
    base_path: Path,
    overwrite: bool,
) -> Path:
    profile = PROFILES[objective]
    _prepare_output_dir(output_dir, overwrite)

    if mode == "simulated":
        with tempfile.TemporaryDirectory() as temp_dir, _registered_mock_adapter():
            workspace_path = Path(temp_dir)
            mgr = SessionManager(
                base_path=str(workspace_path),
                provider="mock-contract",
                model=ContractMockAdapter.MODEL_ID,
            )
            try:
                return _generate_bundle_with_manager(
                    mgr=mgr,
                    mode=mode,
                    profile=profile,
                    output_dir=output_dir,
                    workspace_path=workspace_path,
                )
            finally:
                mgr.close()

    mgr = SessionManager(
        base_path=str(base_path),
        provider=provider,
        model=model,
    )
    try:
        health = mgr.status()["health"]
        if not health["ok"]:
            raise RuntimeError(f"Provider no saludable: {health['detail']}")
        return _generate_bundle_with_manager(
            mgr=mgr,
            mode=mode,
            profile=profile,
            output_dir=output_dir,
            workspace_path=base_path,
        )
    finally:
        mgr.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bago evidence",
        description="Genera bundles de evidencia verificables para los contratos de BAGO v4.",
    )
    parser.add_argument("--mode", choices=("simulated", "real"), default="simulated", help="Tipo de evidencia a generar")
    parser.add_argument("--objective", choices=sorted(PROFILES), default="community-knowledge", help="Objetivo demostrable")
    parser.add_argument("--output", help="Directorio de salida del bundle")
    parser.add_argument("--provider", default="ollama-local", help="Provider para modo real")
    parser.add_argument("--model", default="llama3.2:3b", help="Modelo para modo real")
    parser.add_argument("--base-path", default=str(BAGO_ROOT), help="Base path para config/estado en modo real")
    parser.add_argument("--overwrite", action="store_true", help="Sobrescribe el directorio de salida si existe")
    parser.add_argument("--test", action="store_true", help="Ejecuta la prueba interna del generador")
    return parser


def _run_tests() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "bundle"
        manifest_path = generate_bundle(
            mode="simulated",
            objective="community-knowledge",
            output_dir=output_dir,
            provider="mock-contract",
            model=ContractMockAdapter.MODEL_ID,
            base_path=BAGO_ROOT,
            overwrite=False,
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["status"] == "pass"
        assert any(item["id"] == "plan-generation" for item in manifest["checks"])
        assert (output_dir / "session" / "context.jsonl").exists()
        assert (output_dir / "commands" / "results.json").exists()
        assert (output_dir / "knowledge" / "recent_memories.json").exists()
        print("evidence_bundle.py --test: ALL PASS")
    return 0


def run(args: argparse.Namespace) -> int:
    if getattr(args, "test", False):
        return _run_tests()

    if not getattr(args, "output", None):
        print("Uso: bago evidence --output <directorio> [--mode simulated|real] [--objective ...]")
        return 1

    try:
        manifest_path = generate_bundle(
            mode=args.mode,
            objective=args.objective,
            output_dir=Path(args.output).resolve(),
            provider=args.provider,
            model=args.model,
            base_path=Path(args.base_path).resolve(),
            overwrite=bool(args.overwrite),
        )
    except Exception as exc:
        print(f"❌ No se pudo generar el bundle: {exc}")
        return 1

    print(f"✓ Bundle generado: {manifest_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
