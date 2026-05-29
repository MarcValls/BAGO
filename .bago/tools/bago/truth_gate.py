"""
BAGO Truth Gate
===============

Bloquea cierres de tarea sin trazabilidad:
claim -> command -> evidence -> conclusion.

Objetivo:
- No permitir "Task complete", "verificado", "hecho", "pasa", "no aparece",
  "sin regresiones" o "preexistente" sin evidencia reproducible.
- Convertir cada afirmación en un objeto auditable.
- Guardar evidencia en .bago/traces/*.jsonl.

Solo usa stdlib.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Literal, Optional
import hashlib
import json
import os
import re
import subprocess
import time
import uuid


ClaimKind = Literal[
    "code_change",
    "test_pass",
    "test_fail",
    "absence",
    "preexisting_failure",
    "task_complete",
    "generic",
]


ASSERTIVE_WORDS = (
    "hecho",
    "implementado",
    "corregido",
    "arreglado",
    "verificado",
    "validado",
    "pasa",
    "pasan",
    "sin regresiones",
    "no aparece",
    "no existe",
    "no se encontró",
    "preexistente",
    "ajeno a este trabajo",
    "todo lo que toqué",
    "task complete",
    "trabajo completado",
)

UNCERTAIN_WORDS_FOR_FINAL = (
    "probablemente",
    "parece",
    "creo que",
    "diría que",
    "supongo",
    "quizá",
    "tal vez",
    "puede que",
)


class TruthGateError(RuntimeError):
    """Error duro: una afirmación no cumple trazabilidad mínima."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _safe_tail(text: str, max_chars: int = 12_000) -> str:
    if text is None:
        return ""
    text = text.replace("\x00", "")
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def repo_root(start: Optional[Path] = None) -> Path:
    cur = (start or Path.cwd()).resolve()
    for p in [cur, *cur.parents]:
        if (p / ".git").exists() or (p / ".bago").exists():
            return p
    return cur


def trace_dir(root: Optional[Path] = None) -> Path:
    root = root or repo_root()
    d = root / ".bago" / "traces"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _session_id() -> str:
    sid = os.environ.get("BAGO_TRACE_SESSION")
    if sid:
        return sid
    sid = f"{int(time.time())}-{uuid.uuid4().hex[:8]}"
    os.environ["BAGO_TRACE_SESSION"] = sid
    return sid


def trace_path(root: Optional[Path] = None) -> Path:
    return trace_dir(root) / f"{_session_id()}.jsonl"


def append_record(record: dict, root: Optional[Path] = None) -> None:
    path = trace_path(root)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def load_records(root: Optional[Path] = None) -> list[dict]:
    path = trace_path(root)
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    kind: Literal["command"]
    command: str
    cwd: str
    purpose: str
    started_at: str
    ended_at: str
    returncode: int
    stdout_tail: str
    stderr_tail: str
    combined_sha256: str
    elapsed_seconds: float


@dataclass(frozen=True)
class Claim:
    claim_id: str
    kind: ClaimKind
    text: str
    conclusion: str
    evidence_ids: list[str]
    created_at: str


def run_command(
    command: str,
    *,
    cwd: Optional[str | Path] = None,
    purpose: str,
    timeout: int = 120,
    allow_fail: bool = False,
    root: Optional[str | Path] = None,
) -> Evidence:
    """
    Ejecuta un comando y registra evidencia.

    Si allow_fail=False, returncode != 0 levanta TruthGateError.
    Para registrar un fallo esperado/preexistente usa allow_fail=True, pero luego
    la claim debe declararse como test_fail o preexisting_failure.
    """
    root_path = Path(root).resolve() if root else repo_root(Path(cwd).resolve() if cwd else None)
    cwd_path = Path(cwd).resolve() if cwd else root_path

    started = utc_now()
    t0 = time.time()
    proc = subprocess.run(
        command,
        cwd=str(cwd_path),
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    elapsed = time.time() - t0
    ended = utc_now()

    stdout_tail = _safe_tail(proc.stdout)
    stderr_tail = _safe_tail(proc.stderr)
    combined = f"$ {command}\n# cwd={cwd_path}\n# rc={proc.returncode}\n{proc.stdout}\n{proc.stderr}"

    ev = Evidence(
        evidence_id=f"ev_{uuid.uuid4().hex[:12]}",
        kind="command",
        command=command,
        cwd=str(cwd_path),
        purpose=purpose,
        started_at=started,
        ended_at=ended,
        returncode=proc.returncode,
        stdout_tail=stdout_tail,
        stderr_tail=stderr_tail,
        combined_sha256=sha256_text(combined),
        elapsed_seconds=round(elapsed, 3),
    )
    append_record({"type": "evidence", **asdict(ev)}, root_path)

    if proc.returncode != 0 and not allow_fail:
        raise TruthGateError(
            f"Comando falló sin allow_fail=True: {command}\n"
            f"rc={proc.returncode}\n"
            f"stderr_tail={stderr_tail[-2000:]}"
        )

    return ev


def _records_by_id(root: Optional[Path] = None) -> dict[str, dict]:
    out = {}
    for rec in load_records(root):
        if rec.get("type") == "evidence":
            out[rec["evidence_id"]] = rec
        elif rec.get("type") == "claim":
            out[rec["claim_id"]] = rec
    return out


def _evidence_records(evidence_ids: Iterable[str], root: Optional[Path]) -> list[dict]:
    by_id = _records_by_id(root)
    found = []
    missing = []
    for eid in evidence_ids:
        rec = by_id.get(eid)
        if rec is None:
            missing.append(eid)
        else:
            found.append(rec)
    if missing:
        raise TruthGateError(f"Evidence inexistente en trace: {', '.join(missing)}")
    return found


def _text_has_assertive_word(text: str) -> bool:
    low = text.lower()
    return any(w in low for w in ASSERTIVE_WORDS)


def _text_has_uncertainty(text: str) -> bool:
    low = text.lower()
    return any(w in low for w in UNCERTAIN_WORDS_FOR_FINAL)


def _contains_pytest(command: str) -> bool:
    return "pytest" in command.lower()


def _contains_search_command(command: str) -> bool:
    low = command.lower()
    return any(x in low for x in ("rg ", "ripgrep", "select-string", "grep ", "findstr "))


def _contains_git_diff(command: str) -> bool:
    low = command.lower()
    return "git diff" in low or "git status" in low


def add_claim(
    text: str,
    *,
    conclusion: str,
    evidence_ids: Iterable[str],
    kind: ClaimKind = "generic",
    root: Optional[str | Path] = None,
) -> Claim:
    """
    Registra una claim si cumple reglas mínimas.

    Regla central:
    - Toda afirmación fuerte necesita evidencia.
    - Cada tipo de claim exige comandos compatibles.
    """
    root_path = Path(root).resolve() if root else repo_root()
    evidence_ids = list(evidence_ids)

    if _text_has_assertive_word(text + " " + conclusion) and not evidence_ids:
        raise TruthGateError(f"Claim asertiva sin evidencia: {text}")

    evs = _evidence_records(evidence_ids, root_path)

    if kind == "test_pass":
        if not evs:
            raise TruthGateError("test_pass requiere evidencia pytest.")
        if not any(_contains_pytest(ev["command"]) and ev["returncode"] == 0 for ev in evs):
            raise TruthGateError("test_pass requiere al menos un comando pytest con rc=0.")

    if kind == "test_fail":
        if not any(_contains_pytest(ev["command"]) and ev["returncode"] != 0 for ev in evs):
            raise TruthGateError("test_fail requiere un comando pytest fallido registrado con allow_fail=True.")

    if kind == "absence":
        search_evs = [ev for ev in evs if _contains_search_command(ev["command"])]
        if len(search_evs) < 2:
            raise TruthGateError(
                "Una claim de ausencia/no-aparece requiere al menos 2 búsquedas independientes "
                "(por ejemplo rg + Select-String/grep) registradas como evidencia."
            )

    if kind == "preexisting_failure":
        has_failing_pytest = any(_contains_pytest(ev["command"]) and ev["returncode"] != 0 for ev in evs)
        has_baseline = any("baseline" in ev["purpose"].lower() or "before" in ev["purpose"].lower() for ev in evs)
        if not has_failing_pytest:
            raise TruthGateError("preexisting_failure requiere evidencia pytest fallida.")
        if not has_baseline:
            raise TruthGateError(
                "preexisting_failure requiere evidencia baseline/before-work. "
                "No basta con decir que era preexistente."
            )

    if kind == "code_change":
        if not any(_contains_git_diff(ev["command"]) for ev in evs):
            raise TruthGateError("code_change requiere evidencia de git diff/status.")

    if kind == "task_complete":
        if _text_has_uncertainty(text + " " + conclusion):
            raise TruthGateError(
                "task_complete no puede usar lenguaje incierto: probablemente/parece/creo/supongo..."
            )
        if not evidence_ids:
            raise TruthGateError("task_complete requiere evidencia.")
        if not any(_contains_pytest(ev["command"]) and ev["returncode"] == 0 for ev in evs):
            raise TruthGateError("task_complete requiere al menos una validación pytest con rc=0.")

    claim = Claim(
        claim_id=f"cl_{uuid.uuid4().hex[:12]}",
        kind=kind,
        text=text,
        conclusion=conclusion,
        evidence_ids=evidence_ids,
        created_at=utc_now(),
    )
    append_record({"type": "claim", **asdict(claim)}, root_path)
    return claim


def assert_can_close_task(root: Optional[str | Path] = None) -> None:
    """
    Puerta dura para bago task complete.

    Reglas:
    - Debe existir al menos una claim task_complete.
    - Toda claim asertiva debe tener evidence_ids.
    - No puede haber claims de ausencia sin búsquedas.
    - No puede haber preexisting_failure sin baseline.
    """
    root_path = Path(root).resolve() if root else repo_root()
    records = load_records(root_path)
    claims = [r for r in records if r.get("type") == "claim"]

    if not claims:
        raise TruthGateError("No hay claims registradas. No se puede cerrar la tarea.")

    for c in claims:
        text = f"{c.get('text','')} {c.get('conclusion','')}"
        if _text_has_assertive_word(text) and not c.get("evidence_ids"):
            raise TruthGateError(f"Claim asertiva sin evidencia: {c.get('claim_id')}: {c.get('text')}")

    if not any(c.get("kind") == "task_complete" for c in claims):
        raise TruthGateError("Falta claim kind=task_complete. No se puede cerrar la tarea.")

    # Revalida claims críticas usando add_claim sobre los records ya creados no es ideal
    # porque duplicaría claims; aquí hacemos comprobaciones estructurales.
    evidence = {r["evidence_id"]: r for r in records if r.get("type") == "evidence"}

    for c in claims:
        evs = [evidence[eid] for eid in c.get("evidence_ids", []) if eid in evidence]
        kind = c.get("kind")

        if kind == "absence":
            if len([ev for ev in evs if _contains_search_command(ev["command"])]) < 2:
                raise TruthGateError(f"Claim absence insuficientemente probada: {c.get('claim_id')}")

        if kind == "preexisting_failure":
            if not any(_contains_pytest(ev["command"]) and ev["returncode"] != 0 for ev in evs):
                raise TruthGateError(f"preexisting_failure sin pytest fallido: {c.get('claim_id')}")
            if not any("baseline" in ev["purpose"].lower() or "before" in ev["purpose"].lower() for ev in evs):
                raise TruthGateError(f"preexisting_failure sin baseline/before-work: {c.get('claim_id')}")

        if kind == "task_complete":
            if _text_has_uncertainty(c.get("text", "") + " " + c.get("conclusion", "")):
                raise TruthGateError(f"task_complete incierto: {c.get('claim_id')}")
            if not any(_contains_pytest(ev["command"]) and ev["returncode"] == 0 for ev in evs):
                raise TruthGateError(f"task_complete sin pytest rc=0: {c.get('claim_id')}")


def render_trace_report(root: Optional[str | Path] = None) -> str:
    """
    Genera un informe humano claim -> command -> evidence -> conclusion.
    """
    root_path = Path(root).resolve() if root else repo_root()
    records = load_records(root_path)
    evidence = {r["evidence_id"]: r for r in records if r.get("type") == "evidence"}
    claims = [r for r in records if r.get("type") == "claim"]

    lines = [
        "# BAGO TRACE REPORT",
        "",
        f"root: `{root_path}`",
        f"trace: `{trace_path(root_path)}`",
        "",
    ]

    for c in claims:
        lines.append(f"## Claim {c['claim_id']} [{c['kind']}]")
        lines.append(f"**Claim:** {c['text']}")
        lines.append("")
        for eid in c.get("evidence_ids", []):
            ev = evidence.get(eid)
            if not ev:
                lines.append(f"- MISSING EVIDENCE: `{eid}`")
                continue
            lines.append(f"- **Command:** `{ev['command']}`")
            lines.append(f"  - cwd: `{ev['cwd']}`")
            lines.append(f"  - rc: `{ev['returncode']}`")
            lines.append(f"  - sha256: `{ev['combined_sha256']}`")
            out = (ev.get("stdout_tail") or ev.get("stderr_tail") or "").strip()
            if out:
                out = out[-1200:]
                lines.append("  - tail:")
                lines.append("```")
                lines.append(out)
                lines.append("```")
        lines.append("")
        lines.append(f"**Conclusion:** {c['conclusion']}")
        lines.append("")

    return "\n".join(lines)
