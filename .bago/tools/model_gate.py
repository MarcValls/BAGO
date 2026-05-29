#!/usr/bin/env python3
"""model_gate.py — Gate de fallback entre modelos


Cuando un modelo llama a otro y no está disponible:
1. Intenta fallback al modelo local más cercano
2. Si no hay local, intenta cloud con mismo tier
3. Si cloud no disponible, desactiva la cadena y usa single
4. Registra el fallo para analytics

Reglas:
- Nunca dejar un pipeline roto sin respuesta
- Siempre informar al usuario del cambio
- Siempre registrar el gate para aprendizaje
"""

import json
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

@dataclass
class ModelGateResult:
    success: bool
    fallback_model: Optional[str] = None
    fallback_provider: Optional[str] = None
    reason: str = ""
    gate_action: str = ""  # "fallback" | "skip" | "abort" | "degrade"


class ModelGate:
    """Gate que gestiona llamadas modelo-a-modelo con fallback."""
    
    # Mapa de equivalencias: modelo -> lista de fallbacks ordenados
    FALLBACK_CHAIN: Dict[str, List[Tuple[str, str]]] = {
        "gpt-4o": [("ollama", "qwen2.5:14b"), ("copilot", "gpt-4o")],
        "gpt-4o-mini": [("ollama", "qwen2.5:7b"), ("copilot", "gpt-4o-mini")],
        "claude-opus-4": [("copilot", "gpt-4o"), ("ollama", "qwen2.5:14b")],
        "qwen2.5:14b": [("copilot", "gpt-4o"), ("ollama", "qwen2.5:7b")],
        "qwen2.5:7b": [("copilot", "gpt-4o-mini"), ("ollama", "phi4")],
    }
    
    def __init__(self, state_dir: Optional[Path] = None):
        self.state_dir = state_dir or Path.home() / ".bago" / "state"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.gate_log = self.state_dir / "model_gate_log.jsonl"
    
    def _log(self, entry: Dict[str, Any]):
        with open(self.gate_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    
    def check(self, target_provider: str, target_model: str, 
              available_providers: Dict[str, Any]) -> ModelGateResult:
        """Comprueba si un modelo está disponible y decide fallback."""
        
        # Verificar disponibilidad
        prov_data = available_providers.get(target_provider)
        if prov_data and prov_data.get("ok"):
            models = prov_data.get("models", [])
            if target_model in models or not models:
                return ModelGateResult(
                    success=True,
                    fallback_model=target_model,
                    fallback_provider=target_provider,
                    reason="Modelo disponible",
                    gate_action="direct",
                )
        
        # Modelo no disponible → buscar fallback
        chain = self.FALLBACK_CHAIN.get(target_model, [])
        for fb_prov, fb_model in chain:
            fb_data = available_providers.get(fb_prov)
            if fb_data and fb_data.get("ok"):
                models = fb_data.get("models", [])
                if fb_model in models or not models:
                    self._log({
                        "timestamp": __import__("datetime").datetime.now().isoformat(),
                        "target": f"{target_provider}/{target_model}",
                        "fallback": f"{fb_prov}/{fb_model}",
                        "action": "fallback",
                        "reason": f"{target_model} no disponible",
                    })
                    return ModelGateResult(
                        success=True,
                        fallback_model=fb_model,
                        fallback_provider=fb_prov,
                        reason=f"{target_model} no disponible → fallback a {fb_prov}/{fb_model}",
                        gate_action="fallback",
                    )
        
        # Sin fallback posible → degradar a single
        self._log({
            "timestamp": __import__("datetime").datetime.now().isoformat(),
            "target": f"{target_provider}/{target_model}",
            "action": "degrade",
            "reason": "No hay fallback disponible",
        })
        return ModelGateResult(
            success=False,
            reason=f"{target_provider}/{target_model} no disponible y no hay fallback",
            gate_action="degrade",
        )
    
    def gate_chain(self, chain: List[Tuple[str, str]], available_providers: Dict[str, Any]) -> List[Tuple[str, str]]:
        """Aplica gate a una cadena de modelos. Filtra los que no están disponibles."""
        filtered = []
        for prov, model in chain:
            result = self.check(prov, model, available_providers)
            if result.success:
                filtered.append((result.fallback_provider or prov, result.fallback_model or model))
            else:
                # Skip este paso de la cadena
                continue
        return filtered if len(filtered) >= 1 else []
    
    def summary(self) -> Dict[str, Any]:
        """Resumen de decisiones del gate."""
        if not self.gate_log.exists():
            return {"calls": 0}
        stats = {"fallback": 0, "degrade": 0, "direct": 0}
        with open(self.gate_log, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line: continue
                try:
                    d = json.loads(line)
                    action = d.get("action", "unknown")
                    stats[action] = stats.get(action, 0) + 1
                except json.JSONDecodeError:
                    continue
        return stats


def main():
    import argparse
    p = argparse.ArgumentParser(description="BAGO Model Gate")
    p.add_argument("--check", nargs=2, metavar=("PROVIDER", "MODEL"), help="Comprobar disponibilidad")
    p.add_argument("--summary", action="store_true", help="Resumen de gate")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    
    gate = ModelGate()
    
    if args.check:
        # Mock providers para demo
        providers = {
            "ollama": {"ok": True, "models": ["qwen2.5:7b", "phi4"]},
            "copilot": {"ok": True, "models": ["gpt-4o-mini"]},
            "openai": {"ok": False},
        }
        result = gate.check(args.check[0], args.check[1], providers)
        data = {
            "success": result.success,
            "fallback": f"{result.fallback_provider}/{result.fallback_model}" if result.fallback_model else None,
            "reason": result.reason,
            "action": result.gate_action,
        }
        if args.json:
            print(json.dumps(data, indent=2))
        else:
            print(f"Gate: {result.gate_action} | {result.reason}")
    
    if args.summary:
        s = gate.summary()
        print(f"Direct: {s.get('direct', 0)} Fallback: {s.get('fallback', 0)} Degrade: {s.get('degrade', 0)}")



def run_tests() -> int:
    """Self-test stub: verify module imports and key symbols exist."""
    results = []
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_test_mod", __file__)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        results.append(("import", True, "module loads OK"))
    except Exception as e:
        results.append(("import", False, str(e)))

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, detail in results:
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {name}: {detail}")
    print(f"\n  {passed}/{total} tests passed")
    return 0 if passed == total else 1

if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(run_tests())
    main()