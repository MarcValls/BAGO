#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bago_model_router.py — Unified model router for BAGO.

BAGO scans available models FIRST, then routes every request through
orchestration with per-provider defaults. Tracks tokens per model & provider.

Usage:
    python bago_model_router.py scan                    # detect available models
    python bago_model_router.py route "escribe codigo"  # route a prompt
    python bago_model_router.py default                 # show default model per provider
    python bago_model_router.py status                  # scan + defaults + token summary
    python bago_model_router.py tokens                  # token usage report
    python bago_model_router.py serve --port 11435      # start API server

External CLIs:
    Codex:     set OPENAI_API_BASE=http://localhost:11437/v1
    Copilot:   set GITHUB_MODELS_BASE=http://localhost:11436/v1
    Ollama:    set OLLAMA_HOST=http://localhost:11434
    Any:       POST http://localhost:11435/api/chat
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

BAGO_ROOT = Path(__file__).resolve().parents[1]  # .bago/tools/ -> .bago/ -> project root
if not (BAGO_ROOT / ".bago").is_dir():
    BAGO_ROOT = BAGO_ROOT.parent  # fallback
TOOLS_DIR = BAGO_ROOT / ".bago" / "tools"
STATE_DIR = BAGO_ROOT / ".bago" / "state"
CONFIG_DIR = STATE_DIR / "config"

# ─── Defaults per provider ──────────────────────────────────────────────────

PROVIDER_DEFAULTS = {
    "codex":          {"model": "gpt-5.4-mini", "wire_name": "gpt-5.4-mini", "reason": "Best cost/perf for Codex CLI"},
    "copilot":        {"model": "gpt-5.4-mini", "wire_name": "gpt-5.4-mini", "reason": "Best cost/perf for Copilot"},
    "ollama-local":   {"model": "qwen25-coder",  "wire_name": "qwen2.5-coder:7b", "reason": "Best local coder, free"},
    "ollama-cloud":   {"model": "devstral-2",    "wire_name": "devstral-2:123b",   "reason": "Best cloud coder via Ollama"},
    "openai":         {"model": "gpt-5.4-mini", "wire_name": "gpt-5.4-mini", "reason": "Best cost/perf for OpenAI direct"},
    "anthropic":       {"model": "claude-sonnet-4.6", "wire_name": "claude-sonnet-4.6", "reason": "Best Anthropic model"},
    "gemini":         {"model": "gemini-2.5-pro", "wire_name": "gemini-2.5-pro", "reason": "Best Gemini model"},
}

FALLBACK_CHAIN = {
    "codex":        ["gpt-5.4-mini", "gpt-5.4", "gpt-5.3-codex"],
    "copilot":      ["gpt-5.4-mini", "claude-sonnet-4.6", "gpt-5.4"],
    "ollama-local": ["qwen2.5-coder:7b", "llama3.2:3b", "qwen2.5:0.5b"],
    "ollama-cloud": ["devstral-2:123b", "qwen3-coder:480b", "deepseek-v3.1:671b"],
}

# ─── Color helpers ────────────────────────────────────────────────────────────

def G(s): return f"\033[32m{s}\033[0m"
def R(s): return f"\033[31m{s}\033[0m"
def Y(s): return f"\033[33m{s}\033[0m"
def C(s): return f"\033[36m{s}\033[0m"
def B(s): return f"\033[1m{s}\033[0m"
def D(s): return f"\033[2m{s}\033[0m"


# ─── Model Scanner ───────────────────────────────────────────────────────────

class ModelScanner:
    """Scans all providers for available models."""

    def __init__(self):
        self.providers = self._load_json(STATE_DIR / "model_providers.json").get("providers", {})
        self.routing = self._load_json(STATE_DIR / "model_routing.json")
        self.orchestrator = self._load_json(STATE_DIR / "model_orchestrator.json")
        self.available: dict[str, dict] = {}  # provider -> {ok, models, detail}

    @staticmethod
    def _load_json(path: Path) -> dict:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def scan(self) -> dict[str, dict]:
        """Scan all providers. Returns {provider: {ok, models, detail}}."""
        try:
            sys.path.insert(0, str(TOOLS_DIR))
            from bago.providers import scan_providers
            self.available = scan_providers()
        except Exception:
            self.available = self._manual_scan()
        return self.available

    def _manual_scan(self) -> dict[str, dict]:
        """Fallback scan without importing providers module."""
        import subprocess, shutil, os
        results = {}
        # Ollama local
        ollama = shutil.which("ollama") or shutil.which("ollama.exe") or shutil.which("ollama.cmd")
        if ollama:
            try:
                cmd = [ollama, "list"] if not ollama.endswith(".cmd") else [ollama + ".cmd" if sys.platform == "win32" else ollama, "list"]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=10, shell=(sys.platform == "win32"))
                if r.returncode == 0:
                    models = []
                    for line in r.stdout.strip().splitlines()[1:]:
                        parts = line.split()
                        if parts:
                            models.append(parts[0])
                    results["ollama-local"] = {"ok": True, "models": models, "detail": f"{len(models)} models"}
            except Exception:
                pass
        # Copilot
        gh = shutil.which("gh")
        if gh:
            results["copilot"] = {"ok": True, "models": list(PROVIDER_DEFAULTS.get("copilot", {}).keys()),
                                  "detail": "gh CLI available"}
        # Codex / OpenAI
        if os.environ.get("OPENAI_API_KEY"):
            results["codex"] = {"ok": True, "models": list(PROVIDER_DEFAULTS.get("codex", {}).keys()),
                                "detail": "OPENAI_API_KEY set"}
        return results

    def get_available_models(self, provider: str) -> list[str]:
        """Get list of model names available for a provider."""
        info = self.available.get(provider, {})
        if not info.get("ok"):
            return []
        return info.get("models", list(self.providers.get(provider, {}).get("models", {}).keys()))

    def is_available(self, provider: str) -> bool:
        return self.available.get(provider, {}).get("ok", False)


# ─── Model Router ─────────────────────────────────────────────────────────────

class ModelRouter:
    """Routes prompts to the best provider/model based on BAGO orchestration."""

    def __init__(self, scanner: ModelScanner | None = None):
        self.scanner = scanner or ModelScanner()
        self.usage_file = CONFIG_DIR / "token_usage.jsonl"

    def route(self, prompt: str, provider: str = "", mode: str = "") -> dict:
        """Route a prompt to the best available model.

        1. If provider specified, use that provider with its default model.
        2. If mode specified, use the mode's fallback chain.
        3. Otherwise, auto-route using BAGO rules.

        Returns: {provider, model, wire_name, reason, fallback_chain}
        """
        # Step 1: scan available providers
        if not self.scanner.available:
            self.scanner.scan()

        # Step 2: explicit provider
        if provider:
            return self._route_provider(provider)

        # Step 3: mode-based routing
        if mode:
            return self._route_mode(mode)

        # Step 4: auto-route using BAGO rules
        return self._route_auto(prompt)

    def _route_provider(self, provider: str) -> dict:
        """Route to a specific provider, using its default model."""
        default = PROVIDER_DEFAULTS.get(provider, {})
        models = self.scanner.get_available_models(provider)
        orchestrator = self.scanner.orchestrator
        prov_models = self.scanner.providers.get(provider, {}).get("models", {})

        # Try default model first
        model_name = default.get("model", "")
        if model_name and model_name in prov_models:
            wire = prov_models[model_name].get("wire_name", model_name)
            return {
                "provider": provider,
                "model": model_name,
                "wire_name": wire,
                "reason": default.get("reason", "provider default"),
                "available": self.scanner.is_available(provider),
                "fallback_chain": FALLBACK_CHAIN.get(provider, []),
            }

        # Try first available model from provider config
        for name, info in prov_models.items():
            return {
                "provider": provider,
                "model": name,
                "wire_name": info.get("wire_name", name),
                "reason": "first model in provider config",
                "available": self.scanner.is_available(provider),
                "fallback_chain": FALLBACK_CHAIN.get(provider, []),
            }

        return {"provider": provider, "model": default.get("model", "?"),
                "wire_name": default.get("wire_name", "?"),
                "reason": "default (provider not in config)", "available": False,
                "fallback_chain": []}

    def _route_mode(self, mode: str) -> dict:
        """Route using orchestrator mode (offline, economico, estandar, full)."""
        orchestrator = self.scanner.orchestrator
        mode_config = orchestrator.get("modes", {}).get(mode)
        if not mode_config:
            return self._route_provider("ollama-local")

        # Try each provider in allowed list, pick first available
        for provider in mode_config.get("allowed_providers", []):
            if self.scanner.is_available(provider):
                default = PROVIDER_DEFAULTS.get(provider, {})
                prov_models = self.scanner.providers.get(provider, {}).get("models", {})
                model_name = mode_config.get("default_model", default.get("model", ""))
                wire = prov_models.get(model_name, {}).get("wire_name", model_name)
                if not wire and prov_models:
                    first = next(iter(prov_models.items()))
                    model_name, info = first
                    wire = info.get("wire_name", model_name)
                return {
                    "provider": provider,
                    "model": model_name,
                    "wire_name": wire,
                    "reason": f"mode={mode}, first available provider",
                    "available": True,
                    "fallback_chain": mode_config.get("fallback_chain", []),
                }

        # No available provider in mode — use fallback
        fb = orchestrator.get("modes", {}).get(mode, {}).get("fallback_chain", [])
        if fb:
            first = fb[0]
            return {"provider": "ollama-local", "model": first,
                    "wire_name": first, "reason": f"mode={mode} fallback",
                    "available": False, "fallback_chain": fb}
        return {"provider": "ollama-local", "model": "qwen25-coder",
                "wire_name": "qwen2.5-coder:7b", "reason": "ultimate fallback",
                "available": False, "fallback_chain": []}

    def _route_auto(self, prompt: str) -> dict:
        """Auto-route using BAGO routing rules + availability."""
        try:
            sys.path.insert(0, str(TOOLS_DIR))
            from bago.providers import route_by_task
            result = route_by_task(prompt, self.scanner.routing, self.scanner.providers)
            if isinstance(result, tuple) and len(result) >= 3:
                model, wire, prov = result[0], result[1], result[2]
                reason = result[3] if len(result) > 3 else "auto-routed"
                return {
                    "provider": prov, "model": model, "wire_name": wire,
                    "reason": f"auto: {reason}",
                    "available": self.scanner.is_available(prov),
                    "fallback_chain": FALLBACK_CHAIN.get(prov, []),
                }
        except Exception:
            pass

        # Manual keyword routing
        rules = self.scanner.routing.get("rules", [])
        best, best_hits = None, 0
        tl = prompt.lower()
        for rule in rules:
            hits = sum(1 for kw in rule.get("keywords", []) if kw.lower() in tl)
            if hits > best_hits:
                best_hits, best = hits, rule
        if best:
            prov = best.get("provider", "ollama-local")
            model = best.get("model", "")
            prov_models = self.scanner.providers.get(prov, {}).get("models", {})
            wire = prov_models.get(model, {}).get("wire_name", model)
            return {"provider": prov, "model": model, "wire_name": wire,
                    "reason": f"keyword: {best.get('id', '?')}",
                    "available": self.scanner.is_available(prov),
                    "fallback_chain": FALLBACK_CHAIN.get(prov, [])}

        # Fallback
        fb = self.scanner.routing.get("fallback", {"provider": "ollama-local", "model": "qwen25-coder"})
        return {"provider": fb["provider"], "model": fb["model"],
                "wire_name": fb.get("wire_name", fb["model"]),
                "reason": "fallback", "available": self.scanner.is_available(fb["provider"]),
                "fallback_chain": FALLBACK_CHAIN.get(fb["provider"], [])}

    # ── Token Tracking ──────────────────────────────────────────────────────

    def record_usage(self, provider: str, model: str, prompt_tokens: int,
                     completion_tokens: int, session_id: str = "") -> None:
        """Record token usage per model and provider."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "provider": provider,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "session_id": session_id,
        }
        with open(self.usage_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def token_report(self) -> dict:
        """Token usage report grouped by provider and model."""
        records = self._load_usage()
        total = sum(r.get("total_tokens", 0) for r in records)
        by_provider = defaultdict(lambda: {"tokens": 0, "models": {}})
        for r in records:
            prov = r.get("provider", "unknown")
            model = r.get("model", "unknown")
            tokens = r.get("total_tokens", 0)
            by_provider[prov]["tokens"] += tokens
            if model not in by_provider[prov]["models"]:
                by_provider[prov]["models"][model] = 0
            by_provider[prov]["models"][model] += tokens

        result = {}
        for prov, info in sorted(by_provider.items(), key=lambda x: -x[1]["tokens"]):
            prov_pct = round(info["tokens"] / max(total, 1) * 100, 1)
            models = {}
            for model, tokens in sorted(info["models"].items(), key=lambda x: -x[1]):
                models[model] = {"tokens": tokens, "pct": round(tokens / max(info["tokens"], 1) * 100, 1)}
            result[prov] = {"tokens": info["tokens"], "pct": prov_pct, "models": models}
        result["_total_tokens"] = total
        result["_sessions"] = len(set(r.get("session_id", "") for r in records))
        return result

    def _load_usage(self) -> list[dict]:
        if not self.usage_file.exists():
            return []
        records = []
        with open(self.usage_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return records


# ─── CLI ───────────────────────────────────────────────────────────────────────

def cmd_scan(scanner: ModelScanner) -> None:
    results = scanner.scan()
    print(f"\n  {B('BAGO Model Scanner')}")
    print(f"  {'=' * 50}\n")
    icons = {True: G("\u2705"), False: R("\u274c")}
    for prov, info in sorted(results.items()):
        icon = icons.get(info.get("ok"), Y("?"))
        detail = info.get("detail", "")
        n_models = len(info.get("models", []))
        print(f"  {icon}  {B(prov):<16} {n_models:>3} models  {D(detail)}")
    print()

    # Show defaults
    print(f"  {B('Default models per provider:')}")
    for prov, default in PROVIDER_DEFAULTS.items():
        avail = G("\u2705") if scanner.is_available(prov) else D("\u2022")
        print(f"  {avail}  {prov:<16} {C(default['model']):<20} {D(default['reason'])}")
    print()


def cmd_route(router: ModelRouter, prompt: str, provider: str = "", mode: str = "") -> None:
    result = router.route(prompt, provider=provider, mode=mode)
    avail = G("available") if result.get("available") else Y("offline")
    print(f"\n  {B('BAGO Model Router')}")
    print(f"  {'=' * 50}\n")
    print(f"  Provider:  {C(result['provider'])} ({avail})")
    print(f"  Model:     {B(result['model'])}")
    print(f"  Wire:      {D(result.get('wire_name', result['model']))}")
    print(f"  Reason:    {result.get('reason', 'auto')}")
    fb = result.get("fallback_chain", [])
    if fb:
        print(f"  Fallback:  {' \u2192 '.join(fb)}")
    print()

    # Show mode options
    if not provider and not mode:
        print(f"  {B('Override options:')}")
        modes = router.scanner.orchestrator.get("modes", {})
        for m, cfg in modes.items():
            print(f"    --mode {m:<14} {D(cfg.get('description', ''))}")
        print(f"    --provider <name>   Force a specific provider")
        print()


def cmd_status(scanner: ModelScanner, router: ModelRouter) -> None:
    results = scanner.scan()
    report = router.token_report()
    print(f"\n  {B('BAGO Router Status')}")
    print(f"  {'=' * 50}\n")

    # Providers
    print(f"  {B('Providers:')}")
    for prov, info in sorted(results.items()):
        icon = G("\u2705") if info.get("ok") else R("\u274c")
        n = len(info.get("models", []))
        print(f"  {icon}  {prov:<16} {n} models")
    print()

    # Defaults
    print(f"  {B('Defaults:')}")
    for prov, default in PROVIDER_DEFAULTS.items():
        avail = G("\u2705") if scanner.is_available(prov) else D("\u2022")
        print(f"  {avail}  {prov:<16} {C(default['model']):<20}")
    print()

    # Token usage
    total = report.get("_total_tokens", 0)
    if total > 0:
        print(f"  {B('Token usage:')}")
        for prov, info in {k: v for k, v in report.items() if not k.startswith("_")}.items():
            pct = info.get("pct", 0)
            bar = "\u2588" * int(pct / 5) + "\u2591" * (20 - int(pct / 5))
            print(f"  {prov:<16} {bar} {pct:>5.1f}%  ({info['tokens']:,} tokens)")
        print(f"\n  Total: {total:,} tokens across {report.get('_sessions', 0)} sessions")
    else:
        print(f"  {D('No token usage recorded yet.')}")
    print()


def cmd_tokens(router: ModelRouter) -> None:
    report = router.token_report()
    total = report.get("_total_tokens", 0)
    if total == 0:
        print(f"\n  {D('No token usage recorded yet. Run a session first.')}\n")
        return

    print(f"\n  {B('BAGO Token Analytics')}")
    print(f"  {'=' * 50}\n")
    print(f"  Total tokens: {B(f'{total:,}')}")
    print(f"  Sessions:     {report.get('_sessions', 0)}\n")

    for prov, info in {k: v for k, v in report.items() if not k.startswith("_")}.items():
        pct = info.get("pct", 0)
        print(f"  {B(prov)} — {info['tokens']:,} tokens ({pct}%)")
        for model, minfo in info.get("models", {}).items():
            mpct = minfo.get("pct", 0)
            bar = "\u2588" * max(1, int(mpct / 5)) + "\u2591" * (20 - max(1, int(mpct / 5)))
            print(f"    {model:<24} {bar} {mpct:>5.1f}%  ({minfo['tokens']:,} tok)")
        print()


def cmd_serve(router: ModelRouter, port: int = 11435) -> None:
    """Start the BAGO API server with model routing."""
    try:
        sys.path.insert(0, str(TOOLS_DIR))
        from bago.api.server import create_app
        import uvicorn
        app = create_app(router)
        print(f"\n  {B('BAGO Router API')} on :{port}")
        print(f"  Endpoints: /api/chat, /api/generate, /api/models, /api/route, /api/tokens")
        print(f"  External CLIs: set OPENAI_API_BASE=http://localhost:{port}/v1\n")
        uvicorn.run(app, host="127.0.0.1", port=port)
    except ImportError as e:
        print(f"\n  {R('Missing dependency:')} {e}")
        print(f"  Install with: {C('pip install fastapi uvicorn')}\n")
    except KeyboardInterrupt:
        print(f"\n  {Y('Server stopped.')}\n")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    if "--test" in args:
        scanner = ModelScanner()
        results = scanner._manual_scan()
        assert isinstance(results, dict)
        print("  self-test OK")
        return 0

    if not args or args[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0

    scanner = ModelScanner()
    router = ModelRouter(scanner)

    cmd = args[0]
    rest = args[1:]

    if cmd == "scan":
        cmd_scan(scanner)
    elif cmd == "route":
        prompt = " ".join(rest) if rest else "escribe una funcion Python"
        provider = ""
        mode = ""
        for i, a in enumerate(rest):
            if a == "--provider" and i + 1 < len(rest): provider = rest[i + 1]
            if a == "--mode" and i + 1 < len(rest): mode = rest[i + 1]
        cmd_route(router, prompt, provider=provider, mode=mode)
    elif cmd == "default":
        scanner.scan()
        print(f"\n  {B('BAGO Default Models')}")
        print(f"  {'=' * 50}\n")
        for prov, default in PROVIDER_DEFAULTS.items():
            avail = G("\u2705") if scanner.is_available(prov) else D("\u2022 offline")
            print(f"  {avail}  {prov:<16} {C(default['model']):<20} {D(default['reason'])}")
        print()
    elif cmd == "status":
        cmd_status(scanner, router)
    elif cmd == "tokens":
        cmd_tokens(router)
    elif cmd == "serve":
        port = 11435
        for i, a in enumerate(rest):
            if a == "--port" and i + 1 < len(rest):
                port = int(rest[i + 1])
        cmd_serve(router, port=port)
    else:
        print(f"  Unknown command: {cmd}")
        print(f"  Use: bago router scan|route|default|status|tokens|serve")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
