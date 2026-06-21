#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
role_factory.py — FÁBRICA DE ROLES BAGO

Sistema para CREAR, VALIDAR y GESTIONAR roles especializados.

Cada rol es un especialista con responsabilidades claras:
- GOVERNMENT: Gobierno de BAGO
- SPECIALIST: Análisis profundo en dominio
- SUPERVISION: Verificación de calidad
- PRODUCTION: Operaciones

Uso:
  python role_factory.py create --family specialist --name security_auditor
  python role_factory.py validate SECURITY_AUDITOR.md
  python role_factory.py list
  python role_factory.py list --family specialist
"""

from pathlib import Path
import json
import sys
from datetime import datetime, timezone

ROLES_DIR = Path(__file__).resolve().parent
TEMPLATE = ROLES_DIR / "ROLE_TEMPLATE.md"
MANIFEST = ROLES_DIR / "manifest.json"

FAMILIES = {
    "gobierno": "GOVERNMENT — Gobierno central de BAGO",
    "especialistas": "SPECIALIST — Análisis en dominio específico",
    "supervision": "SUPERVISION — Verificación de calidad",
    "produccion": "PRODUCTION — Operaciones y despliegue"
}

ROLE_TEMPLATE = """# {name_upper}

## Identidad

- id: role_{family}_{name}
- family: {family}
- version: 2.5-stable

## Propósito

{propósito}

## Alcance

{alcance}

## Límites

{limites}

## Entradas

{entradas}

## Salidas

{salidas}

## Activación

{activación}

## No Activación

{no_activación}

## Dependencias

{dependencias}

## Criterio de Éxito

{criterio}
"""


def load_manifest() -> dict:
    """Carga manifest de roles."""
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {"roles": {}, "created": datetime.now(timezone.utc).isoformat()}


def save_manifest(manifest: dict):
    """Guarda manifest."""
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def role_exists(name: str, family: str = None) -> bool:
    """Verifica si rol existe."""
    if family:
        path = ROLES_DIR / family / f"{name.upper()}.md"
        return path.exists()
    
    # Buscar en todas las familias
    for f in FAMILIES.keys():
        if (ROLES_DIR / f / f"{name.upper()}.md").exists():
            return True
    return False


def validate_role(filepath: str) -> tuple[bool, list[str]]:
    """
    Valida estructura de un rol.
    
    Retorna: (is_valid, list_of_errors)
    """
    path = Path(filepath)
    if not path.exists():
        return False, [f"Archivo no existe: {filepath}"]
    
    content = path.read_text(encoding="utf-8")
    errors = []
    
    # Secciones requeridas
    required = [
        "## Identidad",
        "## Propósito",
        "## Alcance",
        "## Límites",
        "## Entradas",
        "## Salidas",
        "## Activación",
        "## No Activación",
        "## Dependencias",
        "## Criterio de Éxito"
    ]
    
    for section in required:
        if section not in content:
            errors.append(f"Falta sección: {section}")
    
    # Validar ID
    if "- id: role_" not in content:
        errors.append("Falta ID válido (debe ser: role_{familia}_{nombre})")
    
    # Validar family
    if "- family:" not in content:
        errors.append("Falta familia (government|specialist|supervision|production)")
    
    return len(errors) == 0, errors


def create_role(family: str, name: str, propósito: str, alcance: list,
                limites: str, entradas: list, salidas: list,
                activación: str, no_activación: str, dependencias: list,
                criterio: str) -> bool:
    """Crea nuevo rol."""
    
    # Validar familia
    if family not in FAMILIES.keys():
        print(f"❌ Familia inválida: {family}")
        print(f"   Válidas: {', '.join(FAMILIES.keys())}")
        return False
    
    # Validar nombre
    if not name or not name.replace('_', '').isalnum():
        print(f"❌ Nombre inválido: {name}")
        return False
    
    # Verificar que no existe
    if role_exists(name, family):
        print(f"❌ Rol ya existe: {family}/{name}")
        return False
    
    # Formatear alcance/entradas/salidas/dependencias
    alcance_text = '\n'.join(f"- {item}" for item in (alcance or ["(especificar)"]))
    entradas_text = '\n'.join(f"- {item}" for item in (entradas or ["(especificar)"]))
    salidas_text = '\n'.join(f"- {item}" for item in (salidas or ["(especificar)"]))
    dependencias_text = '\n'.join(f"- {item}" for item in (dependencias or ["(especificar)"]))
    
    # Generar contenido
    content = ROLE_TEMPLATE.format(
        name_upper=name.upper(),
        family=family,
        name=name,
        propósito=propósito or "(especificar)",
        alcance=alcance_text,
        limites=limites or "(especificar)",
        entradas=entradas_text,
        salidas=salidas_text,
        activación=activación or "(especificar)",
        no_activación=no_activación or "(especificar)",
        dependencias=dependencias_text,
        criterio=criterio or "(especificar)"
    )
    
    # Crear archivo
    role_file = ROLES_DIR / family / f"{name.upper()}.md"
    try:
        role_file.write_text(content, encoding="utf-8")
        print(f"✅ Rol creado: {family}/{name.upper()}.md")
    except Exception as e:
        print(f"❌ Error creando rol: {e}")
        return False
    
    # Registrar en manifest
    manifest = load_manifest()
    manifest["roles"][f"role_{family}_{name}"] = {
        "family": family,
        "name": name,
        "file": str(role_file.relative_to(ROLES_DIR)),
        "created": datetime.now(timezone.utc).isoformat(),
        "status": "active"
    }
    save_manifest(manifest)
    print(f"📝 Registrado en manifest")
    
    return True


def list_roles(family: str = None) -> None:
    """Lista roles disponibles."""
    manifest = load_manifest()
    roles = manifest.get("roles", {})
    
    if not roles:
        print("❌ Sin roles registrados")
        return
    
    # Filtrar por familia si se especifica
    if family:
        roles = {k: v for k, v in roles.items() if v.get("family") == family}
    
    if not roles:
        print(f"❌ Sin roles en familia: {family}")
        return
    
    print()
    print(f"{'ID':<40} {'Family':<15} {'Status':<10}")
    print("─" * 65)
    
    for role_id, info in sorted(roles.items()):
        fam = info.get("family", "?")
        status = info.get("status", "?")
        print(f"{role_id:<40} {fam:<15} {status:<10}")
    
    print()


def describe_families() -> None:
    """Describe las familias de roles."""
    print("\n📚 Familias de Roles BAGO\n")
    for family, description in FAMILIES.items():
        print(f"  {family:<15} → {description}")
    print()


def main():
    """CLI de factory."""
    if len(sys.argv) < 2:
        print("role_factory.py — Generador de Roles BAGO")
        print("\nUso:")
        print("  python role_factory.py create --family {familia} --name {nombre}")
        print("  python role_factory.py validate {archivo}")
        print("  python role_factory.py list [--family {familia}]")
        print("  python role_factory.py families")
        print("\nFamilias:")
        describe_families()
        print("Ejemplo:")
        print("  python role_factory.py create --family especialistas --name security_auditor")
        return
    
    cmd = sys.argv[1]
    
    if cmd == "create":
        family = None
        name = None
        
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == "--family" and i + 1 < len(sys.argv):
                family = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--name" and i + 1 < len(sys.argv):
                name = sys.argv[i + 1]
                i += 2
            else:
                i += 1
        
        if not family or not name:
            print("❌ Sintaxis: create --family {familia} --name {nombre}")
            describe_families()
            return
        
        create_role(
            family=family,
            name=name,
            propósito="(especificar en el MD)",
            alcance=[],
            limites="(especificar en el MD)",
            entradas=[],
            salidas=[],
            activación="(especificar en el MD)",
            no_activación="(especificar en el MD)",
            dependencias=[],
            criterio="(especificar en el MD)"
        )
    
    elif cmd == "validate":
        if len(sys.argv) < 3:
            print("❌ Sintaxis: validate {archivo}")
            return
        
        filepath = sys.argv[2]
        valid, errors = validate_role(filepath)
        
        if valid:
            print(f"✅ Rol válido: {filepath}")
        else:
            print(f"❌ Rol inválido: {filepath}")
            for error in errors:
                print(f"   • {error}")
    
    elif cmd == "list":
        family = None
        if "--family" in sys.argv:
            idx = sys.argv.index("--family")
            if idx + 1 < len(sys.argv):
                family = sys.argv[idx + 1]
        
        list_roles(family)
    
    elif cmd == "families":
        describe_families()
    
    else:
        print(f"❌ Comando desconocido: {cmd}")


if __name__ == "__main__":
    main()
