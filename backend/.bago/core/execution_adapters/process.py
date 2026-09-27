"""Registered server-owned process execution adapter."""
from __future__ import annotations

import shutil
import shlex
import subprocess
import os
import sys
from pathlib import Path
import hashlib
import base64
import json
import ipaddress
from typing import Any

from execution_adapter_contract import ExecutionContext, ExecutionGatewayError
from execution_request import ExecutionRequest
from execution_claims import process_working_directory


class ProcessExecutionEffectAdapter:
    """Execute Permit-bound commands and fixed server-policy inspections."""

    effect_ids = frozenset({"process.execute", "process.inspect", "process.terminate"})
    server_policy_effects = frozenset({"process.inspect"})

    @staticmethod
    def is_read_only_launcher_argv(argv: Any) -> bool:
        if not isinstance(argv, list):
            return False
        values = [str(value) for value in argv]
        fixed = {
            ("node", "status", "--json"),
            ("node", "matrix", "--json"),
            ("node", "pieces", "--json"),
            ("node", "connectors", "--json"),
        }
        if tuple(values) in fixed:
            return True
        if len(values) == 5 and values[:3] == ["node", "evidence", "--limit"] and values[4] == "--json":
            try:
                return 1 <= int(values[3]) <= 100
            except ValueError:
                return False
        return False

    @staticmethod
    def is_read_only_github_argv(argv: Any) -> bool:
        if not isinstance(argv, list):
            return False
        values = [str(value) for value in argv]
        if values in (["auth", "status"], ["auth", "status", "--json", "hosts"]):
            return True
        if len(values) != 2 or values[0] != "api":
            return False
        import re
        return bool(re.fullmatch(
            r"repos/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/(?:readme|contents/[A-Za-z0-9_./-]{1,512}))?",
            values[1],
        ))

    @staticmethod
    def _git_query_argv(argv: Any) -> list[str] | None:
        if not isinstance(argv, list):
            return None
        values = [str(value) for value in argv]
        while len(values) >= 2 and values[0] == "-c" and values[1].startswith("safe.directory="):
            safe_directory = values[1].split("=", 1)[1]
            if not safe_directory or not Path(safe_directory).is_absolute():
                return None
            values = values[2:]
        return values

    @staticmethod
    def is_read_only_git_argv(argv: Any) -> bool:
        values = ProcessExecutionEffectAdapter._git_query_argv(argv)
        if values is None:
            return False
        read_only_queries = (
            ["rev-parse", "HEAD"],
            ["rev-parse", "--show-toplevel"],
            ["rev-parse", "--abbrev-ref", "HEAD"],
            ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
            ["status", "--porcelain=v1", "--untracked-files=all"],
            ["diff", "--binary", "HEAD"],
            ["diff", "--name-only"],
            ["remote", "get-url", "origin"],
            ["branch", "--show-current"],
        )
        return values in read_only_queries

    @staticmethod
    def is_authorized_executable_argv(executable: str, argv: Any) -> bool:
        if not isinstance(argv, list):
            return False
        values = [str(value) for value in argv]
        if executable == "gh":
            if ProcessExecutionEffectAdapter.is_read_only_github_argv(values):
                return True
            if len(values) in {4, 6} and values[:2] == ["repo", "create"]:
                import re
                return bool(re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", values[2])) and values[3] in {"--private", "--public"} and (
                    len(values) == 4 or values[4] == "--description" and len(values[5]) <= 500
                )
            if len(values) in {4, 6} and values[:2] == ["auth", "logout"]:
                import re
                valid_host = values[2] == "--hostname" and bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,253}", values[3]))
                return valid_host and (len(values) == 4 or values[4] == "--user" and bool(re.fullmatch(r"[A-Za-z0-9-]{1,39}", values[5])))
            if len(values) == 6 and values[:2] == ["auth", "login"]:
                import re
                return values[2] == "--hostname" and bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,253}", values[3])) and values[4] == "--token" and bool(values[5])
            return values == ["auth", "login", "--hostname", "github.com", "--web", "--clipboard", "--git-protocol", "https", "--skip-ssh-key", "--scopes", "repo,workflow"]
        if executable == "git":
            if ProcessExecutionEffectAdapter.is_read_only_git_argv(values):
                return True
            if len(values) != 3 or values[:1] != ["config"] or values[1] not in {"user.email", "user.name"}:
                return False
            return bool(values[2]) and not values[2].startswith("-") and "\x00" not in values[2] and len(values[2]) <= 254
        if os.path.normcase(os.path.realpath(executable)) == os.path.normcase(os.path.realpath(sys.executable)):
            return (
                len(values) >= 2
                and values[:2] == ["-m", "pytest"]
                and len(values) <= 130
                and all("\x00" not in value and len(value) <= 4096 for value in values)
            )
        return False

    def execute(self, request: ExecutionRequest, context: ExecutionContext) -> dict[str, Any]:
        manager = context.manager
        target = request.target if isinstance(request.target, dict) else {}
        operation = str(target.get("operation") or "")
        if operation == "launch_manager_server":
            authorization = context.services.get("_authorization")
            if not (
                isinstance(authorization, dict)
                and authorization.get("state") == "consumed"
                and authorization.get("effect_id") == request.effect_id == "process.execute"
                and authorization.get("operation_fingerprint") == request.fingerprint
                and authorization.get("session_id") == request.session_id
                and request.source_surface == "cli.manager.launch"
                and request.actor_kind == "user"
                and request.principal_id == "interactive-local-user"
            ):
                raise ExecutionGatewayError(
                    "Manager launch requires its exact consumed CLI Permit",
                    code="process_execution_authorization_required",
                )
            return self._launch_manager_server(request)
        if manager is None:
            raise ExecutionGatewayError(
                "Process execution requires SessionManager context",
                code="execution_context_manager_required",
            )
        session_id = str(getattr(manager, "session_id", "") or "")
        if not session_id or session_id != request.session_id:
            raise ExecutionGatewayError(
                "Process execution manager belongs to another session",
                code="execution_context_session_mismatch",
            )

        authorization = context.services.get("_authorization")
        direct_authorization = (
            isinstance(authorization, dict)
            and authorization.get("state") == "consumed"
            and authorization.get("effect_id") == request.effect_id
            and authorization.get("operation_fingerprint") == request.fingerprint
            and authorization.get("session_id") == request.session_id
        )
        server_inspection_authorization = (
            isinstance(authorization, dict)
            and authorization.get("kind") == "server_policy"
            and request.effect_id == "process.inspect"
            and authorization.get("effect_id") == request.effect_id
            and authorization.get("operation_fingerprint") == request.fingerprint
            and authorization.get("session_id") == request.session_id
            and request.source_surface == "server.process.inspect"
            and (
                (
                    str((request.target or {}).get("python_module") or "") == "bago_core.launcher"
                    and self.is_read_only_launcher_argv(
                        (request.arguments if isinstance(request.arguments, dict) else {}).get("argv")
                    )
                )
                or (
                    str((request.target or {}).get("executable") or "") == "gh"
                    and self.is_read_only_github_argv(
                        (request.arguments if isinstance(request.arguments, dict) else {}).get("argv")
                    )
                )
                or (
                    str((request.target or {}).get("executable") or "") == "git"
                    and self.is_read_only_git_argv(
                        (request.arguments if isinstance(request.arguments, dict) else {}).get("argv")
                    )
                )
            )
        )
        parent = context.services.get("_parent_request")
        gateway = context.services.get("_gateway")
        nested_authorization = (
            isinstance(authorization, dict)
            and authorization.get("state") == "consumed"
            and getattr(parent, "effect_id", "") == "plan.execute"
            and authorization.get("effect_id") == parent.effect_id
            and authorization.get("operation_fingerprint") == parent.fingerprint
            and request.parent_execution_id == parent.request_id
            and request.session_id == parent.session_id
            and request.principal_id == parent.principal_id
            and request.actor_kind == parent.actor_kind
            and request.source_surface == "plan.runtime"
            and gateway is not None
            and context.services.get("_execution_claim") is not None
        )
        if not (direct_authorization or nested_authorization or server_inspection_authorization):
            raise ExecutionGatewayError(
                "Process execution requires an exact consumed Permit or verified plan child context",
                code="process_execution_authorization_required",
            )

        if request.effect_id == "process.terminate":
            if str((request.target if isinstance(request.target, dict) else {}).get("operation") or "") == "stop_webchat":
                return self._terminate_webchat(request, context, authorization)
            return self._terminate_zombies(request, context, authorization)

        arguments = request.arguments if isinstance(request.arguments, dict) else {}
        executable = str(target.get("executable") or "").strip()
        python_module = str(target.get("python_module") or "").strip()
        python_script = str(target.get("python_script") or "").replace("\\", "/").strip()
        raw_argv = arguments.get("argv")
        command = str(target.get("command") or "").strip()
        child_env = None
        if python_script:
            if python_script != "scripts/bago_supervisor.py" or python_module or executable or command or not isinstance(raw_argv, list):
                raise ExecutionGatewayError(
                    "Python script process target is not approved",
                    code="process_execution_script_invalid",
                )
            framework_root = Path(str(getattr(manager, "framework_root", "") or "")).expanduser()
            try:
                framework_root = framework_root.resolve(strict=True)
                script_file = framework_root.joinpath(*python_script.split("/"))
                if str(target.get("python_root") or "") != str(framework_root) or not script_file.is_file():
                    raise OSError("script file is missing")
                expected_digest = str(target.get("python_module_sha256") or "")
                actual_digest = hashlib.sha256(script_file.read_bytes()).hexdigest()
                if not expected_digest or actual_digest != expected_digest:
                    raise OSError("script source changed after authorization")
            except (OSError, RuntimeError) as exc:
                raise ExecutionGatewayError(
                    "Python script is unavailable in the trusted BAGO runtime",
                    code="process_execution_script_unavailable",
                ) from exc
            executable = sys.executable
            argv = [str(script_file), *[str(value) for value in raw_argv]]
            inherited_pythonpath = os.environ.get("PYTHONPATH", "")
            child_env = dict(os.environ)
            child_env["PYTHONPATH"] = os.pathsep.join(
                item for item in (str(framework_root), inherited_pythonpath) if item
            )
            child_env["PYTHONUTF8"] = "1"
            child_env["PYTHONIOENCODING"] = "utf-8"
        elif python_module:
            allowed_modules = {"bago_core.launcher", "bago_core.session_control"}
            if python_module not in allowed_modules or executable or command:
                raise ExecutionGatewayError(
                    "Python module process target is not approved",
                    code="process_execution_module_invalid",
                )
            if not isinstance(raw_argv, list):
                raise ExecutionGatewayError(
                    "Python module process requires argv",
                    code="process_execution_request_invalid",
                )
            framework_root = Path(str(getattr(manager, "framework_root", "") or "")).expanduser()
            try:
                framework_root = framework_root.resolve(strict=True)
                module_path = framework_root.joinpath(*python_module.split("."))
                module_file = module_path.with_suffix(".py")
                if str(target.get("python_root") or "") != str(framework_root) or not module_file.is_file():
                    raise OSError("module file is missing")
                expected_digest = str(target.get("python_module_sha256") or "")
                actual_digest = hashlib.sha256(module_file.read_bytes()).hexdigest()
                if not expected_digest or actual_digest != expected_digest:
                    raise OSError("module source changed after authorization")
            except (OSError, RuntimeError) as exc:
                raise ExecutionGatewayError(
                    "Python module is unavailable in the trusted BAGO runtime",
                    code="process_execution_module_unavailable",
                ) from exc
            executable = sys.executable
            argv = ["-m", python_module, *[str(value) for value in raw_argv]]
            inherited_pythonpath = os.environ.get("PYTHONPATH", "")
            child_env = dict(os.environ)
            child_env["PYTHONPATH"] = os.pathsep.join(
                item for item in (str(framework_root), inherited_pythonpath) if item
            )
            child_env["PYTHONUTF8"] = "1"
            child_env["PYTHONIOENCODING"] = "utf-8"
        elif command:
            try:
                parsed = shlex.split(command, posix=True)
            except ValueError as exc:
                raise ExecutionGatewayError(
                    "Process command quoting is invalid",
                    code="process_execution_command_invalid",
                ) from exc
            if not parsed:
                raise ExecutionGatewayError(
                    "Process command cannot be empty",
                    code="process_execution_command_invalid",
                )
            executable = parsed[0]
            argv = parsed[1:]
        elif executable and isinstance(raw_argv, list):
            argv = [str(value) for value in raw_argv]
            if not self.is_authorized_executable_argv(executable, argv):
                raise ExecutionGatewayError(
                    "Process executable operation is not approved",
                    code="process_execution_executable_invalid",
                )
            if executable == "gh":
                child_env = dict(os.environ)
                child_env["GH_PROMPT_DISABLED"] = "1"
        else:
            raise ExecutionGatewayError(
                "Process request requires command or executable and argv",
                code="process_execution_request_invalid",
            )
        if any("\x00" in value for value in [executable, *argv]):
            raise ExecutionGatewayError(
                "Process arguments cannot contain NUL bytes",
                code="process_execution_argument_invalid",
            )

        try:
            cwd = process_working_directory(target, manager)
        except (OSError, RuntimeError, ValueError) as exc:
            raise ExecutionGatewayError(
                f"Process working directory is invalid: {exc}",
                code="process_execution_cwd_out_of_scope",
            ) from exc

        executable_path = shutil.which(executable)
        if not executable_path:
            raise ExecutionGatewayError(
                f"Process executable is unavailable: {executable}",
                code="process_execution_executable_unavailable",
            )
        try:
            timeout = float(target.get("timeout_seconds", 300))
        except (TypeError, ValueError) as exc:
            raise ExecutionGatewayError(
                "Process timeout must be numeric",
                code="process_execution_timeout_invalid",
            ) from exc
        if timeout <= 0 or timeout > 1800:
            raise ExecutionGatewayError(
                "Process timeout must be between 0 and 1800 seconds",
                code="process_execution_timeout_invalid",
            )
        if request.effect_id == "process.inspect" and timeout > 30:
            raise ExecutionGatewayError(
                "Read-only process inspection timeout exceeds policy",
                code="process_inspection_timeout_invalid",
            )

        output_digest = str(target.get("output_digest") or "")
        git_query_argv = self._git_query_argv(raw_argv)
        if output_digest and not (
            request.effect_id == "process.inspect"
            and output_digest == "sha256"
            and executable == "git"
            and git_query_argv == ["diff", "--binary", "HEAD"]
        ):
            raise ExecutionGatewayError(
                "Digest output is approved only for the exact candidate diff query",
                code="process_inspection_output_mode_invalid",
            )

        try:
            completed = subprocess.run(
                [executable_path, *argv],
                cwd=str(cwd),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=not bool(output_digest),
                encoding=None if output_digest else "utf-8",
                errors=None if output_digest else "replace",
                timeout=timeout,
                check=False,
                shell=False,
                env=child_env,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ExecutionGatewayError(
                f"Process execution failed: {exc}",
                code="process_execution_failed",
            ) from exc

        stdout = completed.stdout or b"" if output_digest else str(completed.stdout or "")
        if output_digest:
            stdout = f"sha256:{hashlib.sha256(stdout).hexdigest()}"
        return {
            "ok": completed.returncode == 0,
            "executed": True,
            "effect_id": request.effect_id,
            "executable": executable_path,
            "python_module": python_module,
            "cwd": str(cwd),
            "exit_code": int(completed.returncode),
            "stdout": str(stdout)[-65536:],
            "stderr": str(completed.stderr or "")[-65536:],
            "receipt_id": f"process-execute:{request.fingerprint}",
        }

    @staticmethod
    def _launch_manager_server(request: ExecutionRequest) -> dict[str, Any]:
        """Start only the current runtime's loopback manager through a consumed Permit."""
        target = request.target if isinstance(request.target, dict) else {}
        arguments = request.arguments if isinstance(request.arguments, dict) else {}
        runtime_root = Path(__file__).resolve().parents[3]
        module_file = runtime_root / "bago_core" / "launcher.py"
        base_path = Path(str(target.get("cwd") or "")).expanduser()
        ui_dist = Path(str(target.get("ui_dist") or "")).expanduser()
        host = str(target.get("host") or "")
        try:
            base_path = base_path.resolve(strict=True)
            ui_dist = ui_dist.resolve(strict=True)
            address = ipaddress.ip_address(host)
            port = int(target.get("port"))
            actual_digest = hashlib.sha256(module_file.read_bytes()).hexdigest()
            ui_dist.relative_to(base_path)
        except (OSError, RuntimeError, ValueError) as exc:
            raise ExecutionGatewayError(
                "Manager launch identity or paths are invalid",
                code="process_execution_manager_target_invalid",
            ) from exc
        if (
            not address.is_loopback
            or not 1 <= port <= 65535
            or not (ui_dist / "index.html").is_file()
            or str(target.get("python_root") or "") != str(runtime_root)
            or str(target.get("python_module_sha256") or "") != actual_digest
            or arguments.get("argv") != [
                "--base-path", str(base_path), "serve", "--host", host,
                "--port", str(port), "--ui-dist", str(ui_dist),
            ]
        ):
            raise ExecutionGatewayError(
                "Manager launch target is outside the fixed loopback policy",
                code="process_execution_manager_target_invalid",
            )
        child_env = dict(os.environ)
        child_env["PYTHONPATH"] = os.pathsep.join(
            item for item in (str(runtime_root), os.environ.get("PYTHONPATH", "")) if item
        )
        child_env["PYTHONUTF8"] = "1"
        child_env["PYTHONIOENCODING"] = "utf-8"
        popen_kwargs: dict[str, Any] = {
            "cwd": str(base_path),
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "shell": False,
            "close_fds": True,
            "env": child_env,
        }
        if os.name == "nt":
            popen_kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            popen_kwargs["start_new_session"] = True
        command = [sys.executable, "-m", "bago_core.launcher", *arguments["argv"]]
        try:
            process = subprocess.Popen(command, **popen_kwargs)
        except OSError as exc:
            raise ExecutionGatewayError(
                f"BAGO manager could not be started: {exc}",
                code="process_execution_manager_start_failed",
            ) from exc
        return {
            "ok": True,
            "executed": True,
            "effect_id": request.effect_id,
            "process_id": int(process.pid or 0),
            "receipt_id": f"process-execute:{request.fingerprint}",
        }

    @staticmethod
    def _terminate_webchat(request: ExecutionRequest, context: ExecutionContext, authorization: dict[str, Any]) -> dict[str, Any]:
        manager = context.manager
        target = request.target if isinstance(request.target, dict) else {}
        framework_root = str(getattr(manager, "framework_root", "") or "").strip()
        try:
            root = Path(framework_root).expanduser().resolve(strict=True)
            process_id = int(target.get("process_id", 0))
            port = int(target.get("port", 0))
            launcher = Path(str(sys.argv[0])).resolve(strict=True)
            argv_port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 0
        except (OSError, RuntimeError, TypeError, ValueError, IndexError) as exc:
            raise ExecutionGatewayError(
                "Webchat process identity is unavailable",
                code="process_termination_identity_invalid",
            ) from exc
        try:
            launcher.relative_to(root)
        except ValueError as exc:
            raise ExecutionGatewayError(
                "Webchat launcher is outside the trusted runtime",
                code="process_termination_identity_invalid",
            ) from exc
        if (
            target.get("operation") != "stop_webchat"
            or str(target.get("python_root") or "") != str(root)
            or process_id != os.getpid()
            or not 1 <= port <= 65535
            or argv_port != port
            or "serve" not in sys.argv
            or launcher.name.lower() != "launcher.py"
            or str(request.arguments.get("argv") if isinstance(request.arguments, dict) else "") not in {"[]", ""}
        ):
            raise ExecutionGatewayError(
                "Termination target is not the active BAGO webchat server",
                code="process_termination_target_invalid",
            )
        if os.name != "nt":
            raise ExecutionGatewayError(
                "Webchat process termination is supported only on Windows",
                code="process_termination_platform_unsupported",
            )
        system_root = str(os.environ.get("SystemRoot") or r"C:\Windows")
        powershell = Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        if not powershell.is_file():
            raise ExecutionGatewayError(
                "Trusted Windows PowerShell is unavailable",
                code="process_termination_executor_unavailable",
            )
        root_payload = base64.b64encode(str(root).encode("utf-8")).decode("ascii")
        script = f"""
$ErrorActionPreference = 'Stop'
Start-Sleep -Milliseconds 700
$runtimeRoot = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{root_payload}'))
$targetPid = {process_id}
$targetPort = {port}
$proc = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $targetPid)
if (-not $proc -or -not $proc.CommandLine -or -not $proc.ExecutablePath) {{ exit 3 }}
$cmd = [string]$proc.CommandLine
if ($cmd.IndexOf($runtimeRoot, [StringComparison]::OrdinalIgnoreCase) -lt 0 -or
    $cmd.IndexOf('bago_core.launcher', [StringComparison]::OrdinalIgnoreCase) -lt 0 -or
    $cmd.IndexOf('--port ' + [string]$targetPort, [StringComparison]::OrdinalIgnoreCase) -lt 0 -or
    $cmd.IndexOf(' serve', [StringComparison]::OrdinalIgnoreCase) -lt 0) {{ exit 4 }}
Stop-Process -Id $targetPid -Force
"""
        try:
            child = subprocess.Popen(
                [str(powershell), "-NoProfile", "-NonInteractive", "-Command", script],
                cwd=str(root),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
                close_fds=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError as exc:
            raise ExecutionGatewayError(
                f"Webchat termination could not be scheduled: {exc}",
                code="process_termination_schedule_failed",
            ) from exc
        return {
            "ok": True,
            "executed": True,
            "effect_id": request.effect_id,
            "termination_scheduled": True,
            "target_process_id": process_id,
            "port": port,
            "terminator_pid": int(child.pid or 0),
            "receipt_id": f"process-terminate:{request.fingerprint}",
            "authorization_decision_id": authorization.get("decision_id"),
        }

    @staticmethod
    def _terminate_zombies(request: ExecutionRequest, context: ExecutionContext, authorization: dict[str, Any]) -> dict[str, Any]:
        manager = context.manager
        target = request.target if isinstance(request.target, dict) else {}
        framework_root = str(getattr(manager, "framework_root", "") or "").strip()
        state_root = str(getattr(manager, "state_root", "") or "").strip()
        expected_roots = sorted({
            str(Path(framework_root).expanduser().resolve()) if framework_root else "",
            str(Path(state_root).expanduser().resolve()) if state_root else "",
        })
        roots = target.get("cleanup_roots")
        if (
            target.get("operation") != "cleanup_zombies"
            or not isinstance(roots, list)
            or sorted(set(str(item) for item in roots)) != expected_roots
            or not framework_root
            or not state_root
        ):
            raise ExecutionGatewayError(
                "Process cleanup target is not the active trusted runtime and state roots",
                code="process_termination_target_invalid",
            )
        if os.name != "nt":
            raise ExecutionGatewayError(
                "Zombie process cleanup is supported only on Windows",
                code="process_termination_platform_unsupported",
            )
        payload = base64.b64encode(
            json.dumps(expected_roots, ensure_ascii=True).encode("utf-8")
        ).decode("ascii")
        script = f"""
$ErrorActionPreference = 'Stop'
$roots = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{payload}')) | ConvertFrom-Json
$backendPid = {int(os.getpid())}
$stopped = @()
Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" | ForEach-Object {{
  $proc = $_
  if ($proc.ProcessId -eq $backendPid -or -not $proc.CommandLine) {{ return }}
  $matched = $false
  foreach ($root in $roots) {{
    if ($proc.CommandLine.IndexOf([string]$root, [StringComparison]::OrdinalIgnoreCase) -ge 0) {{ $matched = $true; break }}
  }}
  if ($matched) {{
    Stop-Process -Id $proc.ProcessId -Force
    $stopped += [ordered]@{{ pid = $proc.ProcessId; executable = $proc.ExecutablePath; command_line = $proc.CommandLine }}
  }}
}}
[ordered]@{{ ok = $true; cleaned = $stopped.Count; matched = $stopped }} | ConvertTo-Json -Depth 4 -Compress
"""
        system_root = str(os.environ.get("SystemRoot") or r"C:\Windows")
        powershell = Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        if not powershell.is_file():
            raise ExecutionGatewayError(
                "Trusted Windows PowerShell is unavailable",
                code="process_termination_executor_unavailable",
            )
        try:
            completed = subprocess.run(
                [str(powershell), "-NoProfile", "-NonInteractive", "-Command", script],
                cwd=str(Path(str(getattr(manager, "framework_root", ""))).resolve()),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
                check=False,
                shell=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ExecutionGatewayError(
                f"Process cleanup failed: {exc}",
                code="process_termination_failed",
            ) from exc
        if completed.returncode != 0:
            raise ExecutionGatewayError(
                f"Process cleanup failed: {str(completed.stderr or '')[-2048:]}",
                code="process_termination_failed",
            )
        try:
            result = json.loads(str(completed.stdout or "{}"))
        except json.JSONDecodeError as exc:
            raise ExecutionGatewayError(
                "Process cleanup returned invalid JSON",
                code="process_termination_result_invalid",
            ) from exc
        return {
            "ok": True,
            "executed": True,
            "effect_id": request.effect_id,
            "cleaned": int(result.get("cleaned") or 0),
            "matched": result.get("matched") if isinstance(result.get("matched"), list) else [],
            "roots": expected_roots,
            "receipt_id": f"process-terminate:{request.fingerprint}",
            "authorization_decision_id": authorization.get("decision_id"),
        }
