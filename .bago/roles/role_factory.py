#!/usr/bin/env python3
# -*- coding: utf-8 -*-
\"\"\"role_factory.py — FABRICA DE ROLES BAGO v2 (con codigo embebido indexado)

Sistema para CREAR, VALIDAR y GESTIONAR roles especializados con artefactos
indexados en espiral.

Uso:
  python role_factory.py create --family specialist --name security_auditor
  python role_factory.py validate SECURITY_AUDITOR.md
  python role_factory.py list
  python role_factory.py list --family specialist
  python role_factory.py embed --role ARQUITECTO --artifact "snippet:python/error_handling" --priority 2 --condition "cycle >= 2"
  python role_factory.py artifacts
  python role_factory.py prompt --role role_production_architect --cycle 2 --radius 1.5 --task-type architecture
\"\"\"

from pathlib import Path
import json
import sys
from datetime import datetime, timezone

ROLES_DIR = Path(__file__).resolve().parent
BAGO_DIR = ROLES_DIR.parent
ARTIFACTS_DIR = BAGO_DIR / "artifacts"
TEMPLATE = ROLES_DIR / "ROLE_TEMPLATE.md"
MANIFEST = ROLES_DIR / "manifest.json"

FAMILIES = {
    "gobierno": "GOVERNMENT — Gobierno central de BAGO",
    "especialistas": "SPECIALIST — Analisis en dominio especifico",
    "supervision": "SUPERVISION — Verificacion de calidad",
    "produccion": "PRODUCTION — Operaciones y despliegue"
}

ROLE_TEMPLATE_MD = \"\"\"# {name_upper}

## Identidad

- id: role_{family}_{name}
- family: {family}
- version: 3.4.2

## Proposito

{proposito}

## Alcance

{alcance}

## Limites

{limites}

## Entradas

{entradas}

## Salidas

{salidas}

## Activacion

{activacion}

## No Activacion

{no_activacion}

## Dependencias

{dependencias}

## Criterio de Exito

{criterio}
\"\"\"

ROLE_EMBED_TEMPLATE = {
    "schema_version": "1.0.0",
    "role_id": "role_{family}_{name}",
    "role_family": "{family}",
    "version": "3.4.2",
    "spiral_rules": {
        "min_cycle": 1,
        "max_cycle": None,
        "radius_thresholds": {
            "1.0": "base_identity + purpose",
            "1.5": "+ context_expansion + relevant_artifacts",
            "2.0": "+ specialization + deep_snippets"
        }
    },
    "artifacts": [],
    "prompt_template": {
        "head": "[IDENTIDAD]\\n{base_identity}\\n\\n[PROPOSITO]\\n{role_purpose}\\n",
        "body": "\\n[ARTEFACTOS DE CONTEXTO]\\n{context_artifacts}\\n\\n[SNIPPETS Y COMANDOS]\\n{specialized_artifacts}\\n",
        "tail": "\\n[INSTRUCCIONES ESPIRAL]\\nEste es el ciclo {cycle} con radio {radius}.\\nConstruye la solucion acumulativamente. No invalides decisiones previas sin nueva evidencia.\\nSi detectas un gate KO, detente y reporta.\\n"
    },
    "dynamic_bindings": {
        "role_purpose": "(especificar proposito del rol)",
        "role_constraints": []
    }
}


def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {"roles": {}, "created": datetime.now(timezone.utc).isoformat()}


def save_manifest(manifest: dict):
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def role_exists(name: str, family: str = None) -> bool:
    if family:
        return (ROLES_DIR / family / f"{name.upper()}.md").exists()
    for f in FAMILIES.keys():
        if (ROLES_DIR / f / f"{name.upper()}.md").exists():
            return True
    return False


def validate_role(filepath: str) -> tuple[bool, list[str]]:
    path = Path(filepath)
    if not path.exists():
        return False, [f"Archivo no existe: {filepath}"]
    content = path.read_text(encoding="utf-8")
    errors = []
    required = [
        "## Identidad", "## Proposito", "## Alcance", "## Limites",
        "## Entradas", "## Salidas", "## Activacion",
        "## No Activacion", "## Dependencias", "## Criterio de Exito"
    ]
    for section in required:
        if section not in content:
            errors.append(f"Falta seccion: {section}")
    if "- id: role_" not in content:
        errors.append("Falta ID valido")
    if "- family:" not in content:
        errors.append("Falta familia")
    return len(errors) == 0, errors


def create_role(family: str, name: str, **fields) -> bool:
    if family not in FAMILIES.keys():
        print(f"❌ Familia invalida: {family}")
        return False
    if not name or not name.replace('_', '').isalnum():
        print(f"❌ Nombre invalido: {name}")
        return False
    if role_exists(name, family):
        print(f"❌ Rol ya existe: {family}/{name}")
        return False

    role_file = ROLES_DIR / family / f"{name.upper()}.md"
    alcance_text = '\\n'.join(f"- {item}" for item in (fields.get("alcance") or ["(especificar)"]))
    entradas_text = '\\n'.join(f"- {item}" for item in (fields.get("entradas") or ["(especificar)"]))
    salidas_text = '\\n'.join(f"- {item}" for item in (fields.get("salidas") or ["(especificar)"]))
    dependencias_text = '\\n'.join(f"- {item}" for item in (fields.get("dependencias") or ["(especificar)"]))

    content = ROLE_TEMPLATE_MD.format(
        name_upper=name.upper(),
        family=family,
        name=name,
        proposito=fields.get("proposito", "(especificar)"),
        alcance=alcance_text,
        limites=fields.get("limites", "(especificar)"),
        entradas=entradas_text,
        salidas=salidas_text,
        activacion=fields.get("activacion", "(especificar)"),
        no_activacion=fields.get("no_activacion", "(especificar)"),
        dependencias=dependencias_text,
        criterio=fields.get("criterio", "(especificar)")
    )
    role_file.write_text(content, encoding="utf-8")
    print(f"✅ Rol creado: {family}/{name.upper()}.md")

    # Crear .embed.json base
    embed = json.loads(json.dumps(ROLE_EMBED_TEMPLATE).replace("{family}", family).replace("{name}", name))
    embed["role_id"] = f"role_{family}_{name}"
    embed["role_family"] = family
    embed["dynamic_bindings"]["role_purpose"] = fields.get("proposito", "(especificar)")
    embed_file = ROLES_DIR / family / f"{name.upper()}.embed.json"
    embed_file.write_text(json.dumps(embed, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"📝 Embed creado: {family}/{name.upper()}.embed.json")

    # Registrar en manifest
    manifest = load_manifest()
    manifest["roles"][f"role_{family}_{name}"] = {
        "family": family,
        "name": name,
        "file": str(role_file.relative_to(ROLES_DIR)),
        "embed": str(embed_file.relative_to(ROLES_DIR)),
        "created": datetime.now(timezone.utc).isoformat(),
        "status": "active"
    }
    save_manifest(manifest)
    print(f"📝 Registrado en manifest")
    return True


def list_roles(family: str = None) -> None:
    manifest = load_manifest()
    roles = manifest.get("roles", {})
    if family:
        roles = {k: v for k, v in roles.items() if v.get("family") == family}
    if not roles:
        print(f"❌ Sin roles registrados" + (f" en familia: {family}" if family else ""))
        return
    print(f"{'ID':<45} {'Family':<15} {'Embed':<10} {'Status':<10}")
    print("─" * 80)
    for role_id, info in sorted(roles.items()):
        fam = info.get("family", "?")
        status = info.get("status", "?")
        has_embed = "✅" if info.get("embed") else "❌"
        print(f"{role_id:<45} {fam:<15} {has_embed:<10} {status:<10}")
    print()


def list_artifacts() -> None:
    index_path = ARTIFACTS_DIR / "index.json"
    if not index_path.exists():
        print("❌ No hay indice de artefactos")
        return
    index = json.loads(index_path.read_text(encoding="utf-8"))
    artifacts = index.get("artifacts", {})
    print(f"{'Ref':<45} {'Type':<12} {'Tags':<30}")
    print("─" * 90)
    for ref, meta in sorted(artifacts.items()):
        t = meta.get("type", "?")
        tags = ", ".join(meta.get("tags", [])[:3])
        print(f"{ref:<45} {t:<12} {tags:<30}")
    print(f"\nTotal artefactos indexados: {len(artifacts)}")


def embed_artifact(role_name: str, family: str, artifact_ref: str, priority: int = 2,
                   layer: str = "context", condition: str = "", inject_at: str = "body",
                   fmt: str = "") -> bool:
    embed_path = ROLES_DIR / family / f"{role_name.upper()}.embed.json"
    if not embed_path.exists():
        print(f"❌ Embed no encontrado: {embed_path}")
        return False
    embed = json.loads(embed_path.read_text(encoding="utf-8"))
    artifacts = embed.get("artifacts", [])
    # Check if already exists
    for a in artifacts:
        if a.get("ref") == artifact_ref:
            print(f"⚠️  Artefacto ya embebido: {artifact_ref}")
            return False
    artifacts.append({
        "ref": artifact_ref,
        "priority": priority,
        "layer": layer,
        "condition": condition or "cycle >= 1",
        "inject_at": inject_at,
        **({"format": fmt} if fmt else {})
    })
    embed["artifacts"] = artifacts
    embed_path.write_text(json.dumps(embed, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅ Artefacto embebido: {artifact_ref} → {family}/{role_name}")
    return True


def build_prompt(role_id: str, cycle: int = 1, radius: float = 1.0, task_type: str = "") -> None:
    sys.path.insert(0, str(BAGO_DIR / "core"))
    try:
        from spiral_prompt_builder import SpiralPromptBuilder
    except ImportError as e:
        print(f"❌ No se pudo importar spiral_prompt_builder: {e}")
        return
    builder = SpiralPromptBuilder(BAGO_DIR.parent)
    prompt = builder.build(role_id, cycle, radius, task_type)
    print(prompt)


def describe_families() -> None:
    print("\n📚 Familias de Roles BAGO\n")
    for family, description in FAMILIES.items():
        print(f"  {family:<15} → {description}")
    print()


def main():
    if len(sys.argv) < 2:
        print("role_factory.py — Generador de Roles BAGO v2\n")
        print("Uso:")
        print("  python role_factory.py create --family {familia} --name {nombre}")
        print("  python role_factory.py validate {archivo}")
        print("  python role_factory.py list [--family {familia}]")
        print("  python role_factory.py families")
        print("  python role_factory.py artifacts")
        print("  python role_factory.py embed --role {ROL} --family {familia} --artifact {ref}")
        print("  python role_factory.py prompt --role {role_id} [--cycle N] [--radius R] [--task-type T]")
        print("\nEjemplo:")
        print("  python role_factory.py create --family especialistas --name security_auditor")
        print("  python role_factory.py embed --role ARQUITECTO --family produccion --artifact \"snippet:python/error_handling\" --priority 3 --layer specialization --condition \"cycle >= 3\"")
        print("  python role_factory.py prompt --role role_production_architect --cycle 2 --radius 1.5 --task-type architecture")
        return

    cmd = sys.argv[1]

    if cmd == "create":
        family = name = None
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == "--family" and i + 1 < len(sys.argv):
                family = sys.argv[i + 1]; i += 2
            elif sys.argv[i] == "--name" and i + 1 < len(sys.argv):
                name = sys.argv[i + 1]; i += 2
            else:
                i += 1
        if not family or not name:
            print("❌ Sintaxis: create --family {familia} --name {nombre}")
            describe_families()
            return
        create_role(family=family, name=name)

    elif cmd == "validate":
        if len(sys.argv) < 3:
            print("❌ Sintaxis: validate {archivo}"); return
        filepath = sys.argv[2]
        valid, errors = validate_role(filepath)
        print(f"{'✅' if valid else '❌'} Rol: {filepath}")
        for e in errors:
            print(f"   • {e}")

    elif cmd == "list":
        family = None
        if "--family" in sys.argv:
            idx = sys.argv.index("--family")
            if idx + 1 < len(sys.argv):
                family = sys.argv[idx + 1]
        list_roles(family)

    elif cmd == "families":
        describe_families()

    elif cmd == "artifacts":
        list_artifacts()

    elif cmd == "embed":
        role = family = artifact = condition = fmt = ""
        priority = 2
        layer = "context"
        inject_at = "body"
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == "--role" and i + 1 < len(sys.argv):
                role = sys.argv[i + 1]; i += 2
            elif sys.argv[i] == "--family" and i + 1 < len(sys.argv):
                family = sys.argv[i + 1]; i += 2
            elif sys.argv[i] == "--artifact" and i + 1 < len(sys.argv):
                artifact = sys.argv[i + 1]; i += 2
            elif sys.argv[i] == "--priority" and i + 1 < len(sys.argv):
                priority = int(sys.argv[i + 1]); i += 2
            elif sys.argv[i] == "--layer" and i + 1 < len(sys.argv):
                layer = sys.argv[i + 1]; i += 2
            elif sys.argv[i] == "--condition" and i + 1 < len(sys.argv):
                condition = sys.argv[i + 1]; i += 2
            elif sys.argv[i] == "--inject-at" and i + 1 < len(sys.argv):
                inject_at = sys.argv[i + 1]; i += 2
            elif sys.argv[i] == "--format" and i + 1 < len(sys.argv):
                fmt = sys.argv[i + 1]; i += 2
            else:
                i += 1
        if not role or not family or not artifact:
            print("❌ Sintaxis: embed --role {ROL} --family {familia} --artifact {ref} [--priority N] [--layer L] [--condition \"...\"] [--inject-at head|body|tail|commands]")
            return
        embed_artifact(role, family, artifact, priority, layer, condition, inject_at, fmt)

    elif cmd == "prompt":
        role_id = ""
        cycle = 1
        radius = 1.0
        task_type = ""
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == "--role" and i + 1 < len(sys.argv):
                role_id = sys.argv[i + 1]; i += 2
            elif sys.argv[i] == "--cycle" and i + 1 < len(sys.argv):
                cycle = int(sys.argv[i + 1]); i += 2
            elif sys.argv[i] == "--radius" and i + 1 < len(sys.argv):
                radius = float(sys.argv[i + 1]); i += 2
            elif sys.argv[i] == "--task-type" and i + 1 < len(sys.argv):
                task_type = sys.argv[i + 1]; i += 2
            else:
                i += 1
        if not role_id:
            print("❌ Sintaxis: prompt --role {role_id} [--cycle N] [--radius R] [--task-type T]")
            return
        build_prompt(role_id, cycle, radius, task_type)

    else:
        print(f"❌ Comando desconocido: {cmd}")


if __name__ == "__main__":
    main()
