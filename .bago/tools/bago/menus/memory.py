
import datetime
from pathlib import Path

from ..storage import _load_json
from ..ui import _menu_action, _menu_input, _menu_select, pe, pi


def _markdown_files(root: Path):
    if not root.exists():
        return []
    return sorted(root.rglob("*.md"), key=lambda f: f.relative_to(root).as_posix())

def _cmd_memory(session):
    """Memoria episodica y base de conocimiento."""
    knowledge_dir = Path(__file__).parent.parent / "knowledge"
    epis_file     = Path(__file__).parent.parent / "state" / "episodic_memory.json"

    while True:
        choices = [
            ("knowledge", f"Base de conocimiento  ({len(_markdown_files(knowledge_dir))} archivos)"),
            ("episodic",  "Memoria episodica  (episodic_memory.json)"),
            ("search",    "Buscar en el conocimiento"),
            ("add_note",  "Anadir nota al conocimiento"),
        ]
        sel = _menu_select("BAGO / Memoria", "Gestion de memoria y conocimiento:", choices)
        if sel is None: break

        if sel == "knowledge":
            _memory_knowledge(knowledge_dir)

        elif sel == "episodic":
            _memory_episodic(epis_file)

        elif sel == "search":
            query = _menu_input("Buscar", "Texto a buscar en el conocimiento:")
            if query:
                _memory_search(knowledge_dir, query.lower())

        elif sel == "add_note":
            _memory_add_note(knowledge_dir)

def _memory_knowledge(kdir):
    files = _markdown_files(kdir)
    if not files: pi("No hay archivos de conocimiento."); return
    choices = [(str(f), f.relative_to(kdir).as_posix()) for f in files]
    while True:
        sel = _menu_select("Knowledge base", f"{len(files)} archivos:", choices)
        if sel is None: break
        try:
            content = Path(sel).read_text(encoding="utf-8-sig")
            preview = content[:800] + ("\n...(truncado)" if len(content) > 800 else "")
            _menu_action(Path(sel).name, preview, [("Cerrar","ok")])
        except Exception as e:
            pe(str(e))

def _memory_episodic(epis_file):
    data = _load_json(epis_file)
    if not data: pi("Memoria episodica vacia."); return
    entries = data if isinstance(data, list) else data.get("entries", [data])
    choices = []
    for i, e in enumerate(entries[:30]):
        label = e.get("summary", e.get("event", str(e)[:60]))
        ts    = e.get("timestamp", e.get("date", ""))[:10]
        choices.append((str(i), f"{ts}  {label[:70]}"))
    sel = _menu_select("Memoria episodica", f"{len(entries)} entradas:", choices)
    if sel:
        e = entries[int(sel)]
        info = "\n".join(f"{k}: {v}" for k, v in e.items() if not isinstance(v, dict))
        _menu_action("Entrada episodica", info[:600], [("Cerrar","ok")])

def _memory_search(kdir, query):
    results = []
    for f in _markdown_files(kdir):
        try:
            content = f.read_text(encoding="utf-8-sig").lower()
            if query in content:
                # Encontrar contexto
                idx = content.index(query)
                snippet = content[max(0,idx-60):idx+120].replace("\n", " ")
                results.append((f.relative_to(kdir).as_posix(), snippet))
        except Exception:
            pass
    if not results:
        pi(f"Sin resultados para '{query}'."); return
    choices = [(f"{n}||{s}", f"[cyan]{n}[/cyan]  ...{s}...") for n, s in results[:20]]
    _menu_select(f"Busqueda: '{query}'", f"{len(results)} archivos con coincidencias:", choices)

def _memory_add_note(kdir):
    title = _menu_input("Nueva nota", "Titulo de la nota (sera el nombre del archivo):")
    if not title: return
    content = _menu_input("Contenido", "Contenido de la nota (Markdown):")
    if not content: return
    slug = title.lower().replace(" ", "_").replace("/","_")[:40]
    ts   = datetime.datetime.now().strftime("%Y-%m-%d")
    fpath = kdir / "topics" / f"note_{slug}_{ts}.md"
    fpath.parent.mkdir(parents=True, exist_ok=True)
    fpath.write_text(f"# {title}\n\n> Fecha: {ts}\n\n{content}\n", encoding="utf-8")
    pi(f"Nota guardada: {fpath.name}")
