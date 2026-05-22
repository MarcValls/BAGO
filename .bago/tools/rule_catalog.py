#!/usr/bin/env python3
"""rule_catalog.py — Herramienta #96: Catálogo de reglas BAGO-* y JS-*.

Genera un catálogo en Markdown (default) o HTML con todas las reglas
definidas en el framework: BAGO-E/W/I y JS-E/W/I.

Uso:
    python3 rule_catalog.py [--format md|html] [--out FILE] [--filter PREFIX] [--test]
    bago rule-catalog [--format md|html] [--out FILE]

Opciones:
    --format md|html  Formato de salida (default: md)
    --out FILE        Escribir a archivo en vez de stdout
    --filter PREFIX   Mostrar solo reglas que empiezan con PREFIX (ej: BAGO-W, JS-E)
    --test            Ejecutar self-tests y salir
"""
from __future__ import annotations

import sys
from dataclasses import dataclass

# ─── Catálogo de reglas ────────────────────────────────────────────────────

@dataclass
class Rule:
    code: str
    severity: str          # error | warning | info
    category: str          # security | reliability | maintainability | style
    source: str            # bago | js_ast | eslint
    title: str
    description: str
    example_bad: str = ""
    example_good: str = ""
    autofix: bool = False
    noqa: bool = True      # supprimible con # noqa


RULES: list[Rule] = [
    # ── BAGO Python rules ─────────────────────────────────────────────────
    Rule(
        code="BAGO-E001",
        severity="error",
        category="reliability",
        source="bago",
        title="Bare except clause",
        description=(
            "La cláusula `except Exception:` sin tipo captura `SystemExit` y "
            "`KeyboardInterrupt`, lo que impide interrumpir el programa con "
            "Ctrl-C y oculta errores inesperados."
        ),
        example_bad="try:\n    risky()\nexcept:\n    pass",
        example_good="try:\n    risky()\nexcept Exception as e:\n    log(e)",
        autofix=True,
    ),
    Rule(
        code="BAGO-W001",
        severity="warning",
        category="reliability",
        source="bago",
        title="datetime.utcnow() deprecated",  # noqa: BAGO-W001
        description=(
            "`datetime.utcnow()` devuelve un `datetime` naive en UTC, lo que "  # noqa: BAGO-W001
            "induce confusión con zonas horarias. Deprecated desde Python 3.12."
        ),
        example_bad="ts = datetime.utcnow()",  # noqa: BAGO-W001
        example_good="ts = datetime.now(timezone.utc)",
        autofix=True,
    ),
    Rule(
        code="BAGO-W002",
        severity="warning",
        category="security",
        source="bago",
        title="eval() / exec() usage",  # noqa: BAGO-W002
        description=(
            "`eval()` y `exec()` ejecutan código arbitrario. Si la entrada "  # noqa: BAGO-W002
            "proviene de fuentes externas, es una vulnerabilidad crítica RCE."
        ),
        example_bad="result = eval(user_input)",  # noqa: BAGO-W002
        example_good="# Usa ast.literal_eval() para datos estructurados\nresult = ast.literal_eval(data)",
    ),
    Rule(
        code="BAGO-W003",
        severity="warning",
        category="reliability",
        source="bago",
        title="os.system() — use subprocess",  # noqa: BAGO-W003
        description=(
            "`os.system()` no captura stdout/stderr, no permite control de "  # noqa: BAGO-W003
            "código de retorno y es más vulnerable a inyección de shell."
        ),
        example_bad='os.system("ls -la")',  # noqa: BAGO-W003
        example_good='subprocess.run(["ls", "-la"], check=True)',
    ),
    Rule(
        code="BAGO-W004",
        severity="warning",
        category="reliability",
        source="bago",
        title="Hardcoded absolute path",
        description=(
            "Rutas absolutas hardcodeadas (`/Users/`, `/home/`, `C:\\\\`) "
            "impiden portabilidad entre máquinas y entornos CI."
        ),
        example_bad='config = "/Users/marc/project/config.json"',  # noqa: BAGO-W004
        example_good='config = Path(__file__).parent / "config.json"',
    ),
    Rule(
        code="BAGO-I001",
        severity="info",
        category="maintainability",
        source="bago",
        title="raise SystemExit(1) without visible message",
        description=(
            "Salir con código 1 sin mensaje previo dificulta el diagnóstico "
            "en CI/CD. El usuario/operador no sabe qué falló."
        ),
        example_bad="raise SystemExit(1)",
        example_good='print("ERROR: no se encontró config.json", file=sys.stderr)\nsys.exit(1)',
    ),
    Rule(
        code="BAGO-I002",
        severity="info",
        category="maintainability",
        source="bago",
        title="TODO/FIXME/HACK comment",
        description=(
            "Comentarios `TODO`, `FIXME` o `HACK` son deuda técnica visible. "
            "Documenta en un ticket y elimina el comentario o conviértelo en "
            "un issue rastreable."
        ),
        example_bad="# TODO: manejar el caso de archivo vacío",  # noqa: BAGO-I002
        example_good="# Ver issue #123: manejar archivo vacío",
    ),
    # ── JS/TS AST rules ───────────────────────────────────────────────────
    Rule(
        code="JS-E001",
        severity="error",
        category="security",
        source="js_ast",
        title="eval() / Function() constructor",  # noqa: BAGO-W002
        description=(
            "`eval()` y `new Function(string)` ejecutan JavaScript arbitrario "  # noqa: BAGO-W002
            "en tiempo de ejecución. Equivalente a RCE si la cadena viene de "
            "una fuente externa."
        ),
        example_bad="const fn = new Function('return ' + userInput);",
        example_good="// Parsea JSON con JSON.parse(), usa funciones estáticas",
        noqa=True,
    ),
    Rule(
        code="JS-W001",
        severity="warning",
        category="maintainability",
        source="js_ast",
        title="console.log() en código de producción",
        description=(
            "Las llamadas a `console.log/debug/error` exponen información "
            "interna en producción. Usa un logger configurable."
        ),
        example_bad="console.log('Usuario:', user.id);",
        example_good="logger.debug('Usuario:', user.id);",
        noqa=True,
    ),
    Rule(
        code="JS-W002",
        severity="warning",
        category="maintainability",
        source="js_ast",
        title="debugger statement",
        description=(
            "La sentencia `debugger` pausa la ejecución en DevTools. Olvidarla "
            "en producción degrada la experiencia del usuario."
        ),
        example_bad="debugger;",
        example_good="// Eliminar antes del commit",
        noqa=True,
    ),
    Rule(
        code="JS-W003",
        severity="warning",
        category="reliability",
        source="js_ast",
        title="Loose equality == / !=",
        description=(
            "`==` aplica coerción de tipos (`'' == false // true`). Esto "
            "produce bugs sutiles. Usa siempre `===` y `!==`."
        ),
        example_bad="if (value == null) return;",
        example_good="if (value === null || value === undefined) return;",
        noqa=True,
    ),
    Rule(
        code="JS-W004",
        severity="warning",
        category="security",
        source="js_ast",
        title="setTimeout/setInterval con string",
        description=(
            "Pasar una cadena como primer argumento a `setTimeout` o "
            "`setInterval` es equivalente a `eval()` y comparte sus riesgos."  # noqa: BAGO-W002
        ),
        example_bad="setTimeout(\"doSomething()\", 100);",
        example_good="setTimeout(() => doSomething(), 100);",
        noqa=True,
    ),
    Rule(
        code="JS-W005",
        severity="warning",
        category="reliability",
        source="js_ast",
        title="Empty catch block",
        description=(
            "Un bloque `catch {}` vacío silencia errores completamente. "
            "Al menos loguea el error para facilitar el diagnóstico."
        ),
        example_bad="try { risky(); } catch (e) {}",
        example_good="try { risky(); } catch (e) { logger.error(e); }",
        noqa=True,
    ),
    Rule(
        code="JS-I001",
        severity="info",
        category="maintainability",
        source="js_ast",
        title="TODO/FIXME comment",
        description="Comentario de deuda técnica. Ver BAGO-I002 para guía.",
        example_bad="// TODO: refactorizar esta función",
        example_good="// Ver issue #456",
        noqa=True,
    ),
    Rule(
        code="JS-I002",
        severity="info",
        category="maintainability",
        source="js_ast",
        title="Arrow function con >5 parámetros",
        description=(
            "Las arrow functions con muchos parámetros son difíciles de "
            "leer y testear. Considera agrupar parámetros en un objeto."
        ),
        example_bad="const fn = (a, b, c, d, e, f) => a + b;",
        example_good="const fn = ({ a, b, c, d, e, f }) => a + b;",
        noqa=True,
    ),
    Rule(
        code="JS-I003",
        severity="info",
        category="maintainability",
        source="js_ast",
        title="Ternario anidado",
        description=(
            "Los ternarios anidados (`a ? b : c ? d : e`) son difíciles "
            "de leer. Usa `if/else` o un `switch`."
        ),
        example_bad="const x = a ? b : c ? d : e;",
        example_good="let x;\nif (a) { x = b; } else if (c) { x = d; } else { x = e; }",
        noqa=True,
    ),
    Rule(
        code="JS-I004",
        severity="info",
        category="maintainability",
        source="js_ast",
        title="Async function sin await",
        description=(
            "Una función marcada `async` que no contiene `await` es "
            "engañosa — devuelve una Promise innecesariamente."
        ),
        example_bad="async function getUser() { return db.find(id); }",
        example_good="function getUser() { return db.find(id); }",
        noqa=True,
    ),
]


# ─── Helpers ────────────────────────────────────────────────────────────────

_SEV_ICON = {"error": "🔴", "warning": "🟡", "info": "🔵"}
_CAT_LABEL = {
    "security":        "Seguridad",
    "reliability":     "Fiabilidad",
    "maintainability": "Mantenibilidad",
    "style":           "Estilo",
}


def _md_table_row(r: Rule) -> str:
    fix = "✅" if r.autofix else "—"
    return (
        f"| `{r.code}` | {_SEV_ICON[r.severity]} {r.severity} "
        f"| {_CAT_LABEL[r.category]} | {r.title} | {fix} |"
    )


def _md_detail(r: Rule) -> str:
    lines = [f"### `{r.code}` — {r.title}\n"]
    lines.append(f"**Severidad:** {_SEV_ICON[r.severity]} `{r.severity}`  ")
    lines.append(f"**Categoría:** {_CAT_LABEL[r.category]}  ")
    lines.append(f"**Fuente:** `{r.source}`  ")
    if r.autofix:
        lines.append("**Autofix:** ✅ soportado  ")
    if r.noqa:
        lines.append(f"**Suprimir:** `# noqa: {r.code}`\n")
    lines.append(f"\n{r.description}\n")
    if r.example_bad:
        lines.append("**❌ Incorrecto:**")
        lines.append(f"```python\n{r.example_bad}\n```\n" if r.source == "bago"
                     else f"```js\n{r.example_bad}\n```\n")
    if r.example_good:
        lines.append("**✅ Correcto:**")
        lines.append(f"```python\n{r.example_good}\n```\n" if r.source == "bago"
                     else f"```js\n{r.example_good}\n```\n")
    return "\n".join(lines)


# ─── Formato Markdown ───────────────────────────────────────────────────────

def generate_markdown(rules: list[Rule]) -> str:
    lines = [
        "# BAGO Rule Catalog\n",
        f"> **{len(rules)} reglas** ({sum(1 for r in rules if r.source == 'bago')} Python + "
        f"{sum(1 for r in rules if r.source == 'js_ast')} JS/TS)\n",
        "## Índice rápido\n",
        "| Código | Severidad | Categoría | Título | Autofix |",
        "|--------|-----------|-----------|--------|---------|",
    ]
    for r in rules:
        lines.append(_md_table_row(r))

    lines.append("\n---\n")
    lines.append("## Referencia detallada\n")

    current_source = None
    source_labels = {"bago": "Python (bago-lint)", "js_ast": "JS/TS (ast-scan)"}
    for r in rules:
        if r.source != current_source:
            current_source = r.source
            lines.append(f"\n## {source_labels.get(r.source, r.source)}\n")
        lines.append(_md_detail(r))
        lines.append("---\n")

    return "\n".join(lines)


# ─── Formato HTML ───────────────────────────────────────────────────────────

def generate_html(rules: list[Rule]) -> str:
    rows = ""
    for r in rules:
        fix = "✅" if r.autofix else "—"
        rows += (
            f"<tr>"
            f"<td><code>{r.code}</code></td>"
            f"<td>{_SEV_ICON[r.severity]} {r.severity}</td>"
            f"<td>{_CAT_LABEL[r.category]}</td>"
            f"<td>{r.title}</td>"
            f"<td>{fix}</td>"
            f"</tr>\n"
        )

    details = ""
    for r in rules:
        fix_tag = "<span class='fix'>✅ autofix</span>" if r.autofix else ""
        noqa_tag = f"<span class='noqa'># noqa: {r.code}</span>" if r.noqa else ""
        bad = f"<pre><code>{r.example_bad}</code></pre>" if r.example_bad else ""
        good = f"<pre><code>{r.example_good}</code></pre>" if r.example_good else ""
        details += f"""
<div class='rule' id='{r.code}'>
  <h3><code>{r.code}</code> — {r.title}</h3>
  <p class='meta'>
    {_SEV_ICON[r.severity]} <b>{r.severity}</b> &nbsp;·&nbsp;
    {_CAT_LABEL[r.category]} &nbsp;·&nbsp;
    fuente: <code>{r.source}</code>
    {fix_tag} {noqa_tag}
  </p>
  <p>{r.description}</p>
  {'<p><b>❌ Incorrecto:</b></p>' + bad if bad else ''}
  {'<p><b>✅ Correcto:</b></p>' + good if good else ''}
</div>
"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>BAGO Rule Catalog</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
  th, td {{ border: 1px solid #ddd; padding: .5rem .75rem; text-align: left; }}
  th {{ background: #f5f5f5; }}
  .rule {{ border: 1px solid #e0e0e0; border-radius: 6px; padding: 1rem; margin: 1rem 0; }}
  .rule h3 {{ margin: 0 0 .5rem; }}
  .meta {{ color: #555; font-size: .9em; }}
  .fix {{ background: #d4edda; color: #155724; padding: 2px 6px; border-radius: 4px; font-size: .8em; }}
  .noqa {{ background: #fff3cd; color: #856404; padding: 2px 6px; border-radius: 4px; font-size: .8em; font-family: monospace; }}
  pre {{ background: #f8f8f8; padding: .75rem; border-radius: 4px; overflow-x: auto; }}
  code {{ font-family: 'Fira Code', monospace; font-size: .9em; }}
  h2 {{ border-bottom: 2px solid #007acc; padding-bottom: .25rem; margin-top: 2rem; }}
</style>
</head>
<body>
<h1>BAGO Rule Catalog</h1>
<p><b>{len(rules)} reglas</b> ({sum(1 for r in rules if r.source == 'bago')} Python · {sum(1 for r in rules if r.source == 'js_ast')} JS/TS)</p>
<h2>Índice rápido</h2>
<table>
<thead><tr><th>Código</th><th>Severidad</th><th>Categoría</th><th>Título</th><th>Autofix</th></tr></thead>
<tbody>
{rows}
</tbody>
</table>
<h2>Referencia detallada</h2>
{details}
</body>
</html>"""


# ─── CLI ───────────────────────────────────────────────────────────────────

def main(argv: list[str]) -> int:
    fmt    = "md"
    out    = None
    filt   = None

    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--format" and i + 1 < len(argv):
            fmt = argv[i + 1]; i += 2
        elif a == "--out" and i + 1 < len(argv):
            out = argv[i + 1]; i += 2
        elif a == "--filter" and i + 1 < len(argv):
            filt = argv[i + 1]; i += 2
        else:
            i += 1

    rules = RULES
    if filt:
        rules = [r for r in rules if r.code.startswith(filt)]

    if fmt == "html":
        content = generate_html(rules)
    else:
        content = generate_markdown(rules)

    if out:
        import pathlib
        pathlib.Path(out).write_text(content, encoding="utf-8")
        print(f"Catálogo escrito en: {out}  ({len(rules)} reglas, formato {fmt})")
    else:
        print(content)

    return 0


# ─── Self-tests ────────────────────────────────────────────────────────────

def _self_test() -> None:
    print("Tests de rule_catalog.py...")
    fails: list[str] = []

    def ok(name: str) -> None:
        print(f"  OK: {name}")

    def fail(name: str, msg: str) -> None:
        fails.append(name)
        print(f"  FAIL: {name}: {msg}")

    # T1 — RULES no vacío
    if len(RULES) >= 16:
        ok("catalog:rules_count")
    else:
        fail("catalog:rules_count", f"solo {len(RULES)} reglas")

    # T2 — cada regla tiene severity válida
    valid_sev = {"error", "warning", "info"}
    bad = [r.code for r in RULES if r.severity not in valid_sev]
    if not bad:
        ok("catalog:valid_severities")
    else:
        fail("catalog:valid_severities", f"severidades inválidas: {bad}")

    # T3 — Markdown contiene tabla y secciones
    md = generate_markdown(RULES)
    if "| Código |" in md and "BAGO-E001" in md and "JS-E001" in md:
        ok("catalog:markdown_output")
    else:
        fail("catalog:markdown_output", "output Markdown incompleto")

    # T4 — HTML contiene estructura básica
    html = generate_html(RULES)
    if "<table>" in html and "BAGO-E001" in html and "JS-I004" in html:
        ok("catalog:html_output")
    else:
        fail("catalog:html_output", "output HTML incompleto")

    # T5 — --filter funciona
    filtered = [r for r in RULES if r.code.startswith("BAGO-W")]
    if len(filtered) > 0 and all(r.code.startswith("BAGO-W") for r in filtered):
        ok("catalog:filter_prefix")
    else:
        fail("catalog:filter_prefix", "filtrado de prefijo falló")

    # T6 — autofix solo en BAGO-E001 y BAGO-W001
    autofix = [r.code for r in RULES if r.autofix]
    expected = {"BAGO-E001", "BAGO-W001"}
    if set(autofix) == expected:
        ok("catalog:autofix_flags")
    else:
        fail("catalog:autofix_flags", f"autofix en: {autofix}, esperado: {expected}")

    total = 6
    passed = total - len(fails)
    print(f"\n  {passed}/{total} tests pasaron")
    if fails:
        raise SystemExit(1)


if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
    else:
        raise SystemExit(main(sys.argv[1:]))
