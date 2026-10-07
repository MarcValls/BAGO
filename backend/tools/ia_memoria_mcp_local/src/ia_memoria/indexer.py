from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

from .config import Settings
from .database import Database

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def infer_context(relative: Path) -> tuple[str, str]:
    parts = relative.parts
    if parts and parts[0] == "20_PROJECTS" and len(parts) >= 2:
        return parts[1].upper(), "project"
    if parts and parts[0] == "30_LINKS": return "GLOBAL", "links"
    if parts and parts[0] == "00_KERNEL": return "GLOBAL", "kernel"
    if parts and parts[0] == "10_GLOBAL": return "GLOBAL", "global"
    if parts and parts[0] == "40_INBOX": return "GLOBAL", "inbox"
    return "GLOBAL", "other"

def extract_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "): return line[2:].strip()[:200]
    return fallback

def index_documents(settings: Settings, db: Database) -> dict[str, int]:
    root = settings.memory_root
    scanned = {}
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in settings.allowed_extensions: continue
        relative = path.relative_to(root)
        if relative.parts and relative.parts[0] in {"50_INDEX", "90_EVENTS", "99_ARCHIVE"}: continue
        if path.stat().st_size > settings.max_read_bytes * 4: continue
        body = path.read_text(encoding="utf-8", errors="replace")
        scanned[relative.as_posix()] = (*infer_context(relative), extract_title(body,path.name), body, path.stat().st_mtime, hashlib.sha256(body.encode()).hexdigest())
    with db.connect() as conn:
        existing = {r['path'] for r in conn.execute("SELECT path FROM documents")}
        current = set(scanned)
        for missing in existing-current:
            conn.execute("DELETE FROM documents WHERE path=?",(missing,))
            if db.fts_enabled(): conn.execute("DELETE FROM document_fts WHERE path=?",(missing,))
        for rel,(pid,scope,title,body,mtime,digest) in scanned.items():
            conn.execute("""INSERT INTO documents(path,project_id,scope,title,body,content_hash,mtime,updated_at)
            VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET project_id=excluded.project_id,scope=excluded.scope,title=excluded.title,body=excluded.body,content_hash=excluded.content_hash,mtime=excluded.mtime,updated_at=excluded.updated_at""",
            (rel,pid,scope,title,body,digest,mtime,utc_now()))
            if db.fts_enabled():
                conn.execute("DELETE FROM document_fts WHERE path=?",(rel,))
                conn.execute("INSERT INTO document_fts(path,title,body,project_id,scope) VALUES(?,?,?,?,?)",(rel,title,body,pid,scope))
    return {"indexed":len(scanned),"removed":len(existing-current)}

def _tokens(q: str) -> list[str]:
    return [t for t in re.findall(r"[\wáéíóúüñ-]+",q.lower()) if len(t)>1]

def search_documents(db: Database, query: str, project_id: str="", limit: int=10) -> list[dict]:
    if not query.strip(): return []
    rows=[]; pid=project_id.strip().upper()
    with db.connect() as conn:
        if db.fts_enabled():
            fq=" AND ".join(f'"{t.replace(chr(34),"")}"' for t in _tokens(query))
            if fq:
                sql="SELECT path,title,project_id,scope,snippet(document_fts,2,'[',']',' … ',24) snippet,bm25(document_fts) rank FROM document_fts WHERE document_fts MATCH ?"
                params=[fq]
                if pid: sql+=" AND project_id IN (?, 'GLOBAL')"; params.append(pid)
                sql+=" ORDER BY rank LIMIT ?"; params.append(limit)
                try: rows=conn.execute(sql,params).fetchall()
                except Exception: rows=[]
        if not rows:
            like=f"%{query}%"; sql="SELECT path,title,project_id,scope,substr(body,1,700) snippet,100.0 rank FROM documents WHERE (title LIKE ? OR body LIKE ?)"; params=[like,like]
            if pid: sql+=" AND project_id IN (?, 'GLOBAL')"; params.append(pid)
            sql+=" ORDER BY updated_at DESC LIMIT ?"; params.append(limit)
            rows=conn.execute(sql,params).fetchall()
    return [dict(r) for r in rows]

def search_memories(db: Database, query: str, project_id: str="", limit: int=10, include_inferred: bool=False) -> list[dict]:
    if not query.strip(): return []
    classes=("MEM_CONFIRMED","MEM_CONFLICT","MEM_INFERRED") if include_inferred else ("MEM_CONFIRMED","MEM_CONFLICT")
    marks=','.join('?' for _ in classes); like=f"%{query}%"; pid=project_id.strip().upper()
    sql=f"SELECT memory_id,project_id,scope,memory_class,category,statement,source_reference,authority_level,confidence,status,updated_at,file_path FROM memories WHERE status='active' AND memory_class IN ({marks}) AND (statement LIKE ? OR category LIKE ?)"
    params=list(classes)+[like,like]
    if pid: sql+=" AND project_id IN (?, 'GLOBAL')"; params.append(pid)
    sql+=" ORDER BY authority_level DESC,updated_at DESC LIMIT ?"; params.append(limit)
    with db.connect() as conn: return [dict(r) for r in conn.execute(sql,params)]
