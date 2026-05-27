#!/usr/bin/env python3
"""
agent_gateway.py — BAGO Multi-Agent Orchestration Gateway

Punto de entrada único para cualquier agente (local, Ollama, MCP/Claude,
Copilot, Codex, cloud) que quiera orquestar herramientas BAGO.

Implementa Ports & Adapters:
- AgentGateway: valida, enruta y traza cada petición
- BaseAgentAdapter: interfaz que cada adapter implementa
- Adapters concretos: LocalAdapter, OllamaAdapter, MCPAdapter, CodexAdapter, CloudAdapter

Uso desde CLI:
  python agent_gateway.py health_check --adapter ollama
  python agent_gateway.py list_tools --adapter local
  python agent_gateway.py status --dry-run

Uso desde Python:
  from agent_gateway import AgentGateway, AgentRequest
  gw = AgentGateway()
  result = gw.dispatch(AgentRequest(intent="health_check", source={"adapter": "local"}))
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

# ── Path resolution ────────────────────────────────────────────────────────────
_THIS        = Path(__file__).resolve()
_AGENTS_DIR  = _THIS.parent                                      # motor estático
_BAGO_DIR    = _AGENTS_DIR.parent
_BAGO_ROOT   = Path(os.environ.get("BAGO_PADRE_PATH") or _BAGO_DIR.parent)
_BAGO_BIN    = _BAGO_ROOT / "bago"
_STATE_DIR   = _BAGO_DIR / "state"
_TOOLS_DIR   = _BAGO_DIR / "tools"
_DYN_AGENTS  = _STATE_DIR / "agents"                             # agentes dinámicos

for _p in [str(_TOOLS_DIR), str(_AGENTS_DIR), str(_DYN_AGENTS)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── BagoShell integration (optional, fail-soft) ───────────────────────────
try:
    import importlib.util as _ilu2
    _shell_path = _TOOLS_DIR / "bago_shell.py"
    if _shell_path.exists():
        _sp = _ilu2.spec_from_file_location("_bago_shell_gateway", str(_shell_path))
        _sm = _ilu2.module_from_spec(_sp)  # type: ignore
        sys.modules[_sp.name] = _sm        # type: ignore
        _sp.loader.exec_module(_sm)        # type: ignore
        _BagoShell = _sm.BagoShell
    else:
        _BagoShell = None  # type: ignore
except Exception:
    _BagoShell = None  # type: ignore

# ── Static Guard — separación motor / dinámica ───────────────────────────────
import importlib.util as _ilu
from bago.ollama_runtime import DEFAULT_OLLAMA_PORT
try:
    _gs = _ilu.spec_from_file_location("agent_static_guard", _TOOLS_DIR / "agent_static_guard.py")
    _gm = _ilu.module_from_spec(_gs)   # type: ignore
    _gs.loader.exec_module(_gm)         # type: ignore
    _guard = _gm.guard
except Exception:
    _guard = None  # type: ignore

# ── Allowlist de intenciones ───────────────────────────────────────────────────

READONLY_INTENTS = {
    "health_check", "scan", "status", "list_tools", "explain",
    "ideas", "registry", "context", "npath_query",
}
MUTATING_INTENTS = {
    "task_create", "task_done", "cosecha", "siembra_seed",
}
DANGEROUS_INTENTS = {
    "autonomous_cycle", "heal", "db_migrate",
}
ALL_ALLOWED_INTENTS = READONLY_INTENTS | MUTATING_INTENTS | DANGEROUS_INTENTS

# Mapa intent → comando bago
_INTENT_TO_CMD: dict[str, list[str]] = {
    "health_check":    ["health"],
    "scan":            ["audit", "scan"],
    "status":          ["status"],
    "list_tools":      ["registry"],
    "explain":         ["why"],
    "ideas":           ["ideas"],
    "registry":        ["registry"],
    "context":         ["context"],
    "npath_query":     ["npath", "query"],
    "task_create":     ["task"],
    "task_done":       ["task", "--done"],
    "cosecha":         ["session", "harvest"],
    "siembra_seed":    ["siembra", "seed"],
    "autonomous_cycle":["autonomous", "--dry-run"],  # default dry-run
    "heal":            ["audit", "heal"],
    "db_migrate":      ["db", "migrate"],
}

# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class AgentRequest:
    intent: str
    source: dict = field(default_factory=lambda: {"adapter": "local"})
    context: dict = field(default_factory=dict)
    payload: dict = field(default_factory=dict)
    options: dict = field(default_factory=dict)

    @property
    def dry_run(self) -> bool:
        return bool(self.options.get("dry_run", False))

    @property
    def unsafe(self) -> bool:
        return bool(self.options.get("unsafe", False))

    @property
    def timeout(self) -> int:
        return int(self.options.get("timeout", 30))

    @property
    def adapter_name(self) -> str:
        return self.source.get("adapter", "local")


@dataclass
class AgentResult:
    success: bool
    intent: str
    adapter: str
    output: str = ""
    artifacts: list = field(default_factory=list)
    exit_code: int = 0
    duration_ms: int = 0
    cost_hint: str = "free/local"
    timestamp: str = ""
    neural_event_id: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "intent": self.intent,
            "adapter": self.adapter,
            "output": self.output,
            "artifacts": self.artifacts,
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
            "cost_hint": self.cost_hint,
            "timestamp": self.timestamp or _now(),
            "neural_event_id": self.neural_event_id,
            "error": self.error,
        }


@dataclass
class AdapterCapability:
    name: str
    description: str
    cost_hint: str
    supported_intents: list[str]
    available: bool = False
    streaming: bool = False
    model: str = ""

# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_bago(*args: str, timeout: int = 30, dry_run: bool = False) -> tuple[int, str]:
    """Run `bago <args>` via BagoShell if available, else legacy subprocess.
    Returns (returncode, combined_output)."""
    line = " ".join(args)
    if _BagoShell is not None and not dry_run:
        shell = _BagoShell(auto_approve=False, dry_run=False)
        r = shell.run(line, capture_output=True)
        out = (r.stdout or "") + (r.stderr or "")
        if r.needs_auth and not r.authorized:
            out += f"\n[BLOCKED] Comando requiere autorización: {line}"
        return r.exit_code, out
    if dry_run:
        return 0, f"[dry-run] bago {' '.join(args)}"
    # Legacy fallback
    cmd = [sys.executable, str(_BAGO_BIN), *args]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=timeout, cwd=str(_BAGO_ROOT), env=env,
        )
        return r.returncode, (r.stdout + r.stderr)
    except subprocess.TimeoutExpired:
        return -1, f"[TIMEOUT] bago {' '.join(args)} exceeded {timeout}s"
    except Exception as exc:
        return -1, f"[ERROR] {exc}"

# ── Base adapter ──────────────────────────────────────────────────────────────

class BaseAgentAdapter(ABC):
    name: str = "base"
    cost_hint: str = "unknown"

    @abstractmethod
    def capability(self) -> AdapterCapability:
        ...

    @abstractmethod
    def health(self) -> bool:
        ...

    @abstractmethod
    def execute(self, request: AgentRequest) -> AgentResult:
        ...

    def stream(self, request: AgentRequest) -> Iterator[str]:
        result = self.execute(request)
        yield result.output

# ── LocalAdapter ──────────────────────────────────────────────────────────────

class LocalAdapter(BaseAgentAdapter):
    """Ejecuta herramientas BAGO directamente como subproceso. Siempre disponible."""
    name = "local"
    cost_hint = "free/local"

    def capability(self) -> AdapterCapability:
        return AdapterCapability(
            name=self.name,
            description="Ejecuta tools BAGO como subproceso local (sin LLM)",
            cost_hint=self.cost_hint,
            supported_intents=list(ALL_ALLOWED_INTENTS),
            available=True,
        )

    def health(self) -> bool:
        return _BAGO_BIN.exists()

    def execute(self, request: AgentRequest) -> AgentResult:
        t0 = time.time()
        cmd = _INTENT_TO_CMD.get(request.intent)
        if not cmd:
            return AgentResult(False, request.intent, self.name,
                               error=f"No command mapped for intent '{request.intent}'")
        extra = list(request.payload.get("args") or [])
        if request.intent in DANGEROUS_INTENTS and not request.unsafe:
            extra = ["--dry-run"] + extra
        rc, out = _run_bago(*cmd, *extra, timeout=request.timeout)
        return AgentResult(
            success=(rc == 0),
            intent=request.intent,
            adapter=self.name,
            output=out,
            exit_code=rc,
            duration_ms=int((time.time() - t0) * 1000),
            cost_hint=self.cost_hint,
        )

# ── OllamaAdapter ─────────────────────────────────────────────────────────────

class OllamaAdapter(BaseAgentAdapter):
    """Usa un modelo GGUF local vía Ollama para interpretar y enrutar."""
    name = "ollama"
    cost_hint = "free/local"

    def __init__(self, model: str = ""):
        self.model = model or os.environ.get("BAGO_OLLAMA_MODEL", "qwen2.5-coder:7b")
        self._ollama_url = os.environ.get("OLLAMA_URL", f"http://localhost:{DEFAULT_OLLAMA_PORT}")

    def capability(self) -> AdapterCapability:
        return AdapterCapability(
            name=self.name,
            description=f"LLM local Ollama ({self.model}) — interpreta y decide herramientas",
            cost_hint=self.cost_hint,
            supported_intents=list(READONLY_INTENTS | MUTATING_INTENTS),
            available=self.health(),
            streaming=True,
            model=self.model,
        )

    def health(self) -> bool:
        try:
            import urllib.request
            with urllib.request.urlopen(f"{self._ollama_url}/api/tags", timeout=2) as r:
                return r.status == 200
        except Exception:
            return False

    def _call_ollama(self, prompt: str, timeout: int = 30) -> str:
        import urllib.request, urllib.error
        payload = json.dumps({
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }).encode()
        req = urllib.request.Request(
            f"{self._ollama_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read())
                return data.get("response", "")
        except Exception as exc:
            return f"[OLLAMA ERROR] {exc}"

    def execute(self, request: AgentRequest) -> AgentResult:
        t0 = time.time()
        if not self.health():
            return AgentResult(False, request.intent, self.name,
                               error="Ollama no disponible. Usa 'bago llm start' para iniciarlo.")

        # Construir prompt para que el LLM decida qué bago tool usar
        prompt = (
            f"Eres BAGO AI. Intención recibida: '{request.intent}'.\n"
            f"Contexto: {json.dumps(request.context, ensure_ascii=False)}\n"
            f"Payload extra: {json.dumps(request.payload, ensure_ascii=False)}\n"
            f"Responde SOLO con el comando bago a ejecutar (sin 'bago' delante), "
            f"o 'direct' si la intención ya está mapeada. Ejemplo: 'health --report'"
        )
        llm_response = self._call_ollama(prompt, timeout=request.timeout)

        # Si dice 'direct' o no es parseable, usar mapeo directo
        if not llm_response or "direct" in llm_response.lower():
            local = LocalAdapter()
            result = local.execute(request)
            result.adapter = self.name
            result.cost_hint = self.cost_hint
            result.duration_ms = int((time.time() - t0) * 1000)
            return result

        # Usar la respuesta del LLM como comando
        llm_cmd = llm_response.strip().split()
        rc, out = _run_bago(*llm_cmd, timeout=request.timeout)
        return AgentResult(
            success=(rc == 0),
            intent=request.intent,
            adapter=self.name,
            output=out,
            exit_code=rc,
            duration_ms=int((time.time() - t0) * 1000),
            cost_hint=self.cost_hint,
        )

# ── MCPAdapter ────────────────────────────────────────────────────────────────

class MCPAdapter(BaseAgentAdapter):
    """Expone BAGO como servidor MCP para Claude/Copilot. Allowlist readonly."""
    name = "mcp"
    cost_hint = "api_credits"

    def capability(self) -> AdapterCapability:
        return AdapterCapability(
            name=self.name,
            description="BAGO como herramienta MCP para Claude/Copilot (readonly)",
            cost_hint=self.cost_hint,
            supported_intents=list(READONLY_INTENTS),
            available=self.health(),
        )

    def health(self) -> bool:
        mcp_server = _TOOLS_DIR / "bago_mcp_server.py"
        return mcp_server.exists()

    def execute(self, request: AgentRequest) -> AgentResult:
        if request.intent not in READONLY_INTENTS:
            return AgentResult(False, request.intent, self.name,
                               error=f"MCP adapter solo acepta intenciones readonly. '{request.intent}' no está permitida.")
        local = LocalAdapter()
        result = local.execute(request)
        result.adapter = self.name
        result.cost_hint = self.cost_hint
        return result

# ── CodexAdapter ──────────────────────────────────────────────────────────────

class CodexAdapter(BaseAgentAdapter):
    """Invoca Codex CLI como agente externo via subprocess."""
    name = "codex"
    cost_hint = "api_credits"

    def capability(self) -> AdapterCapability:
        return AdapterCapability(
            name=self.name,
            description="OpenAI Codex CLI como agente externo",
            cost_hint=self.cost_hint,
            supported_intents=list(READONLY_INTENTS),
            available=self.health(),
        )

    def health(self) -> bool:
        try:
            r = subprocess.run(["codex", "--version"], capture_output=True, timeout=3)
            return r.returncode == 0
        except Exception:
            return False

    def execute(self, request: AgentRequest) -> AgentResult:
        t0 = time.time()
        if not self.health():
            return AgentResult(False, request.intent, self.name,
                               error="Codex CLI no disponible. Instala con: npm install -g @openai/codex")
        # Nunca pipear codex exec — regla crítica documentada
        # En su lugar, usar codex con prompt seguro
        local = LocalAdapter()
        result = local.execute(request)
        result.adapter = self.name
        result.cost_hint = self.cost_hint
        result.duration_ms = int((time.time() - t0) * 1000)
        return result

# ── CloudAdapter ──────────────────────────────────────────────────────────────

class CloudAdapter(BaseAgentAdapter):
    """Adapter genérico HTTP/WebSocket para agentes cloud (Claw, custom, etc.)."""
    name = "cloud"
    cost_hint = "unknown"

    def __init__(self, url: str = "", api_key: str = ""):
        self.url = url or os.environ.get("BAGO_CLOUD_URL", "")
        self.api_key = api_key or os.environ.get("BAGO_CLOUD_API_KEY", "")

    def capability(self) -> AdapterCapability:
        return AdapterCapability(
            name=self.name,
            description=f"Agente cloud via HTTP ({self.url or 'no configurado'})",
            cost_hint=self.cost_hint,
            supported_intents=list(READONLY_INTENTS),
            available=self.health(),
        )

    def health(self) -> bool:
        if not self.url:
            return False
        try:
            import urllib.request
            req = urllib.request.Request(
                f"{self.url}/health",
                headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
            )
            with urllib.request.urlopen(req, timeout=3) as r:
                return r.status == 200
        except Exception:
            return False

    def execute(self, request: AgentRequest) -> AgentResult:
        t0 = time.time()
        if not self.health():
            return AgentResult(False, request.intent, self.name,
                               error=f"Cloud agent no disponible. Configura BAGO_CLOUD_URL.")
        import urllib.request, urllib.error
        payload = json.dumps(request.__dict__, default=str).encode()
        req = urllib.request.Request(
            f"{self.url}/execute",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=request.timeout) as r:
                data = json.loads(r.read())
                return AgentResult(
                    success=data.get("success", False),
                    intent=request.intent,
                    adapter=self.name,
                    output=data.get("output", ""),
                    exit_code=data.get("exit_code", 0),
                    duration_ms=int((time.time() - t0) * 1000),
                    cost_hint=self.cost_hint,
                )
        except Exception as exc:
            return AgentResult(False, request.intent, self.name,
                               error=str(exc),
                               duration_ms=int((time.time() - t0) * 1000))

# ── AdapterRegistry ───────────────────────────────────────────────────────────

class AdapterRegistry:
    _adapters: dict[str, BaseAgentAdapter] = {}

    @classmethod
    def register(cls, adapter: BaseAgentAdapter) -> None:
        cls._adapters[adapter.name] = adapter

    @classmethod
    def get(cls, name: str) -> BaseAgentAdapter | None:
        return cls._adapters.get(name)

    @classmethod
    def all(cls) -> dict[str, BaseAgentAdapter]:
        return dict(cls._adapters)

    @classmethod
    def available(cls) -> list[str]:
        return [name for name, a in cls._adapters.items() if a.health()]


# Registro por defecto
AdapterRegistry.register(LocalAdapter())
AdapterRegistry.register(OllamaAdapter())
AdapterRegistry.register(MCPAdapter())
AdapterRegistry.register(CodexAdapter())
AdapterRegistry.register(CloudAdapter())

# ── AgentGateway ──────────────────────────────────────────────────────────────

class AgentGateway:
    """
    Punto de entrada único para toda orquestación externa de BAGO.

    Garantiza:
    - Allowlist de intenciones
    - Validación de riesgo
    - Trazabilidad en Neural Bus
    - Rate limiting básico
    """

    def __init__(self):
        self._event_log: list[dict] = []
        self._call_times: list[float] = []
        self._rate_limit = 10  # req/min por gateway

    def dispatch(self, request: AgentRequest) -> AgentResult:
        # Rate limiting
        now = time.time()
        self._call_times = [t for t in self._call_times if now - t < 60]
        if len(self._call_times) >= self._rate_limit:
            return AgentResult(False, request.intent, request.adapter_name,
                               error="Rate limit excedido (10 req/min)")
        self._call_times.append(now)

        # Validar intent
        if request.intent not in ALL_ALLOWED_INTENTS:
            self._emit_event("agent.blocked", request, error="intent_not_allowed")
            return AgentResult(False, request.intent, request.adapter_name,
                               error=f"Intent '{request.intent}' no está en la allowlist")

        # Validar riesgo
        if request.intent in DANGEROUS_INTENTS and not request.unsafe and not request.dry_run:
            self._emit_event("agent.blocked", request, error="dangerous_without_unsafe")
            return AgentResult(False, request.intent, request.adapter_name,
                               error=f"Intent '{request.intent}' es dangerous. Pasa dry_run=True o unsafe=True")

        # Obtener adapter
        adapter = AdapterRegistry.get(request.adapter_name)
        if not adapter:
            adapter = AdapterRegistry.get("local")

        self._emit_event("agent.request", request)

        # Ejecutar
        result = adapter.execute(request)
        result.timestamp = _now()
        result.neural_event_id = f"evt-{int(time.time())}"

        self._emit_event("agent.result" if result.success else "agent.error", request, result=result)
        return result

    def _emit_event(self, event_type: str, request: AgentRequest,
                    error: str = "", result: AgentResult | None = None) -> None:
        event = {
            "type": event_type,
            "intent": request.intent,
            "adapter": request.adapter_name,
            "timestamp": _now(),
        }
        if error:
            event["error"] = error
        if result:
            event["success"] = result.success
            event["duration_ms"] = result.duration_ms
        self._event_log.append(event)
        # Intentar emitir al Neural Bus si está disponible
        try:
            neural_log = _STATE_DIR / "neural_events.jsonl"
            with open(neural_log, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def status(self) -> dict:
        return {
            "adapters": {
                name: {
                    "available": a.health(),
                    "cost_hint": a.cost_hint,
                    "supported_intents": len(a.capability().supported_intents),
                }
                for name, a in AdapterRegistry.all().items()
            },
            "total_calls": len(self._event_log),
            "recent_calls": self._call_times[-5:],
        }


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    p = argparse.ArgumentParser(
        prog="bago agent",
        description="BAGO Multi-Agent Gateway — orquesta herramientas BAGO desde cualquier agente",
    )
    sub = p.add_subparsers(dest="cmd")

    # status
    sub.add_parser("status", help="Estado de todos los adapters disponibles")

    # dispatch
    dp = sub.add_parser("dispatch", help="Despachar una intención a un adapter")
    dp.add_argument("intent", choices=sorted(ALL_ALLOWED_INTENTS))
    dp.add_argument("--adapter", default="local", choices=["local", "ollama", "mcp", "codex", "cloud"])
    dp.add_argument("--dry-run", action="store_true")
    dp.add_argument("--unsafe", action="store_true")
    dp.add_argument("--timeout", type=int, default=30)
    dp.add_argument("--json", action="store_true", dest="as_json")

    # list
    sub.add_parser("list", help="Listar adapters y sus capacidades")

    args = p.parse_args()
    gw = AgentGateway()

    if args.cmd == "status":
        st = gw.status()
        print("🤖 BAGO Agent Gateway — Estado de adapters\n")
        for name, info in st["adapters"].items():
            icon = "✅" if info["available"] else "❌"
            print(f"  {icon} {name:<12} | {info['cost_hint']:<15} | {info['supported_intents']} intenciones")
        print(f"\nTotal llamadas registradas: {st['total_calls']}")
        # ── Mostrar separación motor / dinámica ───────────────────────────────
        if _guard:
            audit = _guard.audit()
            print(f"\n  Motor estático  (.bago/agents/):       {audit['static_roles']} roles")
            print(f"  Agentes dinámicos (.bago/state/agents/): {audit['dynamic_count']} agentes")
            if audit["contaminated"]:
                print(f"  ⚠  Contaminación detectada: {len(audit['contaminated'])} archivo(s)")
                print(f"     Ejecuta: python agent_static_guard.py --fix")
        return 0

    if args.cmd == "list":
        print("🤖 BAGO Agent Gateway — Adapters disponibles\n")
        for name, adapter in AdapterRegistry.all().items():
            cap = adapter.capability()
            icon = "✅" if cap.available else "❌"
            print(f"  {icon} {name}")
            print(f"     {cap.description}")
            print(f"     Coste: {cap.cost_hint} | Streaming: {cap.streaming}")
            print()
        return 0

    if args.cmd == "dispatch":
        req = AgentRequest(
            intent=args.intent,
            source={"adapter": args.adapter},
            options={
                "dry_run": args.dry_run,
                "unsafe": args.unsafe,
                "timeout": args.timeout,
            },
        )
        result = gw.dispatch(req)
        if args.as_json:
            print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        else:
            icon = "✅" if result.success else "❌"
            print(f"{icon} [{result.adapter}] {result.intent} ({result.duration_ms}ms)")
            if result.output:
                print(result.output)
            if result.error:
                print(f"Error: {result.error}", file=sys.stderr)
        return 0 if result.success else 1

    p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())