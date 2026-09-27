"""Request builder for the strong CLI evidence bundle effect."""
from __future__ import annotations

import os
import sys
from pathlib import Path

_CORE_ROOT = Path(__file__).resolve().parents[1] / ".bago" / "core"
if str(_CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(_CORE_ROOT))

from execution_adapters.evidence_bundle import EvidenceBundleGenerateEffectAdapter
from execution_request import build_execution_request
from bago_core.cli_execution import execute_cli_effect


def generate_bundle(
    *, mode: str, objective: str, output_dir: Path, provider: str, model: str,
    base_path: Path, overwrite: bool,
) -> Path:
    target = Path(output_dir).expanduser()
    if not target.is_absolute():
        target = Path.cwd() / target
    target = Path(os.path.abspath(str(target)))
    expected_prior = EvidenceBundleGenerateEffectAdapter.target_fingerprint(target)
    request = build_execution_request(
        effect_id="evidence.bundle.generate",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id=f"evidence-bundle:{target}",
        source_surface="cli.evidence_bundle.generate",
        target={"path": str(target), "expected_prior_sha256": expected_prior},
        arguments={
            "mode": str(mode), "objective": str(objective),
            "provider": str(provider), "model": str(model),
            "base_path": str(Path(base_path).expanduser().resolve()),
            "overwrite": bool(overwrite),
        },
        scope="workspace",
    )
    result, _authorization = execute_cli_effect(
        request,
        confirmation_text=(
            f"Generar bundle de evidencia en {target}"
            + (" reemplazando su contenido actual" if overwrite else "")
        ),
    )
    return Path(str(result["manifest_path"]))
