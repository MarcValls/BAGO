#!/usr/bin/env python3
"""path_healer.py — Reparador automático de rutas rotas con memoria dinámica.

NO contiene ninguna ruta hardcodeada (ni rota ni resuelta).
Todo se descubre en tiempo de ejecución:

  1. DESCUBRIMIENTO DE RAÍCES
     Localiza tools/ buscando el marcador canónico (tool_registry.py)
     caminando desde __file__ hacia arriba. Cero supuestos de ubicación.

  2. DESCUBRIMIENTO DE PATH-VARS
     Lee cada archivo .py y detecta qué variables son asignaciones de ruta:
       TOOLS_DIR = Path(__file__).parent
       ROOT = Path(__file__).resolve().parent.parent
       _HERE = Path(__file__)
       ...
     Evalúa su valor REAL según la ubicación del archivo en disco.
     Sin nombres de variable hardcodeados.

  3. GENERACIÓN DINÁMICA DE PATRONES
     Con las path-vars descubiertas por archivo, genera los patrones de
     búsqueda (regex) en tiempo de ejecución. Si un archivo usa ROOT en
     vez de TOOLS_DIR, los patrones se construyen con ROOT.

  4. VALIDACIÓN
     Para cada expresión `VARNAME / "stem.py"` detectada, resuelve el path
     real evaluando VARNAME + "stem.py" y comprueba si existe.

  5. BÚSQUEDA RECURSIVA
     Si no existe → busca stem.py por todo el árbol del repo.
     Resultado guardado en memoria persistente (state/path_healer_memory.json).

  6. REESCRITURA
     Reemplaza la expresión original por la ruta correcta usando la misma
     variable que el archivo ya tenía. Sin introducir nombres nuevos.

  7. MEMORIA DINÁMICA
     state/path_healer_memory.json — persiste entre ejecuciones:
       - stem_index: stem → ruta actual conocida
       - healed:     historial de reparaciones por archivo
       - missing:    stems que no se encontraron en ningún lugar
     Se actualiza cada vez que un archivo se mueve o se repara.

Uso:
  python3 path_healer.py                → escanea y repara todo
  python3 path_healer.py --scan         → solo detecta (dry-run)
  python3 path_healer.py --file f.py   → repara un archivo concreto
  python3 path_healer.py --report       → JSON para CI/integración
  python3 path_healer.py --watch        → daemon de vigilancia continua
  python3 path_healer.py --forget       → limpia memoria y re-indexa todo
  python3 path_healer.py --test         → self-tests
"""
from __future__ import annotations

import sys as _sys
# Force UTF-8 output on Windows (default codec is cp1252)
if hasattr(_sys.stdout, "reconfigure"):
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(_sys.stderr, "reconfigure"):
    _sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import argparse
import ast
import json
import re
import shutil
import sys
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional


# ═══════════════════════════════════════════════════════════════════
# FASE 0: LOCALIZACIÓN DEL ANCLA (sin rutas hardcodeadas)
# ═══════════════════════════════════════════════════════════════════

def _find_anchor(start: Path, marker: str = "tool_registry.py", max_up: int = 8) -> Path:
    """Sube desde `start` hasta encontrar un directorio que contenga `marker`.

    El marcador es lo único que identifica la raíz de tools/. Sin él,
    este script no puede funcionar y falla con un mensaje claro.
    """
    candidate = start.resolve()
    for _ in range(max_up):
        if (candidate / marker).exists():
            return candidate
        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent
    raise RuntimeError(
        f"No se encontró '{marker}' subiendo desde {start}. "
        f"¿Está path_healer.py dentro del árbol de BAGO?"
    )


# El único path que se asume: este mismo archivo vive dentro de tools/.
_SELF_DIR   = Path(__file__).resolve().parent
TOOLS_DIR   = _find_anchor(_SELF_DIR)
BAGO_ROOT   = TOOLS_DIR.parent
REPO_ROOT   = BAGO_ROOT.parent
STATE_DIR   = BAGO_ROOT / "state"
MEMORY_FILE = STATE_DIR / "path_healer_memory.json"


# ═══════════════════════════════════════════════════════════════════
# COLORES (opcional, sin deps)
# ═══════════════════════════════════════════════════════════════════

_COLOR = sys.stdout.isatty() and sys.platform != "win32"
def _c(code: str, t: str) -> str:
    return f"\033[{code}m{t}\033[0m" if _COLOR else t

OK   = lambda t: _c("1;32", t)   # noqa: E731
WARN = lambda t: _c("1;33", t)   # noqa: E731
ERR  = lambda t: _c("1;31", t)   # noqa: E731
DIM  = lambda t: _c("2", t)      # noqa: E731
BOLD = lambda t: _c("1", t)      # noqa: E731
CYAN = lambda t: _c("1;36", t)   # noqa: E731


# ═══════════════════════════════════════════════════════════════════
# FASE 1: MEMORIA PERSISTENTE
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Memory:
    """Estado persistente del healer entre ejecuciones."""
    version:     int              = 1
    last_scan:   str              = ""
    # stem → ruta relativa desde REPO_ROOT (se actualiza cuando detectamos movimiento)
    stem_index:  dict[str, str]   = field(default_factory=dict)
    # archivo (relativo) → {stem: {line, old, new, ts}}
    healed:      dict[str, dict]  = field(default_factory=dict)
    # stems que no existen en ningún lugar del repo
    missing:     list[str]        = field(default_factory=list)

    def save(self) -> None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        MEMORY_FILE.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @classmethod
    def load(cls) -> "Memory":
        if not MEMORY_FILE.exists():
            return cls()
        try:
            data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
            return cls(**{k: data.get(k, v) for k, v in asdict(cls()).items()})
        except Exception:
            return cls()

    def record_heal(self, file_rel: str, stem: str, line: int, old: str, new: str) -> None:
        entry = self.healed.setdefault(file_rel, {})
        entry[stem] = {"line": line, "old": old, "new": new, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}

    def update_stem(self, stem: str, actual_path: Path) -> None:
        try:
            rel = str(actual_path.relative_to(REPO_ROOT))
        except ValueError:
            rel = str(actual_path)
        self.stem_index[stem] = rel

    def resolve_stem(self, stem: str) -> Optional[Path]:
        """Devuelve la ruta conocida para un stem, o None."""
        rel = self.stem_index.get(stem)
        if not rel:
            return None
        p = REPO_ROOT / rel
        if p.exists():
            return p
        # La memoria apunta a un lugar que ya no existe → borramos
        del self.stem_index[stem]
        return None


# ═══════════════════════════════════════════════════════════════════
# FASE 2: ÍNDICE DINÁMICO DE STEMS
# ═══════════════════════════════════════════════════════════════════

def build_stem_index(mem: Memory) -> dict[str, Path]:
    """Construye/actualiza el índice stem → Path buscando recursivamente.

    Busca en todo el árbol bajo BAGO_ROOT (no solo tools/).
    Actualiza la memoria con los stems encontrados.
    No asume ninguna ubicación concreta de ningún archivo.
    """
    index: dict[str, Path] = {}

    # Directorios donde buscar: todo el árbol de .bago/
    search_roots = [BAGO_ROOT]

    for root in search_roots:
        if not root.exists():
            continue
        for py_file in root.rglob("*.py"):
            if py_file.name.startswith(".") or ".healer.bak" in py_file.name:
                continue
            stem = py_file.stem
            # Preferir archivos en tools/ root sobre subdirectorios
            if stem not in index:
                index[stem] = py_file
            elif py_file.parent == TOOLS_DIR and index[stem].parent != TOOLS_DIR:
                index[stem] = py_file

    # Sincronizar con memoria
    for stem, path in index.items():
        mem.update_stem(stem, path)

    return index


# ═══════════════════════════════════════════════════════════════════
# FASE 3: DESCUBRIMIENTO DE PATH-VARS POR ARCHIVO
# ═══════════════════════════════════════════════════════════════════

# Patrón genérico para detectar cualquier asignación de variable a un Path.
# Captura: grupo 1 = nombre de la variable, grupo 2 = la expresión RHS
_PATH_VAR_DEF = re.compile(
    r"^([A-Z_][A-Z0-9_]*)\s*=\s*"          # VAR_NAME =
    r"(Path\s*\([^)]+\)|os\.path\.[^\n]+)"  # Path(...) o os.path.xxx(...)
    r"(?:[^\n]*)",                           # resto de la línea
    re.MULTILINE,
)

# Partes de la expresión __file__ con modificadores
_FILE_EXPR_PARTS = re.compile(
    r"Path\s*\(\s*__file__\s*\)"
    r"((?:\s*\.\s*(?:resolve|parent|stem|name)\s*\(\s*\)|\s*\.\s*parent)*)"
)


def _resolve_path_expr(expr_rhs: str, file_path: Path) -> Optional[Path]:
    """Evalúa una expresión de Path relativa a la ubicación real del archivo.

    Soporta:
      Path(__file__).parent
      Path(__file__).resolve().parent
      Path(__file__).resolve().parent.parent
      Path(__file__).parent.parent
      (cualquier combinación de .resolve() y .parent)

    No usa eval(). Analiza los modificadores manualmente.
    """
    m = _FILE_EXPR_PARTS.search(expr_rhs)
    if not m:
        return None

    modifiers = m.group(1)  # e.g. ".resolve().parent.parent"

    # Contar cuántos .parent hay
    parent_count = modifiers.count(".parent")
    has_resolve  = ".resolve()" in modifiers

    result = file_path.resolve() if has_resolve else file_path
    # Empezamos desde el directorio del archivo si la expresión base es Path(__file__),
    # que es un archivo, así que el primer .parent ya nos da el directorio.
    for _ in range(parent_count):
        result = result.parent

    return result if result.exists() else None


def discover_path_vars(source: str, file_path: Path) -> dict[str, Path]:
    """Descubre todas las variables de path definidas en un archivo.

    Devuelve {VARNAME: resolved_Path} para cada variable cuyo valor
    puede resolverse con éxito dada la ubicación del archivo.

    Ejemplo para un archivo en tools/:
      TOOLS_DIR = Path(__file__).parent        → tools/
      BAGO_ROOT = Path(__file__).parent.parent → .bago/
      ROOT      = Path(__file__).resolve().parent.parent.parent → repo/
    """
    path_vars: dict[str, Path] = {}
    for m in _PATH_VAR_DEF.finditer(source):
        var_name = m.group(1)
        rhs      = m.group(2) + m.group(0)[m.end(2) - m.start():]  # full RHS line
        resolved = _resolve_path_expr(m.group(0), file_path)
        if resolved is not None:
            path_vars[var_name] = resolved
    return path_vars


# ═══════════════════════════════════════════════════════════════════
# FASE 4: GENERACIÓN DINÁMICA DE PATRONES
# ═══════════════════════════════════════════════════════════════════

# Tipos de envoltorio para una referencia de path
_WRAPPERS = [
    # str(VAR / "stem.py")
    (r'str\s*\(\s*{var}\s*/\s*["\']({stem_pat})\.py["\'](?:\s*/\s*["\'][^"\']*["\'])*\s*\)',   "str_div"),
    # VAR / "stem.py"
    (r'({var}\s*/\s*["\']({stem_pat})\.py["\'](?:\s*/\s*["\'][^"\']*["\'])*)',                 "div"),
    # Path("/absolute/path/stem.py")
    (r'Path\s*\(\s*["\']([^"\']*[/\\\\]({stem_pat})\.py)["\'])',                              "abs_path"),
    # spec_from_file_location("x", str(VAR / "stem.py"))
    (r'spec_from_file_location\s*\([^,]+,\s*str\s*\(\s*{var}\s*/\s*["\']({stem_pat})\.py["\']', "spec"),
]


def build_patterns_for_file(path_vars: dict[str, Path]) -> list[tuple[re.Pattern, str, str]]:
    """Genera los patrones regex para un archivo basándose en sus path-vars.

    Devuelve lista de (compiled_pattern, wrapper_kind, var_name).
    Si el archivo no tiene path-vars reconocibles, devuelve solo
    el patrón de Path absoluta (que no necesita var name).
    """
    patterns: list[tuple[re.Pattern, str, str]] = []
    # Patrón de stem genérico: nombre de archivo Python válido
    stem_pat = r"[a-zA-Z0-9_\-]+"

    for var_name in path_vars:
        esc_var = re.escape(var_name)
        for wrapper_tmpl, kind in _WRAPPERS[:3]:  # str_div, div, spec
            if "{var}" not in wrapper_tmpl:
                continue
            pat_str = wrapper_tmpl.format(var=esc_var, stem_pat=stem_pat)
            try:
                patterns.append((re.compile(pat_str), kind, var_name))
            except re.error:
                pass

    # Siempre incluir el patrón de Path absoluta (sin var)
    abs_pat = _WRAPPERS[2][0].format(var="", stem_pat=stem_pat)
    try:
        patterns.append((re.compile(abs_pat), "abs_path", ""))
    except re.error:
        pass

    return patterns


# ═══════════════════════════════════════════════════════════════════
# TIPOS DE RESULTADO
# ═══════════════════════════════════════════════════════════════════

@dataclass
class PathRef:
    """Una referencia a un path encontrada en el código fuente."""
    file:       Path
    line_no:    int
    col:        int
    fragment:   str           # trozo de código original
    stem:       str           # nombre del módulo sin .py
    var_name:   str           # variable usada (o "" si abs_path)
    var_dir:    Optional[Path]  # directorio que resuelve esa variable
    kind:       str           # wrapper kind
    broken:     bool = False
    found_at:   Optional[Path] = None
    fixed:      bool = False


@dataclass
class ScanReport:
    files_scanned:  int = 0
    refs_found:     int = 0
    broken:         int = 0
    fixed:          int = 0
    missing:        int = 0
    refs:           list[PathRef] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════
# FASE 5: ESCANEO
# ═══════════════════════════════════════════════════════════════════

def scan_file(
    py_file: Path,
    stem_index: dict[str, Path],
    mem: Memory,
) -> list[PathRef]:
    """Escanea un archivo .py y detecta referencias a paths rotas.

    No asume ningún nombre de variable concreto.
    Descubre los path-vars del archivo y genera los patrones sobre la marcha.
    """
    try:
        source = py_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    # Descubrir path-vars de este archivo (completamente dinámico)
    path_vars = discover_path_vars(source, py_file)
    patterns  = build_patterns_for_file(path_vars)

    if not patterns:
        return []

    refs: list[PathRef] = []
    lines = source.splitlines()

    for line_no, line in enumerate(lines, start=1):
        for compiled_pat, kind, var_name in patterns:
            for m in compiled_pat.finditer(line):
                # El stem siempre es el último grupo de captura que parece un nombre de módulo
                groups = [g for g in m.groups() if g and re.match(r'^[a-zA-Z0-9_\-]+$', g)]
                if not groups:
                    continue
                stem = groups[-1]  # el stem es siempre el más específico

                # Calcular path que esta referencia resolvería ahora
                var_dir = path_vars.get(var_name)
                if var_dir and kind in ("str_div", "div", "spec"):
                    resolved_now = var_dir / f"{stem}.py"
                    is_broken = not resolved_now.exists()
                elif kind == "abs_path":
                    # Extraer el path literal del match
                    literal = m.group(1) if m.lastindex and m.lastindex >= 1 else ""
                    resolved_now = Path(literal)
                    is_broken = not resolved_now.exists()
                else:
                    continue

                if not is_broken:
                    continue

                # Buscar dónde está ahora el stem
                found = (
                    mem.resolve_stem(stem)
                    or stem_index.get(stem)
                )

                # Evitar duplicados en la misma línea/stem
                if any(r.line_no == line_no and r.stem == stem for r in refs):
                    continue

                refs.append(PathRef(
                    file=py_file,
                    line_no=line_no,
                    col=m.start(),
                    fragment=m.group(0),
                    stem=stem,
                    var_name=var_name,
                    var_dir=var_dir,
                    kind=kind,
                    broken=True,
                    found_at=found,
                ))

    return refs


def scan_all(mem: Memory, extra_roots: Optional[list[Path]] = None) -> ScanReport:
    """Escanea todos los .py bajo BAGO_ROOT y sus subdirectorios."""
    stem_index = build_stem_index(mem)

    search_roots: list[Path] = [BAGO_ROOT]
    if extra_roots:
        search_roots.extend(extra_roots)

    visited: set[Path] = set()
    all_refs: list[PathRef] = []

    for root in search_roots:
        if not root.exists():
            continue
        for py_file in root.rglob("*.py"):
            if py_file in visited:
                continue
            if ".healer.bak" in py_file.name or py_file.name.startswith("."):
                continue
            visited.add(py_file)
            file_refs = scan_file(py_file, stem_index, mem)
            all_refs.extend(file_refs)

    broken  = [r for r in all_refs if r.broken]
    missing = [r for r in broken if r.found_at is None]

    return ScanReport(
        files_scanned=len(visited),
        refs_found=len(all_refs),
        broken=len(broken),
        missing=len(missing),
        refs=all_refs,
    )


# ═══════════════════════════════════════════════════════════════════
# FASE 6: REESCRITURA
# ═══════════════════════════════════════════════════════════════════

def _build_replacement(ref: PathRef) -> str:
    """Construye la expresión de reemplazo usando la misma variable que ya usa el archivo.

    Nunca introduce nombres de variable nuevos ni rutas hardcodeadas.
    Usa ref.var_name (el nombre que ya tiene el archivo, e.g. TOOLS_DIR, ROOT, _HERE)
    y calcula la ruta relativa desde ref.var_dir hasta ref.found_at.
    """
    assert ref.found_at is not None
    found = ref.found_at.resolve()

    if ref.kind == "abs_path":
        # Para Path absoluta, usamos la var más cercana si existe
        if ref.var_name and ref.var_dir:
            try:
                rel_parts = found.relative_to(ref.var_dir).parts
            except ValueError:
                return f'Path(r"{found}")'
            chain = " / ".join(f'"{p}"' for p in rel_parts)
            return f'Path(str({ref.var_name} / {chain}))'
        return f'Path(r"{found}")'

    if not ref.var_name or ref.var_dir is None:
        return ref.fragment  # no podemos mejorar esto sin var

    # Calcular ruta relativa desde var_dir hasta found_at
    try:
        rel = found.relative_to(ref.var_dir)
        rel_parts = rel.parts
    except ValueError:
        # El archivo encontrado está fuera del directorio de la variable.
        # Intentar con BAGO_ROOT como referencia
        try:
            rel = found.relative_to(BAGO_ROOT)
            # Necesitamos subir desde var_dir hasta BAGO_ROOT
            ups = len(ref.var_dir.relative_to(BAGO_ROOT).parts)
            prefix = "/".join([".."] * ups)
            return f'Path(r"{found}")'  # fallback seguro
        except ValueError:
            return f'Path(r"{found}")'

    # Construir expresión con la misma variable
    chain = " / ".join(f'"{p}"' for p in rel_parts)
    path_expr = f"{ref.var_name} / {chain}"

    if ref.kind == "str_div":
        return f"str({path_expr})"
    elif ref.kind == "spec":
        name_match = re.search(r'spec_from_file_location\s*\(([^,]+),', ref.fragment)
        name_part  = name_match.group(1).strip() if name_match else '"_module"'
        return f"spec_from_file_location({name_part}, str({path_expr}))"
    else:
        return path_expr


def fix_file(
    refs: list[PathRef],
    dry_run: bool,
    backup: bool,
    mem: Memory,
) -> int:
    """Aplica las correcciones a un archivo. Devuelve el número de fixes aplicados."""
    if not refs:
        return 0

    py_file = refs[0].file
    fixable = [r for r in refs if r.found_at is not None and r.broken]
    if not fixable:
        return 0

    try:
        original = py_file.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        print(f"  {ERR('✗')} No se puede leer {py_file}: {e}")
        return 0

    text = original
    applied = 0

    # Procesar en orden inverso de aparición para no desplazar posiciones
    for ref in sorted(fixable, key=lambda r: r.line_no, reverse=True):
        replacement = _build_replacement(ref)
        if replacement == ref.fragment:
            continue

        new_text = text.replace(ref.fragment, replacement, 1)
        if new_text == text:
            print(f"  {WARN('⚠')} No reemplazado: {py_file.name}:{ref.line_no} {ref.fragment!r:.60}")
            continue

        rel_file = str(py_file.relative_to(REPO_ROOT)) if py_file.is_relative_to(REPO_ROOT) else str(py_file)
        rel_found = str(ref.found_at.relative_to(REPO_ROOT)) if ref.found_at and ref.found_at.is_relative_to(REPO_ROOT) else str(ref.found_at)

        print(f"  {CYAN('→')} {py_file.name}:{ref.line_no}")
        print(f"       {DIM('old:')} {ref.fragment[:80]}")
        print(f"       {OK('new:')} {replacement[:80]}")

        if not dry_run:
            text = new_text
            ref.fixed = True
            applied += 1
            mem.record_heal(rel_file, ref.stem, ref.line_no, ref.fragment, replacement)

    if not dry_run and applied > 0:
        if backup:
            bak = py_file.with_suffix(py_file.suffix + ".healer.bak")
            shutil.copy2(str(py_file), str(bak))
        try:
            py_file.write_text(text, encoding="utf-8")
        except OSError as e:
            print(f"  {ERR('✗')} No se puede escribir {py_file}: {e}")
            if backup:
                shutil.copy2(str(bak), str(py_file))
            return 0

    return applied


def fix_all(
    report: ScanReport,
    dry_run: bool,
    backup: bool,
    max_fixes: int,
    mem: Memory,
) -> int:
    """Aplica todos los fixes posibles respetando el límite max_fixes."""
    by_file: dict[Path, list[PathRef]] = {}
    for ref in report.refs:
        if ref.broken and ref.found_at is not None:
            by_file.setdefault(ref.file, []).append(ref)

    total = 0
    for py_file, file_refs in sorted(by_file.items()):
        if total >= max_fixes:
            break
        batch = file_refs[:max_fixes - total]
        total += fix_file(batch, dry_run=dry_run, backup=backup, mem=mem)

    report.fixed = total
    return total


# ═══════════════════════════════════════════════════════════════════
# PRESENTACIÓN DE RESULTADOS
# ═══════════════════════════════════════════════════════════════════

def print_report(report: ScanReport, json_out: bool = False) -> None:
    if json_out:
        data = {
            "files_scanned": report.files_scanned,
            "broken":        report.broken,
            "fixed":         report.fixed,
            "missing":       report.missing,
            "refs": [
                {
                    "file":     str(r.file),
                    "line":     r.line_no,
                    "stem":     r.stem,
                    "var":      r.var_name,
                    "fragment": r.fragment,
                    "found_at": str(r.found_at) if r.found_at else None,
                    "fixed":    r.fixed,
                    "broken":   r.broken,
                }
                for r in report.refs if r.broken
            ],
        }
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    print(f"\n  BAGO Path Healer")
    print(f"  {'─' * 52}")
    print(f"  Archivos escaneados : {report.files_scanned}")
    print(f"  Referencias rotas   : {WARN(str(report.broken)) if report.broken else OK('0')}")
    print(f"  Reparadas           : {OK(str(report.fixed))}")
    print(f"  No encontradas      : {ERR(str(report.missing)) if report.missing else '0'}")

    broken_refs = [r for r in report.refs if r.broken]
    if not broken_refs:
        print(f"\n  {OK('✅ Sin rutas rotas detectadas')}\n")
        return

    pending = [r for r in broken_refs if not r.fixed and r.found_at]
    missing = [r for r in broken_refs if not r.found_at]
    fixed   = [r for r in broken_refs if r.fixed]

    def _rel(p: Path) -> str:
        try:
            return str(p.relative_to(REPO_ROOT))
        except ValueError:
            return str(p)

    if pending:
        print(f"\n  {WARN('⚠')} Pendientes ({len(pending)}):")
        for r in pending:
            print(f"     {_rel(r.file)}:{r.line_no}  {DIM(r.stem)}  →  {_rel(r.found_at)}")

    if missing:
        print(f"\n  {ERR('✗')} No encontrados ({len(missing)}):")
        for r in missing:
            print(f"     {_rel(r.file)}:{r.line_no}  {ERR(r.stem + '.py')}")

    if fixed:
        print(f"\n  {OK('✅')} Reparadas ({len(fixed)}):")
        for r in fixed:
            print(f"     {_rel(r.file)}:{r.line_no}  {r.stem}")

    print()


# ═══════════════════════════════════════════════════════════════════
# MODO DAEMON (WATCH)
# ═══════════════════════════════════════════════════════════════════

def watch_mode(interval: int, max_fixes: int, backup: bool) -> None:
    print(f"\n  👁  Path Healer — daemon (intervalo: {interval}s)")
    print(f"  Raíz vigilada: {BAGO_ROOT}\n")
    mem = Memory.load()
    try:
        while True:
            ts = time.strftime("%H:%M:%S")
            report = scan_all(mem)
            broken_fixable = [r for r in report.refs if r.broken and r.found_at]
            if broken_fixable:
                print(f"  [{ts}] {WARN(f'{len(broken_fixable)} rutas rotas')} — reparando…")
                fix_all(report, dry_run=False, backup=backup, max_fixes=max_fixes, mem=mem)
                mem.last_scan = time.strftime("%Y-%m-%dT%H:%M:%S")
                mem.save()
                print(f"  [{ts}] {OK(f'{report.fixed} reparadas')}")
            else:
                print(f"  [{ts}] {OK('✓')} Sin rutas rotas  ({report.files_scanned} archivos)")
            time.sleep(interval)
    except KeyboardInterrupt:
        print(f"\n  Daemon detenido.")


# ═══════════════════════════════════════════════════════════════════
# SELF-TESTS (sin rutas hardcodeadas)
# ═══════════════════════════════════════════════════════════════════

def _self_test() -> int:
    results: list[tuple[str, bool, str]] = []

    # Test 1: Ancla encontrada — TOOLS_DIR contiene tool_registry.py
    t1 = (TOOLS_DIR / "tool_registry.py").exists()
    results.append(("anchor_found", t1, str(TOOLS_DIR)))

    # Test 2: Memoria cargable sin errores
    mem = Memory.load()
    t2 = isinstance(mem, Memory)
    results.append(("memory_loads", t2, f"stems={len(mem.stem_index)}"))

    # Test 3: build_stem_index > 30 entries
    idx = build_stem_index(mem)
    t3 = len(idx) > 30
    results.append(("stem_index_size", t3, f"{len(idx)} entries"))

    # Test 4: discover_path_vars detecta TOOLS_DIR en este mismo archivo
    source_self = Path(__file__).read_text(encoding="utf-8")
    # Este archivo NO define TOOLS_DIR explícitamente (lo calcula dinámicamente)
    # Probamos con un snippet sintético
    fake_source = f"TOOLS_DIR = Path(__file__).parent\nBAGO_ROOT = Path(__file__).parent.parent\n"
    fake_file   = TOOLS_DIR / "fake_test_xyz.py"
    pvars = discover_path_vars(fake_source, fake_file)
    t4 = "TOOLS_DIR" in pvars and pvars["TOOLS_DIR"] == TOOLS_DIR
    results.append(("discover_path_vars_tools_dir", t4, str(pvars.get("TOOLS_DIR"))))

    # Test 5: discover_path_vars detecta 2 niveles de .parent
    pvars2 = discover_path_vars(fake_source, fake_file)
    t5 = "BAGO_ROOT" in pvars2 and pvars2["BAGO_ROOT"] == BAGO_ROOT
    results.append(("discover_path_vars_bago_root", t5, str(pvars2.get("BAGO_ROOT"))))

    # Test 6: build_patterns_for_file genera patrones si hay vars
    pats = build_patterns_for_file({"TOOLS_DIR": TOOLS_DIR})
    t6 = len(pats) >= 2
    results.append(("patterns_generated", t6, f"{len(pats)} patterns"))

    # Test 7: Los patrones detectan una referencia sintética
    test_line = 'str(TOOLS_DIR / "secret_scan.py")'
    detected = []
    for pat, kind, vname in pats:
        for m in pat.finditer(test_line):
            groups = [g for g in m.groups() if g and re.match(r'^[a-zA-Z0-9_\-]+$', g)]
            if groups:
                detected.append(groups[-1])
    t7 = "secret_scan" in detected
    results.append(("pattern_detects_stem", t7, f"detected={detected}"))

    # Test 8: Memory.save + Memory.load roundtrip
    mem2 = Memory(stem_index={"test_stem": ".bago/tools/test_stem.py"})
    test_mem_file = STATE_DIR / "_test_healer_memory.json"
    old_mem_file  = MEMORY_FILE
    # Monkeypatch MEMORY_FILE para el test
    import path_healer as _self_mod
    _self_mod.MEMORY_FILE = test_mem_file
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    mem2.save()
    mem3 = Memory.load()
    _self_mod.MEMORY_FILE = old_mem_file
    test_mem_file.unlink(missing_ok=True)
    t8 = mem3.stem_index.get("test_stem") == ".bago/tools/test_stem.py"
    results.append(("memory_roundtrip", t8, ""))

    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n  BAGO Path Healer — Self-tests ({passed}/{len(results)} pasaron)\n")
    for name, ok, detail in results:
        print(f"  {'✅' if ok else '❌'}  {name}  {detail}")
    return 0 if passed == len(results) else 1


# ═══════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════

def main(argv: Optional[list[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    ap = argparse.ArgumentParser(
        description="BAGO Path Healer — detecta y repara rutas rotas (memoria dinámica)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--scan",      action="store_true", help="Solo detecta, no modifica")
    ap.add_argument("--file",      metavar="PATH",      help="Repara solo este archivo")
    ap.add_argument("--report",    action="store_true", help="Salida JSON para CI")
    ap.add_argument("--watch",     action="store_true", help="Daemon de vigilancia continua")
    ap.add_argument("--interval",  type=int, default=15, help="Segundos entre ciclos (--watch)")
    ap.add_argument("--max-fixes", type=int, default=100, help="Límite de fixes por ejecución")
    ap.add_argument("--no-backup", action="store_true",  help="No crear .healer.bak")
    ap.add_argument("--forget",    action="store_true",  help="Borra memoria y re-indexa")
    ap.add_argument("--test",      action="store_true",  help="Ejecuta self-tests")
    args = ap.parse_args(argv)

    if args.test:
        return _self_test()

    mem = Memory.load()

    if args.forget:
        mem = Memory()
        mem.save()
        print(f"  {OK('✓')} Memoria borrada — se re-indexará en el próximo escaneo")

    if args.watch:
        watch_mode(interval=args.interval, max_fixes=args.max_fixes, backup=not args.no_backup)
        return 0

    backup = not args.no_backup

    # Modo archivo único
    if args.file:
        target = Path(args.file)
        if not target.is_absolute():
            target = REPO_ROOT / args.file
        if not target.exists():
            print(f"  {ERR('✗')} No encontrado: {target}")
            return 1
        idx = build_stem_index(mem)
        refs = scan_file(target, idx, mem)
        report = ScanReport(files_scanned=1, refs_found=len(refs),
                            broken=sum(1 for r in refs if r.broken),
                            missing=sum(1 for r in refs if r.broken and not r.found_at))
        report.refs = refs
        if not args.scan:
            fix_file([r for r in refs if r.broken], dry_run=False, backup=backup, mem=mem)
            mem.last_scan = time.strftime("%Y-%m-%dT%H:%M:%S")
            mem.save()
        print_report(report, json_out=args.report)
        return 0

    # Escaneo completo
    if not args.report:
        print(f"\n  Escaneando {BAGO_ROOT}…")

    report = scan_all(mem)

    if not args.scan:
        fix_all(report, dry_run=False, backup=backup, max_fixes=args.max_fixes, mem=mem)
        mem.last_scan = time.strftime("%Y-%m-%dT%H:%M:%S")
        mem.save()

    print_report(report, json_out=args.report)
    return 0 if report.missing == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
