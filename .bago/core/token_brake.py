#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""token_brake.py — Freno de tokens para providers de API.

Problema: GitHub Copilot login no tiene freno de tokens (pago a mes vencido).
Solucion: Deshabilitar Copilot login, usar API models con limite de tokens,
y detener automaticamente cuando se exceda el presupuesto.

Uso:
    from token_brake import TokenBrake
    brake = TokenBrake(bago_root)
    if not brake.allow_call(provider="openai", estimated_tokens=500):
        raise TokenBudgetExceeded("Freno activado: presupuesto agotado")
    brake.record_call(provider="openai", tokens_used=512)

    # CLI
    python token_brake.py status
    python token_brake.py set-limit openai 1000000
    python token_brake.py disable copilot
    python token_brake.py enable openai
    python token_brake.py reset --monthly
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class TokenBudgetExceeded(Exception):
    """El freno de tokens ha activado porque se excedio el presupuesto."""
    pass


class TokenBrake:
    """Freno de tokens: limita consumo por provider y periodo."""

    # Provider types
    PROVIDER_API = {"openai", "anthropic", "groq", "deepseek", "google"}
    PROVIDER_LOCAL = {"ollama"}
    PROVIDER_LOGIN = {"copilot", "github_copilot"}

    def __init__(self, bago_root: str | Path):
        self.root = Path(bago_root).resolve()
        self.state_dir = self.root / ".bago" / "state"
        self.config_dir = self.state_dir / "config"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.brake_file = self.config_dir / "token_brake.json"
        self.usage_file = self.config_dir / "token_usage.jsonl"
        self._config = self._load_config()

    def _load_config(self) -> dict:
        if self.brake_file.exists():
            return json.loads(self.brake_file.read_text(encoding="utf-8"))
        return self._default_config()

    def _default_config(self) -> dict:
        return {
            "version": "1.0.0",
            "enabled": True,
            "providers": {
                "copilot": {"mode": "disabled", "reason": "login sin freno de tokens, pago a mes vencido"},
                "github_copilot": {"mode": "disabled", "reason": "login sin freno de tokens, pago a mes vencido"},
                "openai": {"mode": "enabled", "limit_daily": 50000, "limit_monthly": 500000, "limit_per_call": 4000},
                "ollama": {"mode": "enabled", "limit_daily": None, "limit_monthly": None, "limit_per_call": 8000},
            },
            "global_limits": {
                "limit_daily": 100000,
                "limit_monthly": 1000000,
            },
            "alerts": {
                "threshold_50": True,
                "threshold_80": True,
                "threshold_95": True,
            },
        }

    def _save_config(self):
        self.brake_file.write_text(json.dumps(self._config, indent=2, ensure_ascii=False), encoding="utf-8")

    def _today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _this_month(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m")

    def _usage_records(self) -> list[dict]:
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

    def _usage_for_provider(self, provider: str, period: str) -> int:
        """Sum tokens used for provider in a period (day: 2026-05-19, month: 2026-05)."""
        records = self._usage_records()
        total = 0
        for r in records:
            if r.get("provider") == provider:
                ts = r.get("timestamp", "")
                if period.count("-") == 2 and ts.startswith(period):
                    total += r.get("tokens", 0)
                elif period.count("-") == 1 and ts[:7] == period:
                    total += r.get("tokens", 0)
        return total

    def _global_usage(self, period: str) -> int:
        records = self._usage_records()
        total = 0
        for r in records:
            ts = r.get("timestamp", "")
            if period.count("-") == 2 and ts.startswith(period):
                total += r.get("tokens", 0)
            elif period.count("-") == 1 and ts[:7] == period:
                total += r.get("tokens", 0)
        return total

    # ── Public API ───────────────────────────────────────────────────────────

    def is_enabled(self, provider: str) -> bool:
        cfg = self._config.get("providers", {}).get(provider, {})
        return cfg.get("mode") == "enabled"

    def is_disabled(self, provider: str) -> bool:
        return not self.is_enabled(provider)

    def disable(self, provider: str, reason: str = ""):
        if "providers" not in self._config:
            self._config["providers"] = {}
        if provider not in self._config["providers"]:
            self._config["providers"][provider] = {}
        self._config["providers"][provider]["mode"] = "disabled"
        if reason:
            self._config["providers"][provider]["reason"] = reason
        self._save_config()

    def enable(self, provider: str, limits: dict | None = None):
        if "providers" not in self._config:
            self._config["providers"] = {}
        if provider not in self._config["providers"]:
            self._config["providers"][provider] = {}
        self._config["providers"][provider]["mode"] = "enabled"
        self._config["providers"][provider].pop("reason", None)
        if limits:
            self._config["providers"][provider].update(limits)
        self._save_config()

    def allow_call(self, provider: str, estimated_tokens: int = 0) -> tuple[bool, str]:
        """Check if a call is allowed. Returns (allowed, reason)."""
        if not self._config.get("enabled", True):
            return True, "brake disabled"

        provider_cfg = self._config.get("providers", {}).get(provider, {})
        if provider_cfg.get("mode") == "disabled":
            reason = provider_cfg.get("reason", "provider disabled")
            return False, f"BRAKE: {provider} esta deshabilitado. {reason}"

        # Check per-call limit
        per_call = provider_cfg.get("limit_per_call")
        if per_call and estimated_tokens > per_call:
            return False, f"BRAKE: llamada estimada ({estimated_tokens}) excede limite por llamada ({per_call})"

        # Check daily limit
        daily_limit = provider_cfg.get("limit_daily")
        if daily_limit:
            used_today = self._usage_for_provider(provider, self._today())
            if used_today + estimated_tokens > daily_limit:
                return False, f"BRAKE: limite diario de {provider} agotado ({used_today}/{daily_limit})"

        # Check monthly limit
        monthly_limit = provider_cfg.get("limit_monthly")
        if monthly_limit:
            used_month = self._usage_for_provider(provider, self._this_month())
            if used_month + estimated_tokens > monthly_limit:
                return False, f"BRAKE: limite mensual de {provider} agotado ({used_month}/{monthly_limit})"

        # Check global daily limit
        global_daily = self._config.get("global_limits", {}).get("limit_daily")
        if global_daily:
            global_used = self._global_usage(self._today())
            if global_used + estimated_tokens > global_daily:
                return False, f"BRAKE: limite diario global agotado ({global_used}/{global_daily})"

        # Check global monthly limit
        global_monthly = self._config.get("global_limits", {}).get("limit_monthly")
        if global_monthly:
            global_used = self._global_usage(self._this_month())
            if global_used + estimated_tokens > global_monthly:
                return False, f"BRAKE: limite mensual global agotado ({global_used}/{global_monthly})"

        return True, "OK"

    def record_call(self, provider: str, tokens_used: int, model: str = "", meta: dict | None = None):
        """Record actual token usage."""
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "provider": provider,
            "tokens": tokens_used,
            "model": model,
            "meta": meta or {},
        }
        with open(self.usage_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def status(self) -> dict:
        """Full status report."""
        today = self._today()
        month = self._this_month()
        providers_status = {}
        for name, cfg in self._config.get("providers", {}).items():
            mode = cfg.get("mode", "unknown")
            used_today = self._usage_for_provider(name, today)
            used_month = self._usage_for_provider(name, month)
            daily_limit = cfg.get("limit_daily")
            monthly_limit = cfg.get("limit_monthly")
            daily_pct = round(used_today / daily_limit * 100, 1) if daily_limit else None
            monthly_pct = round(used_month / monthly_limit * 100, 1) if monthly_limit else None
            providers_status[name] = {
                "mode": mode,
                "used_today": used_today,
                "used_month": used_month,
                "limit_daily": daily_limit,
                "limit_monthly": monthly_limit,
                "daily_pct": daily_pct,
                "monthly_pct": monthly_pct,
                "reason": cfg.get("reason", ""),
            }
        return {
            "brake_enabled": self._config.get("enabled", True),
            "today": today,
            "month": month,
            "providers": providers_status,
            "global_used_today": self._global_usage(today),
            "global_used_month": self._global_usage(month),
            "global_limits": self._config.get("global_limits", {}),
        }

    def reset(self, period: str = "all"):
        """Reset usage. period: daily, monthly, all."""
        if period == "all":
            if self.usage_file.exists():
                self.usage_file.unlink()
        elif period == "daily":
            # Filter out today's records
            today = self._today()
            records = [r for r in self._usage_records() if not r.get("timestamp", "").startswith(today)]
            self.usage_file.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
        elif period == "monthly":
            month = self._this_month()
            records = [r for r in self._usage_records() if not r.get("timestamp", "")[:7] == month]
            self.usage_file.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")


def main() -> int:
    import sys
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    import argparse
    parser = argparse.ArgumentParser(description="Token Brake — freno de tokens para providers API")
    parser.add_argument("--bago-root", default=".")
    sub = parser.add_subparsers(dest="cmd")

    p_status = sub.add_parser("status", help="estado del freno")
    p_disable = sub.add_parser("disable", help="deshabilitar provider")
    p_disable.add_argument("provider")
    p_disable.add_argument("--reason", default="")
    p_enable = sub.add_parser("enable", help="habilitar provider")
    p_enable.add_argument("provider")
    p_set = sub.add_parser("set-limit", help="establecer limite")
    p_set.add_argument("provider")
    p_set.add_argument("limit_name", choices=["daily", "monthly", "per_call"])
    p_set.add_argument("value", type=int)
    p_allow = sub.add_parser("allow", help="verificar si una llamada esta permitida")
    p_allow.add_argument("provider")
    p_allow.add_argument("--tokens", type=int, default=0)
    p_record = sub.add_parser("record", help="registrar uso")
    p_record.add_argument("provider")
    p_record.add_argument("tokens", type=int)
    p_reset = sub.add_parser("reset", help="resetear uso")
    p_reset.add_argument("--period", choices=["daily", "monthly", "all"], default="all")

    args = parser.parse_args()
    brake = TokenBrake(args.bago_root)

    if args.cmd == "status":
        st = brake.status()
        print(f"Freno activo: {st['brake_enabled']}")
        print(f"Periodo: {st['today']} / {st['month']}")
        print("")
        for name, info in st["providers"].items():
            mode_icon = "✅" if info["mode"] == "enabled" else "❌"
            print(f"{mode_icon} {name:15} mode={info['mode']}")
            if info["mode"] == "enabled":
                if info["limit_daily"]:
                    print(f"   diario:  {info['used_today']:>8} / {info['limit_daily']:<8} ({info['daily_pct']}%)")
                if info["limit_monthly"]:
                    print(f"   mensual: {info['used_month']:>8} / {info['limit_monthly']:<8} ({info['monthly_pct']}%)")
            else:
                print(f"   razon: {info['reason']}")
        print("")
        gl = st["global_limits"]
        if gl.get("limit_daily"):
            print(f"Global diario:  {st['global_used_today']} / {gl['limit_daily']}")
        if gl.get("limit_monthly"):
            print(f"Global mensual: {st['global_used_month']} / {gl['limit_monthly']}")
        return 0

    if args.cmd == "disable":
        brake.disable(args.provider, args.reason)
        print(f"❌ Provider deshabilitado: {args.provider}")
        if args.reason:
            print(f"   razon: {args.reason}")
        return 0

    if args.cmd == "enable":
        brake.enable(args.provider)
        print(f"✅ Provider habilitado: {args.provider}")
        return 0

    if args.cmd == "set-limit":
        key = f"limit_{args.limit_name}"
        brake.enable(args.provider, {key: args.value})
        print(f"✅ Limite establecido: {args.provider} {key} = {args.value}")
        return 0

    if args.cmd == "allow":
        allowed, reason = brake.allow_call(args.provider, args.tokens)
        print(f"{'✅' if allowed else '❌'} {reason}")
        return 0 if allowed else 1

    if args.cmd == "record":
        brake.record_call(args.provider, args.tokens)
        print(f"📝 Registrado: {args.provider} +{args.tokens} tokens")
        return 0

    if args.cmd == "reset":
        brake.reset(args.period)
        print(f"🔄 Uso reseteado: {args.period}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

