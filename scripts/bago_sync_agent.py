#!/usr/bin/env python3
"""Gobernador de sincronizacion Git para BAGO.

El script es el ejecutor mecanico del agente ``bago-sync-agent``. Mantiene
separadas estas operaciones:

* ``plan``: inspecciona el candidato y produce un receipt sin mutar el
  historial ni el worktree (solo hace ``fetch`` si se solicita).
* ``execute``: ejecuta validadores explicitos y, solo con la bandera
  correspondiente, hace commit, push y merge de un PR concreto.

Guardas deliberadas:

* no se usa un shell para validadores ni para Git;
* no se hace force-push, reset destructivo ni resolucion automatica de
  divergencias;
* los cambios sucios preexistentes solo se preservan si el operador lo pide
  explicitamente y proporciona paths acotados para el commit;
* los receipts no almacenan stdout/stderr de validadores para no convertirlos
  en un canal de secretos; solo guardan hashes y codigos de salida.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence


SCHEMA = "bago.sync-agent.receipt.v1"
MAX_VALIDATORS = 3
DEFAULT_TIMEOUT_SECONDS = 1800


class SyncAgentError(RuntimeError):
    """Error operacional que debe convertirse en un receipt FAILED/BLOCKED."""


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0

    @property
    def output_hashes(self) -> dict[str, str]:
        return {
            "stdout_sha256": hashlib.sha256(self.stdout.encode("utf-8", "replace")).hexdigest(),
            "stderr_sha256": hashlib.sha256(self.stderr.encode("utf-8", "replace")).hexdigest(),
        }


@dataclass(frozen=True)
class ValidatorSpec:
    name: str
    argv: tuple[str, ...]

    @property
    def command_sha256(self) -> str:
        return hashlib.sha256("\0".join(self.argv).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ValidatorResult:
    name: str
    command_sha256: str
    returncode: int
    duration_ms: int
    timed_out: bool = False
    error: str = ""
    output_hashes: dict[str, str] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.returncode == 0 and not self.timed_out and not self.error

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "command_sha256": self.command_sha256,
            "returncode": self.returncode,
            "duration_ms": self.duration_ms,
            "timed_out": self.timed_out,
            "error": self.error,
            "output_hashes": dict(self.output_hashes),
            "status": "PASS" if self.passed else "FAIL",
        }


@dataclass(frozen=True)
class GitSnapshot:
    root: str
    branch: str
    head: str
    remote: str
    remote_url: str
    upstream: str
    dirty_paths: tuple[str, ...]
    staged_paths: tuple[str, ...]
    ahead: int | None
    behind: int | None
    remote_branch_exists: bool

    @property
    def dirty(self) -> bool:
        return bool(self.dirty_paths)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "branch": self.branch,
            "head": self.head,
            "remote": self.remote,
            "remote_url": self.remote_url,
            "upstream": self.upstream,
            "dirty": self.dirty,
            "dirty_paths": list(self.dirty_paths),
            "staged_paths": list(self.staged_paths),
            "ahead": self.ahead,
            "behind": self.behind,
            "remote_branch_exists": self.remote_branch_exists,
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_git_prefix(root: Path) -> list[str]:
    return ["git", "-c", f"safe.directory={root.as_posix()}"]


def _run(
    argv: Sequence[str],
    cwd: Path,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> CommandResult:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            list(argv),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        return CommandResult(tuple(argv), 127, stderr=str(exc), duration_ms=_elapsed_ms(started))
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return CommandResult(
            tuple(argv),
            124,
            stdout=stdout,
            stderr=stderr or f"timeout after {timeout}s",
            duration_ms=_elapsed_ms(started),
        )
    return CommandResult(
        tuple(argv),
        completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        duration_ms=_elapsed_ms(started),
    )


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def _git(
    root: Path,
    *args: str,
    allow_failure: bool = False,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> CommandResult:
    result = _run([*_safe_git_prefix(root), *args], root, timeout=timeout)
    if result.returncode and not allow_failure:
        detail = result.stderr.strip() or result.stdout.strip() or "sin detalle"
        raise SyncAgentError(f"git {' '.join(args)} fallo ({result.returncode}): {detail}")
    return result


def _resolve_root(value: str | Path) -> Path:
    candidate = Path(value).expanduser().resolve()
    result = _run(["git", "-C", str(candidate), "rev-parse", "--show-toplevel"], candidate)
    if result.returncode:
        detail = result.stderr.strip() or "no es un repositorio Git"
        raise SyncAgentError(f"repositorio invalido {candidate}: {detail}")
    return Path(result.stdout.strip()).resolve()


def _parse_status(root: Path) -> tuple[tuple[str, ...], tuple[str, ...]]:
    raw = _git(root, "status", "--porcelain=v1", "--untracked-files=all").stdout
    dirty: list[str] = []
    staged: list[str] = []
    for line in raw.splitlines():
        if not line:
            continue
        code = line[:2]
        path = line[3:] if len(line) > 3 else line
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        dirty.append(path)
        if code[0] not in {" ", "?"}:
            staged.append(path)
    return tuple(sorted(set(dirty))), tuple(sorted(set(staged)))


def _ahead_behind(root: Path, remote_ref: str) -> tuple[int | None, int | None, bool]:
    verify = _git(root, "rev-parse", "--verify", remote_ref, allow_failure=True)
    if verify.returncode:
        return None, None, False
    counts = _git(root, "rev-list", "--left-right", "--count", f"HEAD...{remote_ref}").stdout.split()
    if len(counts) != 2:
        raise SyncAgentError(f"no se pudo interpretar la divergencia de HEAD...{remote_ref}")
    return int(counts[0]), int(counts[1]), True


def snapshot(root: Path, remote: str = "origin", base: str = "main") -> GitSnapshot:
    root = _resolve_root(root)
    branch = _git(root, "branch", "--show-current").stdout.strip() or "detached"
    head = _git(root, "rev-parse", "HEAD").stdout.strip()
    remote_url = _git(root, "remote", "get-url", remote, allow_failure=True).stdout.strip()
    upstream = _git(
        root,
        "rev-parse",
        "--abbrev-ref",
        "--symbolic-full-name",
        "@{u}",
        allow_failure=True,
    ).stdout.strip()
    dirty_paths, staged_paths = _parse_status(root)
    ahead, behind, remote_branch_exists = _ahead_behind(root, f"{remote}/{branch}")
    if branch == "detached":
        ahead, behind, remote_branch_exists = None, None, False
    return GitSnapshot(
        root=str(root),
        branch=branch,
        head=head,
        remote=remote,
        remote_url=remote_url,
        upstream=upstream,
        dirty_paths=dirty_paths,
        staged_paths=staged_paths,
        ahead=ahead,
        behind=behind,
        remote_branch_exists=remote_branch_exists,
    )


def parse_validator(value: str) -> ValidatorSpec:
    name, separator, command = value.partition("=")
    if not separator or not name.strip() or not command.strip():
        raise SyncAgentError("cada --validator debe tener el formato nombre=comando")
    try:
        argv = tuple(shlex.split(command, posix=True))
    except ValueError as exc:
        raise SyncAgentError(f"validator {name!r} tiene comillas invalidas: {exc}") from exc
    if not argv:
        raise SyncAgentError(f"validator {name!r} no tiene comando")
    return ValidatorSpec(name.strip(), argv)


def parse_validators(values: Iterable[str]) -> tuple[ValidatorSpec, ...]:
    specs = tuple(parse_validator(value) for value in values)
    if len(specs) > MAX_VALIDATORS:
        raise SyncAgentError(f"se permiten como maximo {MAX_VALIDATORS} validadores externos")
    names = [spec.name for spec in specs]
    if len(set(names)) != len(names):
        raise SyncAgentError("los validadores deben tener nombres distintos")
    return specs


def _run_validator(root: Path, spec: ValidatorSpec, timeout: int) -> ValidatorResult:
    result = _run(spec.argv, root, timeout=timeout)
    return ValidatorResult(
        name=spec.name,
        command_sha256=spec.command_sha256,
        returncode=result.returncode,
        duration_ms=result.duration_ms,
        timed_out=result.returncode == 124,
        error=(result.stderr.strip()[-500:] if result.returncode == 127 else ""),
        output_hashes=result.output_hashes,
    )


def run_validators(
    root: Path,
    specs: Sequence[ValidatorSpec],
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[tuple[ValidatorResult, ...], bool]:
    """Ejecuta hasta tres validadores en paralelo y detecta mutacion del worktree."""
    if not specs:
        return (), False
    before = snapshot(root)
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(specs)) as pool:
        futures = [pool.submit(_run_validator, root, spec, timeout) for spec in specs]
        results = tuple(future.result() for future in futures)
    after = snapshot(root)
    mutated = before.head != after.head or before.dirty_paths != after.dirty_paths
    return results, mutated


def _path_is_allowed(path: str, allowed: Sequence[str]) -> bool:
    normalized = path.replace("\\", "/").lstrip("./")
    for raw in allowed:
        candidate = raw.replace("\\", "/").lstrip("./").rstrip("/")
        if normalized == candidate or normalized.startswith(candidate + "/"):
            return True
    return False


def _preflight_blockers(
    current: GitSnapshot,
    *,
    base: str,
    paths: Sequence[str],
    commit: bool,
    push: bool,
    merge_pr: int | None,
    preserve_unrelated_dirty: bool,
    allow_main_push: bool,
    validators: Sequence[ValidatorSpec],
    skip_validation: bool,
) -> list[str]:
    blockers: list[str] = []
    if not current.remote_url:
        blockers.append(f"no existe el remote {current.remote!r}")
    if current.branch == "detached":
        blockers.append("HEAD esta detached; el agente necesita una rama nombrada")
    if current.ahead is not None and current.behind is not None and current.ahead and current.behind:
        blockers.append(
            f"rama divergente: ahead={current.ahead}, behind={current.behind}; resolver manualmente"
        )
    if commit and not paths:
        blockers.append("commit solicitado sin --path; el alcance debe ser explicito")
    if commit and current.staged_paths:
        blockers.append("hay cambios staged preexistentes; no se pueden atribuir al agente")
    if commit and paths:
        outside = [path for path in current.dirty_paths if not _path_is_allowed(path, paths)]
        if outside and not preserve_unrelated_dirty:
            blockers.append(
                "hay cambios sucios fuera del alcance: " + ", ".join(outside[:8])
                + "; usar --preserve-unrelated-dirty solo si se desea preservarlos"
            )
    if (push or merge_pr is not None) and current.dirty and not commit and not preserve_unrelated_dirty:
        blockers.append("push/merge con worktree sucio requiere --preserve-unrelated-dirty")
    if (push or merge_pr is not None) and current.branch == base and not allow_main_push:
        blockers.append(
            f"push directo a {base!r} bloqueado; usar una rama/PR o --allow-main-push explicitamente"
        )
    if commit and not validators and not skip_validation:
        blockers.append("commit sin validadores; proporcionar --validator o --skip-validation explicitamente")
    if merge_pr is not None and shutil.which("gh") is None:
        blockers.append("merge solicitado pero GitHub CLI (gh) no esta disponible")
    return blockers


def build_plan(
    current: GitSnapshot,
    *,
    base: str,
    paths: Sequence[str],
    commit: bool,
    push: bool,
    merge_pr: int | None,
    preserve_unrelated_dirty: bool = False,
    allow_main_push: bool = False,
    validators: Sequence[ValidatorSpec] = (),
    skip_validation: bool = False,
) -> dict[str, Any]:
    blockers = _preflight_blockers(
        current,
        base=base,
        paths=paths,
        commit=commit,
        push=push,
        merge_pr=merge_pr,
        preserve_unrelated_dirty=preserve_unrelated_dirty,
        allow_main_push=allow_main_push,
        validators=validators,
        skip_validation=skip_validation,
    )
    actions: list[str] = ["fetch"]
    if current.behind and not current.ahead:
        actions.append("fast_forward_if_requested")
    if validators:
        actions.append(f"run_{len(validators)}_validator(s)_in_parallel")
    if commit:
        actions.extend(["stage_scoped_paths", "commit"])
    if push or merge_pr is not None:
        actions.append("push")
    if merge_pr is not None:
        actions.extend(["verify_pr_binding", "merge_pr", "verify_remote_merge"])
    return {
        "status": "BLOCKED" if blockers else "PREPARED",
        "branch": current.branch,
        "base": base,
        "actions": actions,
        "blockers": blockers,
        "paths": list(paths),
        "validators": [spec.name for spec in validators],
        "requested": {
            "commit": commit,
            "push": push,
            "merge_pr": merge_pr,
            "preserve_unrelated_dirty": preserve_unrelated_dirty,
            "allow_main_push": allow_main_push,
            "skip_validation": skip_validation,
        },
    }


def _gh_json(root: Path, args: Sequence[str]) -> dict[str, Any]:
    result = _run(["gh", *args], root)
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "sin detalle"
        raise SyncAgentError(f"gh {' '.join(args)} fallo ({result.returncode}): {detail}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SyncAgentError(f"gh devolvio JSON invalido: {exc}") from exc
    if not isinstance(payload, dict):
        raise SyncAgentError("gh devolvio un payload que no es objeto JSON")
    return payload


def _verify_pr_binding(root: Path, pr_number: int, branch: str, base: str) -> dict[str, Any]:
    payload = _gh_json(
        root,
        [
            "pr",
            "view",
            str(pr_number),
            "--json",
            "number,state,isDraft,baseRefName,headRefName,headRefOid",
        ],
    )
    mismatches: list[str] = []
    if payload.get("state") != "OPEN":
        mismatches.append(f"PR state={payload.get('state')!r}, se esperaba OPEN")
    if payload.get("isDraft"):
        mismatches.append("el PR sigue siendo draft")
    if payload.get("baseRefName") != base:
        mismatches.append(f"base={payload.get('baseRefName')!r}, se esperaba {base!r}")
    if payload.get("headRefName") != branch:
        mismatches.append(f"head={payload.get('headRefName')!r}, se esperaba {branch!r}")
    if mismatches:
        raise SyncAgentError("PR no corresponde al candidato: " + "; ".join(mismatches))
    return payload


def _write_receipt(root: Path, payload: dict[str, Any], requested: str = "") -> str:
    receipt_path = Path(requested).expanduser() if requested else (
        root / ".bago" / "evidence" / "sync-agent" / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:10]}.json"
    )
    receipt_path = receipt_path.resolve()
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=str(receipt_path.parent), delete=False, prefix=".sync-agent-", suffix=".tmp"
    ) as handle:
        handle.write(encoded)
        temporary = Path(handle.name)
    os.replace(temporary, receipt_path)
    return str(receipt_path)


def _public_validator_spec(spec: ValidatorSpec) -> dict[str, str]:
    return {"name": spec.name, "command_sha256": spec.command_sha256}


def _action(name: str, status: str, result: CommandResult | None = None, detail: str = "") -> dict[str, Any]:
    payload: dict[str, Any] = {"action": name, "status": status}
    if detail:
        payload["detail"] = detail
    if result is not None:
        payload["returncode"] = result.returncode
        payload["duration_ms"] = result.duration_ms
        payload["output_hashes"] = result.output_hashes
    return payload


def execute(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    root = _resolve_root(args.root)
    validators = parse_validators(args.validator)
    started_at = _utc_now()
    initial = snapshot(root, args.remote, args.base)
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "run_id": uuid.uuid4().hex,
        "started_at": started_at,
        "mode": "execute",
        "repository": initial.to_dict(),
        "requested": {
            "base": args.base,
            "remote": args.remote,
            "paths": list(args.path),
            "validators": [_public_validator_spec(spec) for spec in validators],
            "commit": bool(args.commit),
            "push": bool(args.push),
            "merge_pr": args.merge_pr,
        },
        "actions": [],
    }
    plan = build_plan(
        initial,
        base=args.base,
        paths=args.path,
        commit=args.commit,
        push=args.push,
        merge_pr=args.merge_pr,
        preserve_unrelated_dirty=args.preserve_unrelated_dirty,
        allow_main_push=args.allow_main_push,
        validators=validators,
        skip_validation=args.skip_validation,
    )
    receipt["plan"] = plan
    if plan["blockers"]:
        receipt["status"] = "BLOCKED"
        receipt["finished_at"] = _utc_now()
        receipt["receipt"] = _write_receipt(root, receipt, args.receipt)
        return 2, receipt

    try:
        fetch = _git(root, "fetch", "--prune", args.remote, timeout=args.timeout)
        receipt["actions"].append(_action("fetch", "PASS", fetch))
        current = snapshot(root, args.remote, args.base)

        refreshed_plan = build_plan(
            current,
            base=args.base,
            paths=args.path,
            commit=args.commit,
            push=args.push,
            merge_pr=args.merge_pr,
            preserve_unrelated_dirty=args.preserve_unrelated_dirty,
            allow_main_push=args.allow_main_push,
            validators=validators,
            skip_validation=args.skip_validation,
        )
        if refreshed_plan["blockers"]:
            raise SyncAgentError("; ".join(refreshed_plan["blockers"]))
        if current.behind and not current.ahead and not args.update_branch:
            raise SyncAgentError(
                f"la rama esta behind={current.behind}; usar --update-branch para hacer fast-forward"
            )

        if args.update_branch and current.behind and not current.ahead:
            if current.dirty:
                raise SyncAgentError("no se puede hacer fast-forward con worktree sucio")
            update = _git(root, "merge", "--ff-only", f"{args.remote}/{current.branch}", timeout=args.timeout)
            receipt["actions"].append(_action("fast_forward", "PASS", update))
            current = snapshot(root, args.remote, args.base)

        if validators:
            results, mutated = run_validators(root, validators, timeout=args.timeout)
            receipt["validators"] = [result.to_dict() for result in results]
            if mutated:
                raise SyncAgentError("un validador modifico el HEAD o el worktree; se detiene el flujo")
            if not all(result.passed for result in results):
                raise SyncAgentError("uno o mas validadores externos fallaron")
            receipt["actions"].append(_action("external_validation", "PASS", detail=f"{len(results)} validator(s)"))
        elif args.skip_validation:
            receipt["actions"].append(_action("external_validation", "SKIPPED", detail="--skip-validation explicito"))

        if args.commit:
            add = _git(root, "add", "--", *args.path, timeout=args.timeout)
            receipt["actions"].append(_action("stage_scoped_paths", "PASS", add))
            after_add = snapshot(root, args.remote, args.base)
            staged = [path for path in after_add.staged_paths if _path_is_allowed(path, args.path)]
            outside = [path for path in after_add.staged_paths if not _path_is_allowed(path, args.path)]
            if outside:
                raise SyncAgentError("git add produjo paths fuera del alcance: " + ", ".join(outside))
            if not staged:
                raise SyncAgentError("no hay cambios staged dentro del alcance solicitado")
            commit = _git(root, "commit", "-m", args.message, timeout=args.timeout)
            receipt["actions"].append(_action("commit", "PASS", commit))

        if args.push or args.merge_pr is not None:
            current = snapshot(root, args.remote, args.base)
            push = _git(root, "push", args.remote, f"HEAD:{current.branch}", timeout=args.timeout)
            receipt["actions"].append(_action("push", "PASS", push))

        if args.merge_pr is not None:
            current = snapshot(root, args.remote, args.base)
            pr_before = _verify_pr_binding(root, args.merge_pr, current.branch, args.base)
            receipt["pr_before"] = pr_before
            merge = _run(["gh", "pr", "merge", str(args.merge_pr), f"--{args.merge_method}"], root, timeout=args.timeout)
            if merge.returncode:
                detail = merge.stderr.strip() or merge.stdout.strip() or "sin detalle"
                raise SyncAgentError(f"gh pr merge fallo ({merge.returncode}): {detail}")
            receipt["actions"].append(_action("merge_pr", "PASS", merge))
            pr_after = _gh_json(
                root,
                ["pr", "view", str(args.merge_pr), "--json", "number,state,mergedAt,mergeCommit,baseRefName,headRefName"],
            )
            receipt["pr_after"] = pr_after
            if pr_after.get("state") != "MERGED" or not pr_after.get("mergedAt"):
                raise SyncAgentError("GitHub no confirma el merge del PR solicitado")
            receipt["actions"].append(_action("verify_remote_merge", "PASS"))

        final = snapshot(root, args.remote, args.base)
        receipt["final_repository"] = final.to_dict()
        receipt["status"] = "EXECUTED"
        receipt["finished_at"] = _utc_now()
        receipt["receipt"] = _write_receipt(root, receipt, args.receipt)
        return 0, receipt
    except SyncAgentError as exc:
        receipt["status"] = "FAILED"
        receipt["error"] = str(exc)
        receipt["finished_at"] = _utc_now()
        receipt["receipt"] = _write_receipt(root, receipt, args.receipt)
        return 1, receipt


def plan(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    root = _resolve_root(args.root)
    validators = parse_validators(args.validator)
    actions: list[dict[str, Any]] = []
    if args.fetch:
        fetch = _git(root, "fetch", "--prune", args.remote, timeout=args.timeout)
        actions.append(_action("fetch", "PASS", fetch))
    current = snapshot(root, args.remote, args.base)
    payload = {
        "schema": SCHEMA,
        "run_id": uuid.uuid4().hex,
        "started_at": _utc_now(),
        "mode": "plan",
        "repository": current.to_dict(),
        "plan": build_plan(
            current,
            base=args.base,
            paths=args.path,
            commit=args.commit,
            push=args.push,
            merge_pr=args.merge_pr,
            preserve_unrelated_dirty=args.preserve_unrelated_dirty,
            allow_main_push=args.allow_main_push,
            validators=validators,
            skip_validation=args.skip_validation,
        ),
        "actions": actions,
        "status": "BLOCKED" if build_plan(
            current,
            base=args.base,
            paths=args.path,
            commit=args.commit,
            push=args.push,
            merge_pr=args.merge_pr,
            preserve_unrelated_dirty=args.preserve_unrelated_dirty,
            allow_main_push=args.allow_main_push,
            validators=validators,
            skip_validation=args.skip_validation,
        )["blockers"] else "PREPARED",
        "finished_at": _utc_now(),
    }
    payload["receipt"] = _write_receipt(root, payload, args.receipt)
    return (2 if payload["status"] == "BLOCKED" else 0), payload


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", default=".", help="Raiz del repositorio")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--base", default="main")
    parser.add_argument("--path", action="append", default=[], help="Path permitido para el commit; repetir para varios")
    parser.add_argument("--validator", action="append", default=[], metavar="NOMBRE=COMANDO", help="Hasta tres validadores read-only")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--receipt", default="", help="Ruta opcional del receipt JSON")
    parser.add_argument("--preserve-unrelated-dirty", action="store_true")
    parser.add_argument("--allow-main-push", action="store_true")
    parser.add_argument("--skip-validation", action="store_true")
    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--merge-pr", type=int, default=None)
    parser.add_argument("--json", action="store_true", help="Salida JSON")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bago-sync-agent",
        description="Planifica y ejecuta sincronizacion Git gobernada para BAGO",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    plan_parser = sub.add_parser("plan", help="Inspecciona y produce un plan/receipt")
    _add_common(plan_parser)
    plan_parser.add_argument("--fetch", action="store_true", help="Actualizar refs remotas antes de planificar")
    execute_parser = sub.add_parser("execute", help="Ejecuta validacion y acciones Git explicitamente solicitadas")
    _add_common(execute_parser)
    execute_parser.add_argument("--message", default="", help="Mensaje de commit")
    execute_parser.add_argument("--update-branch", action="store_true", help="Fast-forward si la rama solo esta behind")
    return parser


def _validate_arguments(args: argparse.Namespace) -> None:
    if args.command == "execute":
        if not (args.commit or args.push or args.merge_pr is not None):
            raise SyncAgentError("execute necesita --commit, --push o --merge-pr")
        if args.commit and not args.message.strip():
            raise SyncAgentError("--commit necesita --message")
        if args.merge_pr is not None:
            args.push = True
    if args.timeout <= 0:
        raise SyncAgentError("--timeout debe ser positivo")


def _print_payload(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return
    print(f"{payload.get('status', 'UNKNOWN')}: {payload.get('mode', 'sync-agent')}")
    plan_payload = payload.get("plan", {})
    for blocker in plan_payload.get("blockers", []):
        print(f"BLOCKER: {blocker}")
    if payload.get("receipt"):
        print(f"Receipt: {payload['receipt']}")
    if payload.get("error"):
        print(f"ERROR: {payload['error']}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        _validate_arguments(args)
        code, payload = plan(args) if args.command == "plan" else execute(args)
    except SyncAgentError as exc:
        payload = {"schema": SCHEMA, "status": "BLOCKED", "error": str(exc)}
        code = 2
    _print_payload(payload, bool(args.json))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
