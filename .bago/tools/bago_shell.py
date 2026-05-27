#!/usr/bin/env python3
"""
bago_shell.py — BAGO Interactive Shell (BISH) + Agente Autónomo

Shell propia de BAGO que habla nativamente todos los comandos del framework
y delega transparentemente al sistema operativo cuando el comando no es
interno. Soporta CMD, PowerShell, bash y cualquier ejecutable del PATH.

─────────────────────────────────────────────────────────────────────────────
MODO HUMANO (REPL)
─────────────────────────────────────────────────────────────────────────────
    bago shell                      → entra en modo interactivo (REPL)
    bago shell script.cmd             → ejecuta script (.cmd/.bat/.ps1/.py/.sh)
    bago shell -- echo hola mundo     → ejecuta comando del sistema y sale
    bago shell -c "git status"        → alias de -- (ejecuta y sale)

Dentro del REPL:
    bago$ health                    → alias de "bago health"
    bago$ validate                  → alias de "bago validate"
    bago$ ls -la                    → delegado al shell nativo
    bago$ cd proyectos              → cambia directorio (persistente)
    bago$ !!                        → repite último comando
    bago$ !42                       → repite comando #42 del historial
    bago$ !git                      → repite último comando que empiece por "git"
    bago$ history                   → muestra historial
    bago$ exit | quit | q           → sale de la shell
    bago$ bago <cmd>                → prefijo explícito BAGO

─────────────────────────────────────────────────────────────────────────────
MODO AGENTE (API programática)
─────────────────────────────────────────────────────────────────────────────
Desde cualquier módulo de BAGO:

    from bago_shell import BagoShell, ShellResult

    shell = BagoShell(auto_approve=False)   # pide confirmación para peligrosos
    result: ShellResult = shell.run("health", capture_output=True)
    print(result.exit_code, result.stdout)

    result = shell.run("git status", capture_output=True)
    # result: {command, canonical, category, exit_code, stdout, stderr,
    #           authorized, needs_auth, duration_ms, timestamp}

Categorías de riesgo:
    safe       → ejecuta directamente (health, validate, status, ls, git status…)
    caution    → ejecuta pero loguea (sync, cosecha, git add, git commit…)
    dangerous  → bloqueado salvo autorización (rm, del, heal --yes,
                 autonomous --yes, install, db-reset, format, mkfs…)

Variables de entorno:
    BAGO_AUTO_APPROVE=1     → auto-autoriza categoría dangerous
    BAGO_SHELL_DRY_RUN=1    → solo simula, no ejecuta nada
    BAGO_SHELL_LOG_PATH     → ruta del JSONL de auditoría (default state/)

Autorización previa:
    Si un comando dangerous se intenta ejecutar sin BAGO_AUTO_APPROVE,
    la shell devuelve needs_auth=True y NO ejecuta. El agente/orquestador
    debe llamar shell.authorize_once() o shell.authorize_batch(commands)
    antes de reintentar.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ═════════════════════════════════════════════════════════════════════════════
#  Configuración global
# ═════════════════════════════════════════════════════════════════════════════
_USE_COLOR = sys.stdout.isatty()
_AUTO_APPROVE = os.environ.get("BAGO_AUTO_APPROVE", "0") == "1"
_GLOBAL_DRY_RUN = os.environ.get("BAGO_SHELL_DRY_RUN", "0") == "1"


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


CLR_CYAN = lambda t: _c("36", t)
CLR_GREEN = lambda t: _c("32", t)
CLR_YELLOW = lambda t: _c("33", t)
CLR_MAGENTA = lambda t: _c("35", t)
CLR_DIM = lambda t: _c("90", t)
CLR_RED = lambda t: _c("31", t)
CLR_BOLD = lambda t: _c("1", t)


# ── Detección de BAGO_ROOT ──────────────────────────────────────────────────
_script_path = Path(__file__).resolve()
_candidate_roots = [
    _script_path.parents[2] / ".bago",
    _script_path.parents[1] / ".bago",
    Path.home() / ".bago" / "active" / ".bago",
]
BAGO_ROOT: Path | None = None
for cand in _candidate_roots:
    if (cand / "pack.json").exists() or (cand / "tools").exists():
        BAGO_ROOT = cand
        break
if BAGO_ROOT is None:
    BAGO_ROOT = _script_path.parents[2] / ".bago"

TOOLS = BAGO_ROOT / "tools"
CORE = BAGO_ROOT / "core"
REPO_ROOT = BAGO_ROOT.parent
_LAUNCHER_PY = REPO_ROOT / "bago_core" / "launcher.py"

_HISTORY_PATH = BAGO_ROOT / "state" / "shell_history.txt"
_log_dir = BAGO_ROOT / "state"
_log_dir.mkdir(parents=True, exist_ok=True)
_AUTONOMOUS_LOG = Path(os.environ.get("BAGO_SHELL_LOG_PATH", str(_log_dir / "shell_autonomous_log.jsonl")))


# ═════════════════════════════════════════════════════════════════════════════
#  Registro de comandos BAGO
# ═════════════════════════════════════════════════════════════════════════════
_SYSTEM_RESERVED: frozenset[str] = frozenset({
    "git", "python", "python3", "node", "npm", "yarn", "pnpm", "npx",
    "docker", "kubectl", "helm", "terraform", "aws", "az", "gcloud",
    "code", "vim", "vi", "nano", "emacs", "cursor", "subl",
    "make", "cmake", "gcc", "g++", "clang", "rust", "cargo", "go",
    "curl", "wget", "ssh", "scp", "rsync", "ftp", "sftp",
    "tar", "gzip", "gunzip", "zip", "unzip", "7z", "rar",
    "apt", "yum", "dnf", "pacman", "brew", "choco", "winget",
    "ping", "tracert", "traceroute", "netstat", "ipconfig", "ifconfig",
    "nslookup", "dig", "whois", "telnet", "nc", "nmap",
    "find", "grep", "awk", "sed", "cut", "sort", "uniq", "wc", "diff",
    "tail", "head", "less", "more", "watch", "top", "htop", "ps",
    "kill", "killall", "pkill", "pgrep", "jobs", "bg", "fg",
    "systemctl", "service", "journalctl", "crontab", "at",
    "useradd", "usermod", "userdel", "passwd", "chown", "chmod",
    "df", "du", "free", "uptime", "uname", "hostname", "dmesg",
    "lsblk", "fdisk", "parted", "mount", "umount", "mkfs", "fsck",
    "lspci", "lsusb", "lscpu", "lsmem",
})

_BAGO_COMMANDS: set[str] = set()
_BAGO_ALIASES: dict[str, str] = {
    "h": "help", "v": "validate", "s": "status", "l": "launch",
    "n": "next", "d": "done", "st": "stability", "sync": "sync",
    "health": "health", "audit": "audit", "cosecha": "cosecha",
    "ideas": "ideas", "task": "task", "session": "session",
    "registry": "registry", "smoke": "smoke", "stale": "stale",
    "sincerity": "sincerity", "heal": "heal", "cabinet": "cabinet",
    "spiral": "spiral", "autonomous": "autonomous", "siembra": "siembra",
    "wizard": "wizard", "serve": "serve", "dashboard": "dashboard",
    "detector": "detector", "versions": "versions", "extensions": "extensions",
    "setup": "setup", "project": "project", "model": "model", "models": "models",
    "assign": "assign", "agent": "agent", "benchmark": "benchmark",
    "telemetry": "telemetry", "neural": "neural", "npath": "npath",
    "inbox": "inbox", "bot": "bot", "rubber-duck": "rubber-duck",
    "seed": "seed", "validate-goal": "validate-goal", "git-dirty": "git-dirty",
    "encoding": "encoding", "census": "census", "map": "map",
    "prompt-router": "prompt-router", "role-spiral": "role-spiral",
    "model-gate": "model-gate", "token-analytics": "token-analytics",
    "token-brake": "token-brake", "spiral-prompt": "spiral-prompt",
    "splash": "splash", "menu": "menu", "start": "start",
    "shell": "shell", "last": "last", "history": "history", "timeline": "timeline",
    "portable": "portable", "sendnow": "sendnow", "heal-paths": "heal-paths",
    "dev": "dev", "v2": "v2", "workflow": "workflow",
    "efficiency": "efficiency", "seed-ideas": "seed-ideas",
    "report": "report", "learn": "learn", "list": "list",
    "promote": "promote", "deactivate": "deactivate",
    "sprite-studio": "sprite-studio", "image-studio": "image-studio",
    "stats-panel": "stats-panel",
}


# ── Riesgo por categoría ────────────────────────────────────────────────────
_SAFE_BAGO: frozenset[str] = frozenset({
    "help", "status", "validate", "health", "smoke", "stale",
    "sincerity", "audit", "versions", "extensions", "registry",
    "history", "last", "telemetry", "dashboard", "detector",
    "census", "map", "stats-panel", "encoding", "git-dirty",
    "token-analytics", "token-brake", "npath", "neural", "heal-paths",
})

_CAUTION_BAGO: frozenset[str] = frozenset({
    "sync", "cosecha", "ideas", "task", "session", "siembra",
    "setup", "project", "model", "models", "assign", "agent",
    "benchmark", "report", "learn", "list", "promote", "deactivate",
    "sprite-studio", "image-studio", "launch", "menu", "start",
    "splash", "seed-ideas", "rubber-duck", "sendnow", "portable",
    "workflow", "efficiency", "spiral-prompt", "role-spiral",
    "model-gate", "prompt-router", "inbox", "bot", "seed",
    "validate-goal",
})

_DANGEROUS_BAGO: frozenset[str] = frozenset({
    "done", "next", "autonomous", "heal", "cabinet", "spiral",
    "dev", "v2", "serve", "shell", "wizard",
})

# Palabras peligrosas en comandos del sistema
_DANGEROUS_SYSTEM_PATTERNS: tuple[str, ...] = (
    "rm -rf", "rm -fr", "rm -r /", "rm -f /", "del /f /s", "rmdir /s",
    "format ", "mkfs", "dd if=", "> /dev/null", "chmod 777 -R",
    "chown -R", "sudo ", "su -", "curl .*|.*sh", "wget .*|.*sh",
    ":(){ :|:& };:", "> /dev/sda", "mkfs.ext", "mkfs.ntfs",
    "reg delete", "reg add", "shutdown", "restart-computer",
    "stop-computer", "clear-recyclebin", "remove-item -recurse -force",
)


def _load_registry_commands() -> None:
    global _BAGO_COMMANDS
    registry_path = TOOLS / "tool_registry.py"
    fallback = set(_BAGO_ALIASES.values()) | {
        "status", "next", "done", "validate", "health", "audit",
        "cosecha", "ideas", "launch", "task", "session", "stability",
        "sync", "smoke", "stale", "sincerity", "cabinet", "spiral",
        "autonomous", "siembra", "wizard", "serve", "dashboard",
        "detector", "versions", "extensions", "setup", "project",
        "model", "models", "assign", "agent", "benchmark", "telemetry",
        "neural", "npath", "inbox", "bot", "rubber-duck", "seed",
        "validate-goal", "git-dirty", "encoding", "census", "map",
        "prompt-router", "role-spiral", "model-gate", "token-analytics",
        "token-brake", "spiral-prompt", "splash", "menu", "start",
        "shell", "last", "history", "portable", "sendnow",
        "heal-paths", "dev", "v2", "workflow", "efficiency",
        "seed-ideas", "report", "learn", "list", "promote",
        "deactivate", "sprite-studio", "image-studio", "stats-panel",
        "project-init", "project-link", "project-unlink", "project-state",
    }
    if not registry_path.exists():
        _BAGO_COMMANDS = fallback
        return
    try:
        import importlib.util as iu
        spec = iu.spec_from_file_location("_bago_tool_registry_shell", str(registry_path))
        if spec is None:
            _BAGO_COMMANDS = fallback
            return
        mod = iu.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        registry = getattr(mod, "REGISTRY", {})
        _BAGO_COMMANDS = set(registry.keys()) | fallback
    except Exception:
        _BAGO_COMMANDS = fallback


_load_registry_commands()


# ═════════════════════════════════════════════════════════════════════════════
#  Shell nativo del SO
# ═════════════════════════════════════════════════════════════════════════════
_SHELL_SPECIAL = frozenset({"|", "&", ";", "<", ">", "$", "`", "\"", "'", "(", ")", "&&", "||", "2>", ">>", "<<"})


def _get_native_shell() -> tuple[str, list[str]]:
    if sys.platform == "win32":
        shell_env = os.environ.get("SHELL", "")
        msystem = os.environ.get("MSYSTEM", "")
        term = os.environ.get("TERM", "")
        in_posix = msystem or "bash" in shell_env.lower() or "sh" in shell_env.lower() or term.startswith(("xterm", "cygwin"))
        if in_posix:
            bash = shutil.which("bash") or shutil.which("sh") or shell_env or "/bin/sh"
            return (bash, ["-c"])
        pwsh = shutil.which("pwsh") or shutil.which("powershell")
        if pwsh:
            return (pwsh, ["-NoProfile", "-Command"])
        return (shutil.which("cmd") or r"C:\Windows\System32\cmd.exe", ["/c"])
    return (shutil.which("bash") or shutil.which("sh") or "/bin/sh", ["-c"])


_NATIVE_SHELL_EXE, _NATIVE_SHELL_BASE = _get_native_shell()
_IN_POSIX_MODE = sys.platform != "win32" or "bash" in _NATIVE_SHELL_EXE.lower() or "sh" in _NATIVE_SHELL_EXE.lower()


if _IN_POSIX_MODE:
    _SYSTEM_ALIASES: dict[str, list[str]] = {
        "ll": ["ls", "-la"], "la": ["ls", "-a"], "cls": ["clear"],
    }
else:
    _SYSTEM_ALIASES = {
        "dir": ["powershell", "-Command", "Get-ChildItem"],
        "ls":  ["powershell", "-Command", "Get-ChildItem"],
        "cat": ["powershell", "-Command", "Get-Content"],
        "pwd": ["powershell", "-Command", "Get-Location"],
        "clear": ["powershell", "-Command", "Clear-Host"],
        "cls":   ["powershell", "-Command", "Clear-Host"],
        "which": ["powershell", "-Command", "Get-Command"],
        "rm":    ["powershell", "-Command", "Remove-Item"],
        "cp":    ["powershell", "-Command", "Copy-Item"],
        "mv":    ["powershell", "-Command", "Move-Item"],
        "mkdir": ["powershell", "-Command", "New-Item", "-ItemType", "Directory"],
        "touch": ["powershell", "-Command", "New-Item"],
        "ps":    ["powershell", "-Command", "Get-Process"],
        "kill":  ["powershell", "-Command", "Stop-Process"],
        "env":   ["powershell", "-Command", "Get-ChildItem", "Env:"],
    }


# ═════════════════════════════════════════════════════════════════════════════
#  Dataclass de resultado
# ═════════════════════════════════════════════════════════════════════════════
@dataclass
class ShellResult:
    command: str
    canonical: str
    category: str          # "bago_safe" | "bago_caution" | "bago_dangerous" | "system_safe" | "system_caution" | "system_dangerous" | "builtin" | "script"
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    authorized: bool = False
    needs_auth: bool = False
    dry_run: bool = False
    duration_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _expand_system_alias(parts: list[str]) -> list[str] | None:
    """Expande aliases del sistema; devuelve None si no hay alias."""
    if not parts:
        return None
    head = parts[0].lower()
    if head in _SYSTEM_ALIASES:
        return _SYSTEM_ALIASES[head] + parts[1:]
    return None


# ═════════════════════════════════════════════════════════════════════════════
#  BagoShell — motor principal (humano + agente)
# ═════════════════════════════════════════════════════════════════════════════
class BagoShell:
    """Shell de ejecución dual: REPL para humanos, API para agentes."""

    def __init__(
        self,
        *,
        auto_approve: bool | None = None,
        dangerous_requires_confirm: bool = True,
        dry_run: bool | None = None,
        log_path: Path | None = None,
        cwd: Path | None = None,
    ):
        self.auto_approve = _AUTO_APPROVE if auto_approve is None else auto_approve
        self.dangerous_requires_confirm = dangerous_requires_confirm
        self.dry_run = _GLOBAL_DRY_RUN if dry_run is None else dry_run
        self.log_path = log_path or _AUTONOMOUS_LOG
        self.cwd = cwd or Path.cwd()
        self._history: list[str] = []
        self._load_history()
        self._auth_cache: set[str] = set()  # líneas autorizadas manualmente

    # ── Historial ──────────────────────────────────────────────────────────
    def _load_history(self) -> None:
        if _HISTORY_PATH.exists():
            try:
                self._history = [l.rstrip("\n") for l in _HISTORY_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
            except Exception:
                self._history = []
        else:
            self._history = []

    def _save_history(self) -> None:
        try:
            _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
            trimmed = self._history[-5000:]
            _HISTORY_PATH.write_text("\n".join(trimmed) + "\n", encoding="utf-8")
        except Exception:
            pass

    def _append_history(self, line: str) -> None:
        if line.strip() and (not self._history or self._history[-1] != line.strip()):
            self._history.append(line.strip())

    # ── Autorización ───────────────────────────────────────────────────────
    def authorize_once(self, line: str) -> None:
        """Autoriza una línea dangerous para la próxima ejecución."""
        self._auth_cache.add(line.strip())

    def authorize_batch(self, lines: list[str]) -> None:
        """Autoriza múltiples líneas."""
        for line in lines:
            self._auth_cache.add(line.strip())

    def revoke_authorization(self, line: str | None = None) -> None:
        """Revoca autorización. Si line=None, limpia todo."""
        if line is None:
            self._auth_cache.clear()
        else:
            self._auth_cache.discard(line.strip())

    # ── Categorización de riesgo ───────────────────────────────────────────
    def _classify(self, parts: list[str]) -> tuple[str, str, list[str]]:
        """Devuelve (categoría, cmd_canónico, args_resto).

        Categorías:
          bago_safe / bago_caution / bago_dangerous
          system_safe / system_caution / system_dangerous
          builtin / script / unknown
        """
        if not parts:
            return ("unknown", "", [])

        head = parts[0].lower()

        # Built-ins
        if head in ("cd", "exit", "quit", "q", "history", "help-shell", "h?", "bago-help"):
            return ("builtin", head, parts[1:])

        # Scripts por extensión
        p = Path(parts[0]).expanduser()
        if p.suffix.lower() in (".cmd", ".bat", ".ps1", ".py", ".sh") and p.exists():
            return ("script", str(p), parts[1:])

        # Prefijo explícito bago
        explicit = head == "bago" and len(parts) >= 2
        candidate = parts[1].lower() if explicit else head
        rest = parts[2:] if explicit else parts[1:]

        # Alias BAGO
        canonical = _BAGO_ALIASES.get(candidate, candidate)

        # Si es un comando reservado del sistema y NO hay prefijo "bago",
        # forzar clasificación como sistema (no BAGO)
        if not explicit and candidate in _SYSTEM_RESERVED:
            line = " ".join(parts)
            low = line.lower()
            for pat in _DANGEROUS_SYSTEM_PATTERNS:
                if pat.lower() in low:
                    return ("system_dangerous", candidate, parts)
            if candidate in ("rm", "del", "rmdir", "format", "fdisk", "mkfs", "dd", "shutdown", "restart-computer"):
                return ("system_dangerous", head, parts[1:])
            if candidate in ("sudo", "su"):
                return ("system_dangerous", head, parts[1:])
            return ("system_safe", candidate, parts[1:])

        if canonical in _BAGO_COMMANDS or candidate in _BAGO_COMMANDS:
            if canonical in _DANGEROUS_BAGO or candidate in _DANGEROUS_BAGO:
                return ("bago_dangerous", canonical, rest)
            if canonical in _CAUTION_BAGO or candidate in _CAUTION_BAGO:
                return ("bago_caution", canonical, rest)
            return ("bago_safe", canonical, rest)

        # Comando del sistema
        line = " ".join(parts)
        low = line.lower()
        for pat in _DANGEROUS_SYSTEM_PATTERNS:
            if pat.lower() in low:
                return ("system_dangerous", candidate, parts)

        # Heurísticas de riesgo sistema
        if head in ("rm", "del", "rmdir", "format", "fdisk", "mkfs", "dd", "shutdown", "restart-computer"):
            return ("system_dangerous", head, parts[1:])
        if head in ("sudo", "su"):
            return ("system_dangerous", head, parts[1:])

        return ("system_safe", head, parts[1:])

    # ── Ejecución ──────────────────────────────────────────────────────────
    def _run_bago(self, cmd: str, args: list[str], capture_output: bool) -> ShellResult:
        if not _LAUNCHER_PY.exists():
            return ShellResult(command=cmd, canonical=cmd, category="bago_safe", exit_code=1, error=f"launcher.py no encontrado: {_LAUNCHER_PY}")
        cmdline = [sys.executable, str(_LAUNCHER_PY), cmd] + args
        t0 = time.monotonic()
        try:
            if capture_output:
                proc = subprocess.run(cmdline, cwd=str(self.cwd), capture_output=True, text=True, encoding="utf-8", errors="replace")
            else:
                proc = subprocess.run(cmdline, cwd=str(self.cwd))
            dur = (time.monotonic() - t0) * 1000
            return ShellResult(
                command=cmd,
                canonical=cmd,
                category="bago_safe",
                exit_code=proc.returncode,
                stdout=proc.stdout if capture_output else "",
                stderr=proc.stderr if capture_output else "",
                authorized=True,
                duration_ms=dur,
            )
        except Exception as exc:
            return ShellResult(command=cmd, canonical=cmd, category="bago_safe", exit_code=1, error=str(exc))

    def _run_system(self, line: str, capture_output: bool) -> ShellResult:
        shell_exe, shell_base = _get_native_shell()
        t0 = time.monotonic()
        try:
            if sys.platform == "win32" and "powershell" in shell_exe.lower():
                cmdline = [shell_exe, "-NoProfile", "-Command", line]
            elif sys.platform == "win32" and "cmd" in shell_exe.lower():
                cmdline = [shell_exe, "/c", line]
            else:
                cmdline = [shell_exe] + shell_base + [line]

            if capture_output:
                proc = subprocess.run(cmdline, cwd=str(self.cwd), capture_output=True, text=True, encoding="utf-8", errors="replace")
            else:
                proc = subprocess.run(cmdline, cwd=str(self.cwd))
            dur = (time.monotonic() - t0) * 1000
            return ShellResult(
                command=line,
                canonical=line.split()[0],
                category="system_safe",
                exit_code=proc.returncode,
                stdout=proc.stdout if capture_output else "",
                stderr=proc.stderr if capture_output else "",
                authorized=True,
                duration_ms=dur,
            )
        except Exception as exc:
            return ShellResult(command=line, canonical=line.split()[0] if line else "", category="system_safe", exit_code=1, error=str(exc))

    def _run_builtin(self, head: str, args: list[str]) -> ShellResult:
        if head in ("exit", "quit", "q"):
            return ShellResult(command=head, canonical=head, category="builtin", exit_code=0, stdout="  👋 Shell cerrada.")
        if head == "cd":
            target = args[0] if args else str(Path.home())
            if target == "~":
                target = str(Path.home())
            elif target == "-":
                target = os.environ.get("BAGO_SHELL_OLDPWD", str(Path.home()))
            try:
                old = str(self.cwd)
                os.chdir(target)
                self.cwd = Path.cwd()
                os.environ["BAGO_SHELL_OLDPWD"] = old
                return ShellResult(command=f"cd {target}", canonical="cd", category="builtin", exit_code=0)
            except Exception as exc:
                return ShellResult(command=f"cd {target}", canonical="cd", category="builtin", exit_code=1, error=str(exc))
        if head == "history":
            if not self._history:
                return ShellResult(command="history", canonical="history", category="builtin", exit_code=0, stdout="  (historial vacío)")
            start = max(0, len(self._history) - 50)
            out = "\n".join(f"  {'→' if i == len(self._history) else ' '} {i:4d}  {h}" for i, h in enumerate(self._history[start:], start=start + 1))
            return ShellResult(command="history", canonical="history", category="builtin", exit_code=0, stdout=out)
        if head in ("help-shell", "h?", "bago-help"):
            return ShellResult(command=head, canonical="help-shell", category="builtin", exit_code=0, stdout=_help_text())
        return ShellResult(command=head, canonical=head, category="builtin", exit_code=1, error="builtin desconocido")

    def _run_script(self, path: Path, args: list[str], capture_output: bool) -> ShellResult:
        ext = path.suffix.lower()
        if ext in (".cmd", ".bat"):
            cmdline = ["cmd", "/c", str(path)] + args
        elif ext == ".ps1":
            pwsh = shutil.which("pwsh") or shutil.which("powershell")
            if not pwsh:
                return ShellResult(command=str(path), canonical=str(path), category="script", exit_code=1, error="PowerShell no encontrado")
            cmdline = [pwsh, "-ExecutionPolicy", "Bypass", "-File", str(path)] + args
        elif ext == ".py":
            cmdline = [sys.executable, str(path)] + args
        elif ext == ".sh":
            bash = shutil.which("bash") or shutil.which("sh")
            if not bash:
                return ShellResult(command=str(path), canonical=str(path), category="script", exit_code=1, error="bash no encontrado")
            cmdline = [bash, str(path)] + args
        else:
            cmdline = [str(path)] + args
        t0 = time.monotonic()
        try:
            if capture_output:
                proc = subprocess.run(cmdline, cwd=str(self.cwd), capture_output=True, text=True, encoding="utf-8", errors="replace")
            else:
                proc = subprocess.run(cmdline, cwd=str(self.cwd))
            dur = (time.monotonic() - t0) * 1000
            return ShellResult(
                command=str(path),
                canonical=str(path),
                category="script",
                exit_code=proc.returncode,
                stdout=proc.stdout if capture_output else "",
                stderr=proc.stderr if capture_output else "",
                authorized=True,
                duration_ms=dur,
            )
        except Exception as exc:
            return ShellResult(command=str(path), canonical=str(path), category="script", exit_code=1, error=str(exc))

    # ── Logging ────────────────────────────────────────────────────────────
    def _log(self, result: ShellResult) -> None:
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(result.to_dict(), ensure_ascii=False, default=str) + "\n")
        except Exception:
            pass

    # ── API pública: run ───────────────────────────────────────────────────
    def run(self, line: str, *, capture_output: bool = False, dry_run: bool | None = None) -> ShellResult:
        """Ejecuta una línea de comando con clasificación de riesgo y autorización.

        Args:
            line: comando a ejecutar.
            capture_output: si True, captura stdout/stderr (modo agente).
            dry_run: si True, solo simula sin ejecutar.

        Returns:
            ShellResult con toda la metadata de la ejecución.
        """
        _dry = self.dry_run if dry_run is None else dry_run
        raw = line.strip()
        if not raw:
            return ShellResult(command="", canonical="", category="unknown", exit_code=0, error="comando vacío")

        self._append_history(raw)

        # Bang history (solo interactivo; en API no tiene sentido)
        # Se salta aquí

        parts = raw.split()

        # Expandir aliases del sistema (ej: ll → ls -la)
        expanded_parts = _expand_system_alias(parts)
        if expanded_parts is not None:
            parts = expanded_parts
            raw = " ".join(parts)

        category, canonical, args = self._classify(parts)

        # Evaluar riesgo y autorización
        needs_auth = category in ("bago_dangerous", "system_dangerous")
        authorized = not needs_auth
        if needs_auth:
            if self.auto_approve or raw.strip() in self._auth_cache:
                authorized = True
            else:
                # Dry-run implícito: devolvemos resultado sin ejecutar
                result = ShellResult(
                    command=raw,
                    canonical=canonical,
                    category=category,
                    exit_code=1,
                    authorized=False,
                    needs_auth=True,
                    dry_run=True,
                    error=f"Comando peligroso requiere autorización: {raw}",
                )
                self._log(result)
                return result

        if _dry:
            result = ShellResult(
                command=raw,
                canonical=canonical,
                category=category,
                exit_code=0,
                authorized=authorized,
                needs_auth=needs_auth,
                dry_run=True,
                stdout=f"[DRY-RUN] Se ejecutaría: {raw}  (cat={category})",
            )
            self._log(result)
            return result

        # Ejecutar según categoría
        if category == "builtin":
            result = self._run_builtin(canonical, args)
        elif category == "script":
            result = self._run_script(Path(canonical), args, capture_output)
        elif category.startswith("bago_"):
            result = self._run_bago(canonical, args, capture_output)
        else:
            result = self._run_system(raw, capture_output)

        result.category = category
        result.command = raw
        result.canonical = canonical
        result.authorized = authorized
        result.needs_auth = needs_auth
        self._log(result)
        return result

    def run_batch(self, lines: list[str], *, capture_output: bool = True) -> list[ShellResult]:
        """Ejecuta múltiples comandos secuencialmente."""
        results: list[ShellResult] = []
        for line in lines:
            results.append(self.run(line, capture_output=capture_output))
            # Si un comando falla críticamente, paramos
            if results[-1].exit_code != 0 and results[-1].needs_auth:
                break
        return results

    # ── REPL para humanos ──────────────────────────────────────────────────
    def repl(self) -> int:
        """Modo interactivo humano."""
        banner_py = TOOLS / "bago_banner.py"
        if banner_py.exists() and _USE_COLOR:
            try:
                subprocess.run([sys.executable, str(banner_py), "--mini"], cwd=str(REPO_ROOT), capture_output=True)
            except Exception:
                pass
        print()
        print(CLR_CYAN("  🐚 BAGO Interactive Shell (BISH) — 'exit' para salir, 'help-shell' para ayuda"))
        if self.auto_approve:
            print(CLR_YELLOW("  ⚠️  Modo AUTO-APPROVE activo — comandos peligrosos se ejecutan sin confirmación"))
        if self.dry_run:
            print(CLR_YELLOW("  ⚠️  Modo DRY-RUN activo — nada se ejecuta realmente"))
        print()

        exit_code = 0
        while True:
            try:
                line = input(_prompt(self.cwd))
            except (EOFError, KeyboardInterrupt):
                print("\n  👋 Shell cerrada.")
                break

            raw = line.strip()
            if not raw:
                continue

            # Bang history
            expanded = _history_replay(raw, self._history)
            if expanded is not None:
                if not expanded:
                    continue
                raw = expanded
                print(f"  {CLR_DIM('→')} {raw}")

            self._append_history(raw)
            head = raw.split()[0].lower()
            if head in ("exit", "quit", "q"):
                print("  👋 Shell cerrada.")
                break

            result = self.run(raw, capture_output=False)
            if result.needs_auth and not result.authorized:
                print(CLR_YELLOW(f"  ⚠️  COMANDO BLOQUEADO (requiere autorización): {raw}"))
                print(CLR_DIM(f"      Categoría: {result.category}"))
                print(CLR_DIM("      Usa shell.authorize_once() desde API, o BAGO_AUTO_APPROVE=1"))
            elif result.error and result.exit_code != 0:
                print(CLR_RED(f"  [ERROR {result.exit_code}] {result.error}"))
            exit_code = result.exit_code

        self._save_history()
        return exit_code


# ═════════════════════════════════════════════════════════════════════════════
#  Helpers estáticos (prompt, historial bang, ayuda)
# ═════════════════════════════════════════════════════════════════════════════
def _git_branch() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=1.0,
        )
        if result.returncode == 0:
            b = result.stdout.strip()
            return b if b != "HEAD" else None
    except Exception:
        pass
    return None


def _prompt(cwd: Path) -> str:
    try:
        rel = cwd.relative_to(REPO_ROOT)
        display = f"~/{rel}" if str(rel) != "." else "~"
    except ValueError:
        display = str(cwd)
        if sys.platform == "win32" and len(display) > 2 and display[1] == ":":
            display = display[0].upper() + display[1:]

    parts = [CLR_CYAN("🅱 "), CLR_DIM(display)]
    branch = _git_branch()
    if branch:
        parts.append(CLR_MAGENTA(f" [{branch}]"))
    parts.extend([CLR_GREEN(" bago$"), " "])
    return "".join(parts)


def _history_replay(line: str, history: list[str]) -> str | None:
    if not line.startswith("!"):
        return None
    if line == "!!":
        if not history:
            print("  (historial vacío)")
            return ""
        return history[-1]
    inner = line[1:]
    if inner.isdigit():
        idx = int(inner) - 1
        if 0 <= idx < len(history):
            return history[idx]
        print(f"  !{inner}: fuera de rango (1–{len(history)})")
        return ""
    for h in reversed(history):
        if h.startswith(inner):
            return h
    print(f"  !{inner}: no encontrado en historial")
    return ""


def _help_text() -> str:
    aliases = "\n".join(f"    {k:10s} → {' '.join(v)}" for k, v in sorted(_SYSTEM_ALIASES.items()))
    return (
        "\n"
        "  ┌─────────────────────────────────────────────────────────────┐\n"
        "  │  🐚 BAGO Interactive Shell (BISH) — Ayuda rápida            │\n"
        "  └─────────────────────────────────────────────────────────────┘\n"
        "\n"
        "  Comandos BAGO (nativos):\n"
        "    Cualquier comando registrado de BAGO funciona directamente.\n"
        "    Ejemplos: health, validate, status, launch, next, done, sync,\n"
        "              audit, cosecha, ideas, task, session, registry...\n"
        "\n"
        "  Comandos del sistema:\n"
        "    Todo lo demás se delega al shell nativo (PowerShell / bash).\n"
        "    Soporta pipes (|), redirecciones (>, >>, <, 2>), &&, ||.\n"
        "\n"
        "  Built-ins de BISH:\n"
        "    cd <dir> | ~ | .. | ... | -     cambiar directorio\n"
        "    exit | quit | q                  salir de la shell\n"
        "    history                          últimos 50 comandos\n"
        "    !!<cmd>                          repetir último comando\n"
        "    !n                               repetir comando número n\n"
        "    !prefix                          repetir último comando con prefix\n"
        "    help-shell | h? | bago-help      mostrar esta ayuda\n"
        "\n"
        "  Aliases del sistema:\n"
        f"{aliases}\n"
    )


# ═════════════════════════════════════════════════════════════════════════════
#  Entrypoints CLI
# ═════════════════════════════════════════════════════════════════════════════
def run_script(path_str: str) -> int:
    p = Path(path_str).expanduser().resolve()
    if not p.exists():
        print(CLR_RED(f"  [ERROR] No existe: {p}"))
        return 1
    shell = BagoShell()
    r = shell._run_script(p, [], capture_output=False)
    if r.error:
        print(CLR_RED(f"  [ERROR] {r.error}"))
    return r.exit_code


def run_command(args: list[str]) -> int:
    shell = BagoShell()
    if not args:
        return shell.repl()

    first = args[0]
    if first in ("--", "-c"):
        r = shell.run(" ".join(args[1:]), capture_output=False)
        return r.exit_code

    p = Path(first).expanduser().resolve()
    if p.exists() and p.suffix.lower() in (".cmd", ".bat", ".ps1", ".py", ".sh"):
        r = shell._run_script(p, args[1:], capture_output=False)
        return r.exit_code

    r = shell.run(" ".join(args), capture_output=False)
    if r.needs_auth and not r.authorized:
        print(CLR_YELLOW(f"  ⚠️  Bloqueado (requiere autorización): {' '.join(args)}"))
    return r.exit_code


def main() -> int:
    args = sys.argv[1:]
    return run_command(args)


# ═════════════════════════════════════════════════════════════════════════════
#  Self-test
# ═════════════════════════════════════════════════════════════════════════════
def _self_test() -> str | None:
    errors: list[str] = []
    if BAGO_ROOT is None or not BAGO_ROOT.exists():
        errors.append("BAGO_ROOT no resuelto")
    try:
        shell = BagoShell()
    except Exception as e:
        errors.append(f"instancia: {e}")
        return "FAIL: " + "; ".join(errors)

    # 1. classify bago safe
    cat, can, _ = shell._classify(["health"])
    if cat != "bago_safe":
        errors.append(f"classify health={cat} (esperado bago_safe)")

    # 2. classify bago dangerous
    cat, can, _ = shell._classify(["autonomous"])
    if cat != "bago_dangerous":
        errors.append(f"classify autonomous={cat} (esperado bago_dangerous)")

    # 3. classify system dangerous
    cat, can, _ = shell._classify(["rm", "-rf", "/tmp"])
    if cat != "system_dangerous":
        errors.append(f"classify rm={cat} (esperado system_dangerous)")

    # 4. dry-run devuelve sin ejecutar
    r = shell.run("autonomous", dry_run=True, capture_output=True)
    if not r.dry_run or r.authorized:
        errors.append("dry_run no funciona para dangerous")

    # 5. safe ejecuta realmente
    r = shell.run("validate", capture_output=True)
    if r.exit_code != 0:
        errors.append(f"validate falló: {r.error}")

    # 6. system safe
    r = shell.run("echo test_bago_shell", capture_output=True)
    if "test_bago_shell" not in r.stdout:
        errors.append(f"echo no capturado: {r.stdout!r}")

    # 7. builtin cd
    old = str(Path.cwd())
    r = shell.run("cd ..", capture_output=True)
    if r.exit_code != 0:
        errors.append(f"cd falló: {r.error}")
    os.chdir(old)

    if errors:
        return "FAIL: " + "; ".join(errors)
    return None


if __name__ == "__main__":
    if "--test" in sys.argv:
        result = _self_test()
        if result:
            print(CLR_RED(f"  {result}"))
            raise SystemExit(1)
        print(CLR_GREEN("  Self-test OK"))
        raise SystemExit(0)
    raise SystemExit(main())
