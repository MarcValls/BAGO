from __future__ import annotations

import json, os, tempfile, uuid, zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Settings
from .database import Database
from .indexer import index_documents, search_documents, search_memories
from .security import SecurityError, ensure_allowed_extension, ensure_managed_write_location, normalize_project_id, safe_resolve

def utc_now() -> str: return datetime.now(timezone.utc).isoformat()
def compact_id(prefix: str) -> str: return f"{prefix}-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"

def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w",encoding="utf-8",delete=False,dir=path.parent,newline="\n") as tmp:
        tmp.write(content); temp=Path(tmp.name)
    os.replace(temp,path)

def record_md(title: str, fields: dict[str,Any], body: str) -> str:
    lines=[f"# {title}",""]+[f"- **{k}:** {'' if v is None else v}" for k,v in fields.items()]
    return "\n".join(lines+["","## Contenido","",body.strip(),""])

TEMPLATES={
"00_IDENTIDAD_Y_ALCANCE.md":"""# Identidad y alcance\n\nProyecto: {pid}\n\nTítulo: {title}\n\n## Propósito\n\n{purpose}\n\n## Límite\n\nNo importa decisiones de otros proyectos sin enlace explícito.\n""",
"01_ESTADO_VIGENTE.md":"""# Estado vigente\n\nEstado documental: inicializado.\n\n## Próxima acción\n\nDefinir objetivo y criterio de cierre.\n""",
"02_CANON_Y_REGLAS.md":"""# Canon y reglas\n\n- La decisión explícita prevalece sobre inferencias.\n- No declarar cierre sin producto y comprobación.\n- Proponer, confirmar y después consolidar.\n""",
"03_REGISTRO_DE_DECISIONES.md":"""# Registro de decisiones\n\nRegistrar identificador, fecha, estado, decisión, causa, fuente, sustitución y alcance.\n""",
"04_ENLACES_INTERPROYECTO.md":"""# Enlaces interproyecto\n\nConsultar `30_LINKS` y el índice MCP.\n""",
"05_PENDIENTES.md":"""# Pendientes\n\nNo hay pendientes registrados.\n""",
}

class MemoryRepository:
    def __init__(self, settings: Settings):
        self.settings=settings; self.root=settings.memory_root; self.db=Database(self.root/"50_INDEX"/"memory.sqlite")

    def initialize(self) -> dict[str,Any]:
        for rel in ["00_KERNEL","10_GLOBAL/MEMORY","20_PROJECTS","30_LINKS","40_INBOX/PROPOSALS","40_INBOX/CONFLICTS","50_INDEX","90_EVENTS","99_ARCHIVE"]:
            (self.root/rel).mkdir(parents=True,exist_ok=True)
        self.db.initialize(); return {"root":str(self.root),**index_documents(self.settings,self.db)}

    def system_status(self) -> dict[str,Any]:
        self.initialize()
        with self.db.connect() as c:
            q=lambda sql:c.execute(sql).fetchone()[0]
            return {"status":"ok","version":"0.1.0","root":str(self.root),"transport":self.settings.transport,"fts5":self.db.fts_enabled(),
            "documents":q("SELECT count(*) FROM documents"),"memories_active":q("SELECT count(*) FROM memories WHERE status='active'"),
            "proposals_pending":q("SELECT count(*) FROM proposals WHERE status='proposed'"),"links_active":q("SELECT count(*) FROM links WHERE status='active'"),"events":q("SELECT count(*) FROM events")}

    def list_projects(self) -> list[dict[str,str]]:
        out=[]; root=self.root/"20_PROJECTS"
        if not root.exists(): return out
        for d in sorted(x for x in root.iterdir() if x.is_dir() and not x.name.startswith('_')):
            title=d.name; f=d/"00_IDENTIDAD_Y_ALCANCE.md"
            if f.exists():
                for line in f.read_text(encoding='utf-8',errors='replace').splitlines():
                    if line.startswith('Título:'): title=line.split(':',1)[1].strip() or title; break
            out.append({"project_id":d.name,"title":title})
        return out

    def create_project(self, project_id: str, title: str, purpose: str) -> dict[str,Any]:
        pid=normalize_project_id(project_id); d=self.root/"20_PROJECTS"/pid; ensure_managed_write_location(self.root,d)
        if d.exists() and any(d.iterdir()): raise FileExistsError(f"El proyecto {pid} ya existe.")
        (d/"MEMORY").mkdir(parents=True,exist_ok=True)
        for name,t in TEMPLATES.items(): atomic_write(d/name,t.format(pid=pid,title=title.strip(),purpose=purpose.strip()))
        self.record_event(pid,"PROJECT_CREATED",f"Proyecto {pid} creado.",""); index_documents(self.settings,self.db)
        return {"project_id":pid,"path":f"20_PROJECTS/{pid}","status":"created"}

    def read_file(self, relative_path: str, start_line: int=1, max_lines: int=200) -> dict[str,Any]:
        p=safe_resolve(self.root,relative_path); ensure_allowed_extension(p,self.settings.allowed_extensions)
        if not p.is_file(): raise IsADirectoryError(relative_path)
        if p.stat().st_size>self.settings.max_read_bytes: raise SecurityError("El archivo supera el límite de lectura.")
        lines=p.read_text(encoding='utf-8',errors='replace').splitlines(); start=max(start_line,1)-1; count=min(max(max_lines,1),1000); selected=lines[start:start+count]
        return {"path":p.relative_to(self.root).as_posix(),"start_line":start+1,"end_line":start+len(selected),"total_lines":len(lines),"content":"\n".join(selected),"has_more":start+len(selected)<len(lines)}

    def get_project_state(self, project_id: str) -> dict[str,Any]:
        pid=normalize_project_id(project_id); d=self.root/"20_PROJECTS"/pid
        if not d.exists(): raise FileNotFoundError(f"No existe {pid}.")
        f=d/"01_ESTADO_VIGENTE.md"; state=f.read_text(encoding='utf-8',errors='replace') if f.exists() else ''
        with self.db.connect() as c:
            mem=[dict(r) for r in c.execute("SELECT memory_id,memory_class,category,statement,source_reference,authority_level,confidence,updated_at FROM memories WHERE project_id=? AND status='active' ORDER BY authority_level DESC,updated_at DESC LIMIT 20",(pid,))]
            links=[dict(r) for r in c.execute("SELECT link_id,source_project,target_project,concept,authority,conditions,source_reference,status FROM links WHERE status='active' AND (source_project=? OR target_project=?) ORDER BY created_at DESC LIMIT 20",(pid,pid))]
            pending=c.execute("SELECT count(*) FROM proposals WHERE project_id=? AND status='proposed'",(pid,)).fetchone()[0]
        return {"project_id":pid,"state_document":state[:12000],"active_memories":mem,"conflicts":[m for m in mem if m['memory_class']=='MEM_CONFLICT'],"links":links,"pending_proposals":pending}

    def search(self, query: str, project_id: str='', limit: int=10, include_inferred: bool=False) -> dict[str,Any]:
        pid=normalize_project_id(project_id) if project_id.strip() else ''; limit=min(max(limit,1),self.settings.max_results)
        return {"query":query,"project_id":pid or None,"documents":search_documents(self.db,query,pid,limit),"memories":search_memories(self.db,query,pid,limit,include_inferred)}

    def get_context(self, project_id: str, query: str, limit: int=8) -> dict[str,Any]:
        return {"project":project_id.upper(),"state":self.get_project_state(project_id),"relevant":self.search(query,project_id,limit),"usage":["Prioriza estado y memoria confirmada.","No trates inferencias como canon.","Resuelve conflictos antes de escribir.","Usa memory_propose para conocimiento nuevo."]}

    def propose_memory(self, project_id: str, statement: str, category: str, source_reference: str, proposed_class: str='MEM_INFERRED', scope: str='project', authority_level: int=50, confidence: float=.75) -> dict[str,Any]:
        pid='GLOBAL' if project_id.strip().upper()=='GLOBAL' else normalize_project_id(project_id)
        if proposed_class not in {'MEM_CONFIRMED','MEM_INFERRED','MEM_CONFLICT','MEM_EVENT'}: raise ValueError('Clase no permitida.')
        if not statement.strip(): raise ValueError('Contenido vacío.')
        if not 0<=confidence<=1 or not 0<=authority_level<=100: raise ValueError('Confianza o autoridad fuera de rango.')
        ident=compact_id('PRP'); created=utc_now(); rel=f"40_INBOX/PROPOSALS/{ident}.md"; p=safe_resolve(self.root,rel,must_exist=False); ensure_managed_write_location(self.root,p)
        atomic_write(p,record_md(f"Propuesta {ident}",{"proposal_id":ident,"project_id":pid,"scope":scope,"proposed_class":proposed_class,"category":category,"source_reference":source_reference,"authority_level":authority_level,"confidence":confidence,"status":"proposed","created_at":created},statement))
        with self.db.connect() as c: c.execute("INSERT INTO proposals(proposal_id,project_id,scope,proposed_class,category,statement,source_reference,authority_level,confidence,status,created_at,file_path) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(ident,pid,scope,proposed_class,category,statement.strip(),source_reference.strip(),authority_level,confidence,'proposed',created,rel))
        self.record_event(pid,'MEMORY_PROPOSED',f"Propuesta {ident}: {statement[:180]}",source_reference); index_documents(self.settings,self.db)
        return {"proposal_id":ident,"status":"proposed","file_path":rel}

    def list_pending_proposals(self, project_id: str='') -> list[dict[str,Any]]:
        pid=normalize_project_id(project_id) if project_id.strip() else ''
        sql="SELECT proposal_id,project_id,scope,proposed_class,category,statement,source_reference,authority_level,confidence,created_at,file_path FROM proposals WHERE status='proposed'"; params=[]
        if pid: sql+=' AND project_id=?'; params.append(pid)
        sql+=' ORDER BY created_at DESC LIMIT 100'
        with self.db.connect() as c: return [dict(r) for r in c.execute(sql,params)]

    def commit_memory(self, proposal_id: str, approved_by: str, final_class: str='MEM_CONFIRMED', supersedes: str='', contradicts: str='') -> dict[str,Any]:
        if final_class not in {'MEM_CONFIRMED','MEM_INFERRED','MEM_CONFLICT','MEM_EVENT'} or not approved_by.strip(): raise ValueError('Clase o aprobador inválido.')
        with self.db.connect() as c:
            p=c.execute("SELECT * FROM proposals WHERE proposal_id=?",(proposal_id,)).fetchone()
            if not p: raise KeyError(f"No existe {proposal_id}.")
            if p['status']!='proposed': raise ValueError(f"Estado: {p['status']}")
            mid=compact_id('MEM'); now=utc_now(); pid=p['project_id']; rel=f"10_GLOBAL/MEMORY/{mid}.md" if pid=='GLOBAL' else f"20_PROJECTS/{pid}/MEMORY/{mid}.md"; path=safe_resolve(self.root,rel,must_exist=False); ensure_managed_write_location(self.root,path)
            atomic_write(path,record_md(f"Memoria {mid}",{"memory_id":mid,"project_id":pid,"scope":p['scope'],"memory_class":final_class,"category":p['category'],"source_reference":p['source_reference'],"authority_level":p['authority_level'],"confidence":p['confidence'],"status":"active","approved_by":approved_by,"created_at":now,"supersedes":supersedes,"contradicts":contradicts},p['statement']))
            c.execute("INSERT INTO memories(memory_id,project_id,scope,memory_class,category,statement,source_reference,authority_level,confidence,status,created_at,updated_at,supersedes,contradicts,file_path) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(mid,pid,p['scope'],final_class,p['category'],p['statement'],p['source_reference'],p['authority_level'],p['confidence'],'active',now,now,supersedes or None,contradicts or None,rel))
            c.execute("UPDATE proposals SET status='committed',resolved_at=?,resolved_by=?,memory_id=? WHERE proposal_id=?",(now,approved_by.strip(),mid,proposal_id))
            if self.db.fts_enabled(): c.execute("INSERT INTO memory_fts(memory_id,statement,category,project_id,scope) VALUES(?,?,?,?,?)",(mid,p['statement'],p['category'],pid,p['scope']))
        self.record_event(pid,'MEMORY_COMMITTED',f"{mid} confirmada desde {proposal_id}.",approved_by); index_documents(self.settings,self.db)
        return {"memory_id":mid,"status":"active","file_path":rel}

    def deprecate_memory(self, memory_id: str, reason: str, superseded_by: str='') -> dict[str,Any]:
        if not reason.strip(): raise ValueError('Razón obligatoria.')
        with self.db.connect() as c:
            m=c.execute("SELECT * FROM memories WHERE memory_id=?",(memory_id,)).fetchone()
            if not m: raise KeyError(f"No existe {memory_id}.")
            if m['status']!='active': raise ValueError(f"Estado: {m['status']}")
            c.execute("UPDATE memories SET status='deprecated',updated_at=? WHERE memory_id=?",(utc_now(),memory_id))
            if self.db.fts_enabled(): c.execute("DELETE FROM memory_fts WHERE memory_id=?",(memory_id,))
        p=safe_resolve(self.root,m['file_path']); old=p.read_text(encoding='utf-8',errors='replace'); atomic_write(p,old.rstrip()+f"\n\n## Deprecación\n\n- **reason:** {reason}\n- **superseded_by:** {superseded_by}\n")
        self.record_event(m['project_id'],'MEMORY_DEPRECATED',f"{memory_id}: {reason}",superseded_by)
        return {"memory_id":memory_id,"status":"deprecated","superseded_by":superseded_by or None}

    def create_link(self, source_project: str, target_project: str, concept: str, authority: str, source_reference: str, conditions: str='') -> dict[str,Any]:
        s=normalize_project_id(source_project); t=normalize_project_id(target_project)
        if s==t: raise ValueError('Origen y destino deben diferir.')
        lid=compact_id('LNK'); now=utc_now(); rel=f"30_LINKS/{s}__{t}__{lid}.md"; p=safe_resolve(self.root,rel,must_exist=False); ensure_managed_write_location(self.root,p)
        atomic_write(p,record_md(f"Enlace {s} → {t}",{"link_id":lid,"source_project":s,"target_project":t,"authority":authority,"conditions":conditions,"source_reference":source_reference,"status":"active","created_at":now},concept))
        with self.db.connect() as c: c.execute("INSERT INTO links(link_id,source_project,target_project,concept,authority,conditions,source_reference,status,created_at,file_path) VALUES(?,?,?,?,?,?,?,?,?,?)",(lid,s,t,concept.strip(),authority.strip(),conditions.strip(),source_reference.strip(),'active',now,rel))
        self.record_event(t,'PROJECT_LINK_CREATED',f"{s} → {t}: {concept[:160]}",source_reference); index_documents(self.settings,self.db)
        return {"link_id":lid,"status":"active","file_path":rel}

    def record_event(self, project_id: str, event_type: str, summary: str, evidence: str='') -> dict[str,Any]:
        pid=project_id.strip().upper() or 'GLOBAL'; pid=pid if pid=='GLOBAL' else normalize_project_id(pid); eid=compact_id('EVT'); now=utc_now()
        with self.db.connect() as c: c.execute("INSERT INTO events(event_id,project_id,event_type,summary,evidence,created_at) VALUES(?,?,?,?,?,?)",(eid,pid,event_type.strip(),summary.strip(),evidence.strip(),now))
        rel=f"90_EVENTS/{datetime.now(timezone.utc):%Y-%m}.jsonl"; p=safe_resolve(self.root,rel,must_exist=False); ensure_managed_write_location(self.root,p); p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('a',encoding='utf-8',newline='\n') as f: f.write(json.dumps({"event_id":eid,"project_id":pid,"event_type":event_type.strip(),"summary":summary.strip(),"evidence":evidence.strip(),"created_at":now},ensure_ascii=False)+'\n')
        return {"event_id":eid,"status":"recorded"}

    def reindex(self) -> dict[str,Any]: return index_documents(self.settings,self.db)
    def backup(self, destination: Path|None=None) -> Path:
        dest=destination or self.root.parent/'backups'; dest.mkdir(parents=True,exist_ok=True); out=dest/f"IA_MEMORIA_BACKUP_{datetime.now():%Y%m%d_%H%M%S}.zip"
        with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
            for p in self.root.rglob('*'):
                if p.is_file() and not p.name.endswith(('-wal','-shm')): z.write(p,p.relative_to(self.root.parent))
        return out
