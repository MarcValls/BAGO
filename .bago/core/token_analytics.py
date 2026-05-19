#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""token_analytics.py — Analytics de tokens por proveedor, modelo y evolucion del sistema.

Desglose:
  - % tokens usados por proveedor
  - % tokens usados por modelo dentro de cada proveedor
  - Tokens derrochados: reintentos, fallos, ruido, desacoplamiento
  - Evolucion: como cambia la eficiencia token a lo largo del tiempo

Uso:
    python token_analytics.py --bago-root . report
    python token_analytics.py --bago-root . evolution --days 30
    python token_analytics.py --bago-root . models --provider openai
    python token_analytics.py --bago-root . wasted
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


class TokenAnalytics:
    """Analytics de uso y derroche de tokens."""

    def __init__(self, bago_root: str | Path):
        self.root = Path(bago_root).resolve()
        self.usage_file = self.root / ".bago" / "state" / "config" / "token_usage.jsonl"
        self.brake_file = self.root / ".bago" / "state" / "config" / "token_brake.json"

    def _load_records(self) -> list[dict]:
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

    def _load_brake_config(self) -> dict:
        if self.brake_file.exists():
            return json.loads(self.brake_file.read_text(encoding="utf-8"))
        return {}

    # ── Reports ────────────────────────────────────────────────────────────────

    def report_by_provider(self) -> dict:
        records = self._load_records()
        total = sum(r.get("tokens", 0) for r in records)
        by_provider = defaultdict(int)
        for r in records:
            by_provider[r.get("provider", "unknown")] += r.get("tokens", 0)
        result = {}
        for prov, used in sorted(by_provider.items(), key=lambda x: -x[1]):
            pct = round(used / max(total, 1) * 100, 2)
            result[prov] = {"tokens": used, "pct": pct}
        result["_total"] = total
        return result

    def report_by_model(self) -> dict:
        records = self._load_records()
        total = sum(r.get("tokens", 0) for r in records)
        by_model = defaultdict(lambda: {"tokens": 0, "provider": ""})
        for r in records:
            model = r.get("model", "unknown")
            prov = r.get("provider", "unknown")
            by_model[model]["tokens"] += r.get("tokens", 0)
            by_model[model]["provider"] = prov
        result = {}
        for model, info in sorted(by_model.items(), key=lambda x: -x[1]["tokens"]):
            pct = round(info["tokens"] / max(total, 1) * 100, 2)
            result[model] = {"tokens": info["tokens"], "pct": pct, "provider": info["provider"]}
        result["_total"] = total
        return result

    def report_by_provider_model(self) -> dict:
        records = self._load_records()
        total = sum(r.get("tokens", 0) for r in records)
        nested = defaultdict(lambda: defaultdict(int))
        for r in records:
            prov = r.get("provider", "unknown")
            model = r.get("model", "unknown")
            nested[prov][model] += r.get("tokens", 0)
        result = {}
        for prov in sorted(nested.keys()):
            prov_total = sum(nested[prov].values())
            prov_pct = round(prov_total / max(total, 1) * 100, 2)
            models = {}
            for model, used in sorted(nested[prov].items(), key=lambda x: -x[1]):
                model_pct = round(used / max(prov_total, 1) * 100, 2)
                models[model] = {"tokens": used, "pct_of_provider": model_pct}
            result[prov] = {
                "tokens": prov_total,
                "pct_of_total": prov_pct,
                "models": models,
            }
        result["_total"] = total
        return result

    def report_wasted(self) -> dict:
        """Tokens derrochados: calculados heurísticamente desde metadata.

        Criterios de derroche:
          - retry=True: tokens de reintentos fallidos
          - truncated=True: tokens desperdiciados en respuesta truncada
          - drift_detected=True en meta: el prompt se desacopló, tokens sin valor
          - error=True: llamada fallida
          - noise_score > 0.5 en meta: mucho ruido en el prompt
        """
        records = self._load_records()
        total = sum(r.get("tokens", 0) for r in records)
        wasted = 0
        reasons = defaultdict(int)
        for r in records:
            meta = r.get("meta", {})
            tokens = r.get("tokens", 0)
            w = 0
            if meta.get("retry"):
                w += tokens
                reasons["retry"] += tokens
            if meta.get("truncated"):
                w += int(tokens * 0.5)
                reasons["truncated"] += int(tokens * 0.5)
            if meta.get("drift_detected"):
                w += int(tokens * 0.3)
                reasons["drift"] += int(tokens * 0.3)
            if meta.get("error"):
                w += tokens
                reasons["error"] += tokens
            noise = meta.get("noise_score", 0)
            if noise > 0.5:
                w += int(tokens * noise)
                reasons["noise"] += int(tokens * noise)
            wasted += min(w, tokens)
        useful = max(total - wasted, 0)
        return {
            "total_tokens": total,
            "wasted_tokens": wasted,
            "useful_tokens": useful,
            "wasted_pct": round(wasted / max(total, 1) * 100, 2),
            "useful_pct": round(useful / max(total, 1) * 100, 2),
            "reasons": dict(reasons),
        }

    def report_evolution(self, days: int = 30) -> list[dict]:
        """Evolucion diaria del sistema: eficiencia, derroche, presion."""
        records = self._load_records()
        by_day = defaultdict(lambda: {"total": 0, "wasted": 0, "calls": 0, "providers": set()})
        for r in records:
            ts = r.get("timestamp", "")[:10]
            if not ts:
                continue
            tokens = r.get("tokens", 0)
            meta = r.get("meta", {})
            by_day[ts]["total"] += tokens
            by_day[ts]["calls"] += 1
            by_day[ts]["providers"].add(r.get("provider", "unknown"))
            w = 0
            if meta.get("retry"):
                w += tokens
            if meta.get("truncated"):
                w += int(tokens * 0.5)
            if meta.get("drift_detected"):
                w += int(tokens * 0.3)
            if meta.get("error"):
                w += tokens
            noise = meta.get("noise_score", 0)
            if noise > 0.5:
                w += int(tokens * noise)
            by_day[ts]["wasted"] += min(w, tokens)

        result = []
        for day in sorted(by_day.keys())[-days:]:
            info = by_day[day]
            total = info["total"]
            wasted = info["wasted"]
            useful = max(total - wasted, 0)
            result.append({
                "day": day,
                "total_tokens": total,
                "wasted_tokens": wasted,
                "useful_tokens": useful,
                "calls": info["calls"],
                "providers": len(info["providers"]),
                "efficiency_pct": round(useful / max(total, 1) * 100, 2),
                "wasted_pct": round(wasted / max(total, 1) * 100, 2),
            })
        return result

    def summary(self) -> dict:
        records = self._load_records()
        providers = self.report_by_provider()
        models = self.report_by_model()
        wasted = self.report_wasted()
        evol = self.report_evolution(days=7)
        return {
            "total_calls": len(records),
            "total_tokens": providers.get("_total", 0),
            "providers": {k: v for k, v in providers.items() if not k.startswith("_")},
            "models_top5": dict(list({k: v for k, v in models.items() if not k.startswith("_")}.items())[:5]),
            "wasted": wasted,
            "evolution_last7": evol,
        }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Token Analytics")
    parser.add_argument("--bago-root", default=".")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("report", help="resumen completo")
    sub.add_parser("providers", help="desglose por proveedor")
    sub.add_parser("models", help="desglose por modelo")
    p_evol = sub.add_parser("evolution", help="evolucion temporal")
    p_evol.add_argument("--days", type=int, default=30)
    sub.add_parser("wasted", help="tokens derrochados")
    args = parser.parse_args()

    analytics = TokenAnalytics(args.bago_root)

    if args.cmd == "report":
        data = analytics.summary()
        print(f"Llamadas totales: {data['total_calls']}")
        print(f"Tokens totales:   {data['total_tokens']}")
        print("")
        print("--- Por Proveedor ---")
        for prov, info in data["providers"].items():
            print(f"  {prov:15} {info['tokens']:>10} tokens  ({info['pct']:>6}%)")
        print("")
        print("--- Top 5 Modelos ---")
        for model, info in data["models_top5"].items():
            print(f"  {model:25} {info['tokens']:>10} tokens  ({info['pct']:>6}%)  [{info['provider']}]")
        print("")
        w = data["wasted"]
        print(f"--- Tokens Derrochados ---")
        print(f"  Total:    {w['total_tokens']}")
        print(f"  Derroche: {w['wasted_tokens']} ({w['wasted_pct']}%)")
        print(f"  Utiles:   {w['useful_tokens']} ({w['useful_pct']}%)")
        if w["reasons"]:
            print("  Razones:")
            for reason, amount in w["reasons"].items():
                print(f"    - {reason}: {amount}")
        print("")
        print("--- Evolucion Ultimos 7 Dias ---")
        for day in data["evolution_last7"]:
            print(f"  {day['day']} | {day['total_tokens']:>8} tokens | efic: {day['efficiency_pct']:>5}% | derroche: {day['wasted_pct']:>5}% | {day['calls']} llamadas")

    elif args.cmd == "providers":
        data = analytics.report_by_provider_model()
        total = data.pop("_total", 0)
        print(f"Tokens totales: {total}")
        print("")
        for prov, info in data.items():
            print(f"{prov}: {info['tokens']} tokens ({info['pct_of_total']}% del total)")
            for model, minfo in info["models"].items():
                print(f"  - {model}: {minfo['tokens']} ({minfo['pct_of_provider']}% del proveedor)")

    elif args.cmd == "models":
        data = analytics.report_by_model()
        total = data.pop("_total", 0)
        print(f"Tokens totales: {total}")
        print("")
        for model, info in data.items():
            print(f"{model:25} {info['tokens']:>10} tokens  ({info['pct']:>6}%)  [{info['provider']}]")

    elif args.cmd == "evolution":
        data = analytics.report_evolution(days=args.days)
        print(f"Evolucion ultimos {args.days} dias:")
        print(f"{'Dia':12} {'Total':>10} {'Utiles':>10} {'Derroche':>10} {'Efic%':>8} {'Der%':>8} {'Llamadas':>10}")
        print("-" * 75)
        for day in data:
            print(f"{day['day']:12} {day['total_tokens']:>10} {day['useful_tokens']:>10} {day['wasted_tokens']:>10} {day['efficiency_pct']:>8} {day['wasted_pct']:>8} {day['calls']:>10}")

    elif args.cmd == "wasted":
        data = analytics.report_wasted()
        print(f"Tokens totales:    {data['total_tokens']}")
        print(f"Tokens derrochados: {data['wasted_tokens']} ({data['wasted_pct']}%)")
        print(f"Tokens utiles:     {data['useful_tokens']} ({data['useful_pct']}%)")
        print("")
        print("Desglose por razon:")
        for reason, amount in data["reasons"].items():
            print(f"  - {reason}: {amount}")

    else:
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
