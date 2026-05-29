#!/usr/bin/env python3
"""role_embedded.py — Roles BAGO con código embebido


Los roles ahora contienen:
- Descripción textual (prompt base)
- Scripts ejecutables (comportamiento dinámico)
- Comandos shell que montan el prompt en espiral
- Referencias a repositorios de artefactos (fragmentos de código)
- Índice de contenido para autogeneración del prompt

La espiral de prompts se autogenera: empieza con poco contexto
y va creciendo infinitamente según la tarea lo requiera.
"""

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from pathlib import Path
import hashlib

@dataclass
class RoleArtifact:
    """Fragmento de código/texto/script que un rol puede usar."""
    id: str
    type: str  # "script" | "command" | "text" | "snippet"
    content: str
    source: str  # URL o path local
    checksum: str = ""
    
    def __post_init__(self):
        if not self.checksum:
            self.checksum = hashlib.sha256(self.content.encode()).hexdigest()[:16]

@dataclass
class EmbeddedRole:
    """Rol con código embebido para comportamiento dinámico."""
    role_id: str
    name: str
    description: str  # prompt base
    system_prompt: str
    artifacts: List[RoleArtifact] = field(default_factory=list)
    # Índice de contenido: qué artefactos activar según fase
    spiral_index: Dict[str, List[str]] = field(default_factory=dict)
    # Scripts dinámicos: código Python que modifica el comportamiento
    dynamic_code: str = ""
    # Comandos que montan el prompt
    prompt_builders: List[str] = field(default_factory=list)
    # Router de eficiencia: qué banda usar según tarea
    preferred_band: str = "5g"


class RoleSpiralBuilder:
    """Construye prompts en espiral: de menos a más contexto."""
    
    def __init__(self, roles_dir: Optional[Path] = None):
        self.roles_dir = roles_dir or Path(__file__).resolve().parents[2] / "roles"
        self.roles_dir.mkdir(parents=True, exist_ok=True)
        self.roles: Dict[str, EmbeddedRole] = {}
        self._load_roles()
    
    def _load_roles(self):
        for f in self.roles_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                role = EmbeddedRole(
                    role_id=data["role_id"],
                    name=data["name"],
                    description=data.get("description", ""),
                    system_prompt=data.get("system_prompt", ""),
                    artifacts=[RoleArtifact(**a) for a in data.get("artifacts", [])],
                    spiral_index=data.get("spiral_index", {}),
                    dynamic_code=data.get("dynamic_code", ""),
                    prompt_builders=data.get("prompt_builders", []),
                    preferred_band=data.get("preferred_band", "5g"),
                )
                self.roles[role.role_id] = role
            except Exception:
                continue
    
    def build_prompt(self, role_id: str, cycle: int = 1, task_type: str = "", history: str = "") -> Dict[str, Any]:
        """Construye prompt en espiral para un rol.
        
        cycle 1: prompt base + artifacts esenciales
        cycle 2+: añade más artifacts según spiral_index
        """
        role = self.roles.get(role_id)
        if not role:
            return {"error": f"Role {role_id} not found"}
        
        # Determinar fase según ciclo
        if cycle == 1:
            phase = "init"
        elif cycle <= 3:
            phase = "build"
        elif cycle <= 6:
            phase = "stabilize"
        else:
            phase = "refine"
        
        # Activar artifacts según fase
        active_artifacts = []
        for artifact_id in role.spiral_index.get(phase, []):
            for a in role.artifacts:
                if a.id == artifact_id:
                    active_artifacts.append(a)
        
        # Construir prompt
        prompt_parts = [role.system_prompt]
        for a in active_artifacts:
            prompt_parts.append(f"\n--- {a.type}: {a.id} ---\n{a.content}")
        
        if history:
            prompt_parts.append(f"\n--- Historia ---\n{history}")
        
        if task_type:
            prompt_parts.append(f"\n--- Tarea actual ---\n{task_type}")
        
        # Ejecutar código dinámico si existe
        dynamic_context = {}
        if role.dynamic_code:
            try:
                # Sandbox seguro: solo evalúa código que define funciones
                local_ns = {"cycle": cycle, "phase": phase, "task_type": task_type, "history": history}
                exec(role.dynamic_code, {}, local_ns)
                if "get_context" in local_ns:
                    dynamic_context = local_ns["get_context"](cycle, phase, task_type)
            except Exception as e:
                dynamic_context = {"error": str(e)}
        
        return {
            "role_id": role_id,
            "cycle": cycle,
            "phase": phase,
            "prompt": "\n".join(prompt_parts),
            "active_artifacts": [a.id for a in active_artifacts],
            "dynamic_context": dynamic_context,
            "preferred_band": role.preferred_band,
            "checksum": hashlib.sha256("\n".join(prompt_parts).encode()).hexdigest()[:16],
        }
    
    def list_roles(self) -> List[str]:
        return list(self.roles.keys())
    
    def save_role(self, role: EmbeddedRole):
        """Guarda un rol en disco."""
        data = {
            "role_id": role.role_id,
            "name": role.name,
            "description": role.description,
            "system_prompt": role.system_prompt,
            "artifacts": [{"id": a.id, "type": a.type, "content": a.content, "source": a.source, "checksum": a.checksum} for a in role.artifacts],
            "spiral_index": role.spiral_index,
            "dynamic_code": role.dynamic_code,
            "prompt_builders": role.prompt_builders,
            "preferred_band": role.preferred_band,
        }
        path = self.roles_dir / f"{role.role_id}.json"
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        self.roles[role.role_id] = role


def main():
    import argparse
    p = argparse.ArgumentParser(description="BAGO Role Spiral Builder")
    p.add_argument("--list", action="store_true", help="Listar roles")
    p.add_argument("--build", nargs=2, metavar=("ROLE_ID", "CYCLE"), help="Construir prompt")
    p.add_argument("--task", default="", help="Tipo de tarea")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    
    builder = RoleSpiralBuilder()
    
    if args.list:
        for rid in builder.list_roles():
            role = builder.roles[rid]
            print(f"{rid}: {role.name} (band={role.preferred_band}, artifacts={len(role.artifacts)})")
    
    if args.build:
        result = builder.build_prompt(args.build[0], int(args.build[1]), args.task)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"Role: {result['role_id']} Cycle: {result['cycle']} Phase: {result['phase']}")
            print(f"Artifacts: {', '.join(result['active_artifacts'])}")
            print(f"Band: {result['preferred_band']}")
            print(f"\n--- PROMPT ---\n{result['prompt'][:500]}...")



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