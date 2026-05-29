#!/usr/bin/env python3
"""role_contract_validator.py — Validador de contratos de roles BAGO.

Parsea los ficheros markdown de roles (que ya contienen Entradas/Salidas/Límites/
Criterio de éxito estructurados) y valida si una sesión usó el rol correctamente.

Los roles BAGO tienen formato canónico:
  ## Entradas     → lista de inputs requeridos
  ## Salidas      → lista de outputs esperados
  ## Límites      → restricciones del rol
  ## Criterio de éxito → condición de éxito

Uso:
    python3 role_contract_validator.py --list                # lista todos los roles
    python3 role_contract_validator.py --show ROLE_ID        # muestra el contrato de un rol
    python3 role_contract_validator.py --validate SESSION_JSON  # valida una sesión
    python3 role_contract_validator.py --export              # exporta todos los contratos en JSON
    python3 role_contract_validator.py --test                # self-tests
"""
from __future__ import annotations

from bago_utils import load_json, save_json, timestamp_iso

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

BAGO_ROOT  = Path(__file__).parent.parent
ROLES_DIRS = [
    BAGO_ROOT / "roles" / "gobierno",
    BAGO_ROOT / "roles" / "produccion",
    BAGO_ROOT / "roles" / "especialistas",
    BAGO_ROOT / "roles" / "supervision",
]

_GRN  = "\033[0;32m"
_YEL  = "\033[0;33m"
_RED  = "\033[0;31m"
_CYN  = "\033[0;36m"
_RST  = "\033[0m"
_BOLD = "\033[1m"


# ── Contrato parseado ──────────────────────────────────────────────────────────

@dataclass
class RoleContract:
    role_id:         str
    family:          str
    version:         str
    purpose:         str
    alcance:         list[str] = field(default_factory=list)
    entradas:        list[str] = field(default_factory=list)
    salidas:         list[str] = field(default_factory=list)
    limites:         list[str] = field(default_factory=list)
    activacion:      list[str] = field(default_factory=list)
    no_activacion:   list[str] = field(default_factory=list)
    dependencias:    list[str] = field(default_factory=list)
    criterio_exito:  list[str] = field(default_factory=list)
    source_file:     str = ""

    def to_dict(self) -> dict:
        return {
            "role_id":        self.role_id,
            "family":         self.family,
            "version":        self.version,
            "purpose":        self.purpose,
            "alcance":        self.alcance,
            "entradas":       self.entradas,
            "salidas":        self.salidas,
            "limites":        self.limites,
            "activacion":     self.activacion,
            "no_activacion":  self.no_activacion,
            "dependencias":   self.dependencias,
            "criterio_exito": self.criterio_exito,
            "source_file":    self.source_file,
        }


# ── Parser ─────────────────────────────────────────────────────────────────────

def _parse_list_section(lines: list[str], start: int) -> list[str]:
    """Extrae items de una sección markdown (líneas `- item`) desde start."""
    items = []
    for line in lines[start:]:
        stripped = line.strip()
        if stripped.startswith("## "):
            break
        if stripped.startswith("- "):
            items.append(stripped[2:].strip())
        elif stripped.startswith("* "):
            items.append(stripped[2:].strip())
    return items


def _parse_identity_field(lines: list[str], field_name: str) -> str:
    """Extrae valor de `- field_name: valor` dentro de ## Identidad."""
    pattern = re.compile(rf"^[-*]\s+{re.escape(field_name)}:\s*(.+)$", re.IGNORECASE)
    for line in lines:
        m = pattern.match(line.strip())
        if m:
            return m.group(1).strip()
    return ""


def parse_role_file(path: Path) -> RoleContract | None:
    """Parsea un fichero .md de rol y devuelve su contrato."""
    try:
        text = path.read_text("utf-8")
    except OSError:
        return None

    lines = text.splitlines()

    # Extraer identidad
    role_id = _parse_identity_field(lines, "id")
    family  = _parse_identity_field(lines, "family")
    version = _parse_identity_field(lines, "version")

    if not role_id:
        role_id = path.stem.lower()

    # Extraer propósito (primera línea de contenido tras ## Propósito)
    purpose = ""
    for i, line in enumerate(lines):
        if line.strip().startswith("## Propósito") or line.strip().startswith("## Proposito"):
            for j in range(i + 1, len(lines)):
                content = lines[j].strip()
                if content and not content.startswith("#"):
                    purpose = content
                    break
            break

    # Extraer secciones de lista
    section_map = {
        "entradas":       [],
        "salidas":        [],
        "alcance":        [],
        "límites":        [],  # noqa: SPANISH — tolerancia de ortografía intencional
        "limites":        [],  # noqa: SPANISH
        "activación":     [],  # noqa: SPANISH
        "activacion":     [],  # noqa: SPANISH
        "no activación":  [],  # noqa: SPANISH
        "no activacion":  [],  # noqa: SPANISH
        "dependencias":   [],
        "criterio de éxito": [],  # noqa: SPANISH
        "criterio de exito": [],  # noqa: SPANISH
    }

    current_section: str | None = None
    section_lines: dict[str, list[str]] = {k: [] for k in section_map}

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            header = stripped[3:].lower().strip()
            current_section = header if header in section_lines else None
        elif current_section is not None:
            section_lines[current_section].append(line)

    def _items(key: str) -> list[str]:
        items = []
        for line in section_lines.get(key, []):
            s = line.strip()
            if s.startswith("- ") or s.startswith("* "):
                items.append(s[2:].strip())
        return items

    return RoleContract(
        role_id        = role_id,
        family         = family,
        version        = version,
        purpose        = purpose,
        alcance        = _items("alcance"),
        entradas       = _items("entradas"),
        salidas        = _items("salidas"),
        limites        = _items("límites") or _items("limites"),
        activacion     = _items("activación") or _items("activacion"),
        no_activacion  = _items("no activación") or _items("no activacion"),
        dependencias   = _items("dependencias"),
        criterio_exito = _items("criterio de éxito") or _items("criterio de exito"),
        source_file    = str(path.relative_to(BAGO_ROOT)),
    )


# ── Carga de todos los roles ───────────────────────────────────────────────────

def load_all_contracts() -> dict[str, RoleContract]:
    """Carga todos los contratos de roles desde los directorios canónicos."""
    contracts: dict[str, RoleContract] = {}
    for roles_dir in ROLES_DIRS:
        if not roles_dir.exists():
            continue
        for md_file in sorted(roles_dir.glob("*.md")):
            contract = parse_role_file(md_file)
            if contract:
                contracts[contract.role_id] = contract
    return contracts


# ── Validación de sesión ───────────────────────────────────────────────────────

@dataclass
class ValidationResult:
    role_id:   str
    passed:    bool
    issues:    list[str] = field(default_factory=list)
    warnings:  list[str] = field(default_factory=list)


def validate_session(session_path: Path) -> list[ValidationResult]:
    """Valida que una sesión JSON usó los roles según sus contratos.

    Comprueba:
      - Los roles declarados existen en el catálogo.
      - Los artefactos producidos incluyen las Salidas esperadas del rol.
      - No se usaron más de 2 roles (restricción de W7).
    """
    if not session_path.exists():
        return []
    try:
        session = json.loads(session_path.read_text("utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    contracts = load_all_contracts()
    results: list[ValidationResult] = []

    declared_roles: list[str] = session.get("roles", [])
    artifacts:      list[str] = session.get("artifacts", [])
    artifact_names  = {Path(a).name.lower() for a in artifacts}

    # Regla: máximo 2 roles (W7)
    if len(declared_roles) > 2:
        r = ValidationResult(
            role_id="session",
            passed=False,
            issues=[f"Demasiados roles ({len(declared_roles)}) — máximo 2 permitidos (W7)"],
        )
        results.append(r)

    for role_id in declared_roles:
        contract = contracts.get(role_id)
        if not contract:
            results.append(ValidationResult(
                role_id=role_id,
                passed=False,
                issues=[f"Rol '{role_id}' no encontrado en el catálogo de contratos"],
            ))
            continue

        issues:   list[str] = []
        warnings: list[str] = []

        # Verificar que al menos alguna salida esperada aparece en artefactos
        if contract.salidas and artifacts is not None:
            matched_salidas = [
                s for s in contract.salidas
                if any(kw.lower() in " ".join(artifact_names)
                       for kw in s.split()[:3] if len(kw) > 3)
            ]
            if not matched_salidas and artifacts:
                warnings.append(
                    f"Ninguna salida del rol ({', '.join(contract.salidas[:2])}) "
                    f"detectada en artefactos"
                )

        # Verificar no activación — heurístico: objetivo de sesión contiene señales de no-uso
        objective: str = session.get("objetivo", "").lower()
        for na in contract.no_activacion:
            keywords = [w for w in na.split() if len(w) > 4]
            if keywords and all(kw.lower() in objective for kw in keywords[:2]):
                warnings.append(
                    f"El objetivo de sesión puede contradecir la condición de no-activación: '{na}'"
                )

        results.append(ValidationResult(
            role_id  = role_id,
            passed   = len(issues) == 0,
            issues   = issues,
            warnings = warnings,
        ))

    return results


# ── Presentación ───────────────────────────────────────────────────────────────

def _print_contract(contract: RoleContract) -> None:
    print(f"\n  {_BOLD}{contract.role_id}{_RST}  ({contract.family} · v{contract.version})")
    print(f"  Propósito: {contract.purpose}")
    if contract.alcance:
        print(f"\n  Alcance:")
        for a in contract.alcance:
            print(f"    - {a}")
    if contract.entradas:
        print(f"\n  {_CYN}Entradas:{_RST}")
        for e in contract.entradas:
            print(f"    - {e}")
    if contract.salidas:
        print(f"\n  {_GRN}Salidas:{_RST}")
        for s in contract.salidas:
            print(f"    - {s}")
    if contract.limites:
        print(f"\n  {_YEL}Límites:{_RST}")
        for l in contract.limites:
            print(f"    - {l}")
    if contract.activacion:
        print(f"\n  Activación:")
        for a in contract.activacion:
            print(f"    - {a}")
    if contract.no_activacion:
        print(f"\n  No activación:")
        for na in contract.no_activacion:
            print(f"    - {na}")
    if contract.dependencias:
        print(f"\n  Dependencias:")
        for d in contract.dependencias:
            print(f"    - {d}")
    if contract.criterio_exito:
        print(f"\n  Criterio de éxito:")
        for c in contract.criterio_exito:
            print(f"    - {c}")
    print(f"\n  Fuente: {contract.source_file}")


def _print_validation_results(results: list[ValidationResult]) -> None:
    if not results:
        print(f"  {_YEL}Sin resultados de validación{_RST}")
        return
    for r in results:
        sym = _GRN + "✅" + _RST if r.passed else _RED + "❌" + _RST
        print(f"\n  {sym}  {_BOLD}{r.role_id}{_RST}")
        for issue in r.issues:
            print(f"     {_RED}[ERROR]{_RST} {issue}")
        for warn in r.warnings:
            print(f"     {_YEL}[WARN]{_RST}  {warn}")
        if r.passed and not r.warnings:
            print(f"     {_GRN}Contrato OK{_RST}")


# ── Self-tests ─────────────────────────────────────────────────────────────────

def _run_tests() -> int:
    results: list[tuple[str, bool, str]] = []

    # T01 — load_all_contracts devuelve al menos un contrato
    contracts = load_all_contracts()
    t01 = len(contracts) > 0
    results.append(("T01:contracts_loaded", t01, f"{len(contracts)} contratos"))

    # T02 — role_maestro_bago tiene entradas y salidas
    maestro = contracts.get("role_maestro_bago")
    t02 = maestro is not None and len(maestro.entradas) > 0 and len(maestro.salidas) > 0
    results.append(("T02:maestro_has_inputs_outputs", t02, ""))

    # T03 — todos los contratos tienen role_id
    missing_ids = [c for c in contracts.values() if not c.role_id]
    t03 = len(missing_ids) == 0
    results.append(("T03:all_contracts_have_id", t03,
                     f"{len(missing_ids)} sin id" if missing_ids else ""))

    # T04 — parse_role_file con fichero real devuelve contrato
    for roles_dir in ROLES_DIRS:
        if roles_dir.exists():
            md_files = list(roles_dir.glob("*.md"))
            if md_files:
                contract = parse_role_file(md_files[0])
                t04 = contract is not None and bool(contract.role_id)
                results.append(("T04:parse_real_file", t04, md_files[0].name))
                break

    # T05 — validate_session con sesión inexistente devuelve lista vacía
    fake_path = Path("/nonexistent/session.json")
    vr = validate_session(fake_path)
    t05 = vr == []
    results.append(("T05:validate_nonexistent_returns_empty", t05, ""))

    # T06 — validate_session con sesión con >2 roles detecta problema
    import tempfile, json as _json
    tmp_session = Path(tempfile.mktemp(suffix=".json"))
    try:
        fake_session = {
            "roles": ["role_a", "role_b", "role_c"],
            "artifacts": [],
            "objetivo": "test",
        }
        tmp_session.write_text(_json.dumps(fake_session), encoding="utf-8")
        vr2 = validate_session(tmp_session)
        t06 = any(not r.passed and "Demasiados roles" in " ".join(r.issues) for r in vr2)
        results.append(("T06:detects_too_many_roles", t06, ""))
    finally:
        tmp_session.unlink(missing_ok=True)

    # T07 — export to_dict funciona para todos los contratos
    try:
        for contract in contracts.values():
            d = contract.to_dict()
            assert "role_id" in d and "entradas" in d
        t07 = True
    except Exception as e:
        t07 = False
    results.append(("T07:to_dict_works_for_all", t07, ""))

    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    for name, ok, detail in results:
        sym = "✅" if ok else "❌"
        print(f"  {sym}  {name}" + (f": {detail}" if detail else ""))
    print(f"\n  {passed}/{len(results)} pasaron")

    output = {
        "tool": "role_contract_validator",
        "status": "ok" if failed == 0 else "fail",
        "checks": [{"name": n, "passed": ok} for n, ok, _ in results],
    }
    print(json.dumps(output))
    return 0 if failed == 0 else 1


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = sys.argv[1:]

    if not args or "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)

    if "--test" in args:
        sys.exit(_run_tests())

    if "--list" in args:
        contracts = load_all_contracts()
        print(f"\n  {_BOLD}Roles registrados ({len(contracts)}):{_RST}")
        for rid, c in sorted(contracts.items()):
            print(f"  {_CYN}{rid:<35}{_RST} {c.family:<12} {c.source_file}")
        print()
        sys.exit(0)

    if "--export" in args:
        contracts = load_all_contracts()
        export = {rid: c.to_dict() for rid, c in sorted(contracts.items())}
        print(json.dumps(export, indent=2, ensure_ascii=False))
        sys.exit(0)

    if "--show" in args:
        i = args.index("--show")
        role_id = args[i + 1] if i + 1 < len(args) else ""
        if not role_id:
            print("  Especifica un role_id con --show", file=sys.stderr)
            sys.exit(1)
        contracts = load_all_contracts()
        contract = contracts.get(role_id)
        if not contract:
            print(f"  {_RED}Rol '{role_id}' no encontrado.{_RST}", file=sys.stderr)
            print(f"  Roles disponibles: {', '.join(sorted(contracts.keys()))}")
            sys.exit(1)
        _print_contract(contract)
        print()
        sys.exit(0)

    if "--validate" in args:
        i = args.index("--validate")
        session_path_str = args[i + 1] if i + 1 < len(args) else ""
        if not session_path_str:
            print("  Especifica una ruta a JSON de sesión con --validate", file=sys.stderr)
            sys.exit(1)
        session_path = Path(session_path_str)
        vr = validate_session(session_path)
        _print_validation_results(vr)
        print()
        all_passed = all(r.passed for r in vr)
        sys.exit(0 if all_passed else 1)

    print(__doc__)
    sys.exit(1)
