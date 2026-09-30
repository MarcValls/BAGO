#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Maquetador editorial IA. LA PREGUNTA.
Markdown -> HTML -> PDF con TOC paginado y familias visuales.
Usa WeasyPrint; si no está disponible, intenta Edge/Chrome headless.
"""
from __future__ import annotations
import argparse, html, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
from urllib.parse import quote

try:
    import mistune
except Exception:
    mistune=None

ROMAN={0:'0',1:'I',2:'II',3:'III',4:'IV',5:'V',6:'VI',7:'VII',8:'VIII',9:'IX',10:'X',11:'XI',12:'XII',13:'XIII',14:'XIV'}


def parse_frontmatter(text:str):
    data={}; m=re.match(r"^---\s*\n(.*?)\n---\s*\n",text,re.S)
    body=text
    if m:
        for ln in m.group(1).splitlines():
            mm=re.match(r"\s*([\w-]+)\s*:\s*[\"']?(.*?)[\"']?\s*$",ln)
            if mm: data[mm.group(1)]=mm.group(2)
        body=text[m.end():]
    return data,body


def infer_editorial_meta(meta:dict, md:str, filename:str):
    # Número de volumen
    if meta.get('volume_number'):
        num=int(meta['volume_number'])
    else:
        m=re.search(r'^#\s*Volumen\s+(\d+)\b',md,re.M|re.I) or re.search(r'Volumen[_\s]+(\d+)',filename,re.I)
        num=int(m.group(1)) if m else 0
    title=meta.get('volume_title','').strip()
    if not title:
        m=re.search(r'^#\s*Volumen\s+\d+\s*[—-]\s*(.+?)\s*$',md,re.M|re.I)
        title=m.group(1).strip() if m else f'Volumen {num}'
    subtitle=meta.get('subtitle','').strip()
    if not subtitle:
        m=re.search(r'^\*\*Subt[ií]tulo:\*\*\s*(.+?)\s*$',md,re.M|re.I)
        subtitle=m.group(1).strip() if m else ''
    collection=meta.get('collection','').strip()
    if not collection:
        m=re.search(r'^#\s*(IA\.\s*LA\s+PREGUNTA)\s*$',md,re.M|re.I)
        collection=m.group(1).strip() if m else 'IA. LA PREGUNTA'
    author=meta.get('author','Marc Valls').strip()
    return num,title,subtitle,collection,author


def strip_redundant_top_metadata(md:str, num:int, title:str, subtitle:str, collection:str):
    # La portada se genera aparte; quitamos solo los encabezados/metadatos editoriales iniciales redundantes.
    md=re.sub(r'^#\s*IA\.\s*LA\s+PREGUNTA\s*\n+', '', md, count=1, flags=re.M|re.I)
    md=re.sub(rf'^#\s*Volumen\s+{num}\s*[—-]\s*{re.escape(title)}\s*\n+', '', md, count=1, flags=re.M|re.I)
    md=re.sub(r'^\*\*Subt[ií]tulo:\*\*\s*.+?\s*\n+', '', md, count=1, flags=re.M|re.I)
    return md

def slug(s:str):
    import unicodedata
    s=unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower()
    s=re.sub(r'[^a-z0-9]+','-',s).strip('-')
    return s or 'sec'


def extract_headings(md:str):
    out=[]; seen={}
    for ln in md.splitlines():
        m=re.match(r"^(#{1,3})\s+(.+?)\s*$",ln)
        if not m: continue
        level=len(m.group(1)); title=re.sub(r"[*_`]+",'',m.group(2)).strip()
        base=slug(title); n=seen.get(base,0)+1; seen[base]=n; sid=base if n==1 else f"{base}-{n}"
        out.append((level,title,sid))
    return out


def preprocess(md:str):
    md=re.sub(r"^\\newpage\s*$",'<div class="page-break"></div>',md,flags=re.M)
    # preservar math como bloque tipográfico
    stash=[]
    def mathrepl(m):
        tok=f"@@IALPMATH{len(stash)}@@"; stash.append(m.group(1).strip()); return tok
    md=re.sub(r"```math\s*\n(.*?)\n```",mathrepl,md,flags=re.S|re.I)
    return md,stash


def md_to_html(md:str):
    if mistune is not None:
        renderer=mistune.HTMLRenderer(escape=False)
        markdown=mistune.create_markdown(renderer=renderer,plugins=['table','strikethrough','task_lists'])
        return markdown(md)
    try:
        import markdown as python_markdown
    except ImportError as exc:
        raise RuntimeError('Instale mistune o Markdown para convertir el manuscrito.') from exc
    return python_markdown.markdown(md,extensions=['tables','fenced_code','sane_lists'])


def inject_ids(body:str, headings):
    it=iter(headings)
    def repl(m):
        try: lvl,title,sid=next(it)
        except StopIteration: return m.group(0)
        return f'<h{lvl} id="{sid}">{m.group(2)}</h{lvl}>'
    return re.sub(r"<h([1-3])>(.*?)</h\1>",repl,body,flags=re.S)


def build_toc(headings):
    rows=[]
    for level,title,sid in headings:
        if level==1 and len(rows)==0: continue
        index=len(rows)
        rows.append(
            f'<div class="toc-l{level}"><a href="#{sid}">'
            f'<span class="toc-title">{html.escape(title)}</span>'
            '<span class="toc-leader" aria-hidden="true"></span>'
            f'<span class="toc-page" data-index="{index}">00</span>'
            '</a></div>'
        )
    return '<section class="toc"><h1>Índice</h1>'+''.join(rows)+'</section><div class="page-break"></div>'


def paginate_toc(html_text:str,html_path:Path,engine:str)->str:
    """Resolve TOC page numbers from the first rendered PDF's anchor destinations."""
    import fitz
    with tempfile.TemporaryDirectory(prefix='bago-toc-') as tmp:
        draft=Path(tmp)/'draft.pdf'
        render_pdf(html_path,draft,engine)
        doc=fitz.open(draft)
        destinations=[]
        started=False
        for page in doc:
            links=sorted(page.get_links(),key=lambda link:(link.get('from').y0 if link.get('from') else 0))
            if links:
                started=True
                destinations.extend(link.get('page',-1)+1 for link in links)
            elif started:
                break
        placeholders=list(re.finditer(r'<span class="toc-page" data-index="(\d+)">00</span>',html_text))
        if len(destinations)!=len(placeholders) or any(page<1 for page in destinations):
            raise RuntimeError(f'Índice no resoluble: {len(placeholders)} entradas y {len(destinations)} destinos PDF')
        for index,page in reversed(list(enumerate(destinations))):
            html_text=html_text.replace(
                f'<span class="toc-page" data-index="{index}">00</span>',
                f'<span class="toc-page" data-index="{index}">{page}</span>',
                1,
            )
        doc.close()
    return html_text


def family_for(num:int, requested:str):
    if requested and requested!='auto': return requested
    if num==0: return 'puerta'
    if 1<=num<=11: return 'doctrina'
    return 'sintesis'


def find_browser():
    candidates=[
        r'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
        r'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
        r'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
        r'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
        'msedge','chrome','chromium','google-chrome']
    for c in candidates:
        if os.path.isabs(c) and os.path.exists(c): return c
        p=shutil.which(c)
        if p: return p
    return None


def render_pdf(html_path:Path,pdf_path:Path,engine:str):
    if engine in ('auto','weasyprint'):
        try:
            from weasyprint import HTML
            HTML(filename=str(html_path),base_url=str(html_path.parent)).write_pdf(str(pdf_path))
            return 'weasyprint'
        except Exception as e:
            if engine=='weasyprint': raise
            print('[WARN] WeasyPrint no disponible/usable:',e)
    b=find_browser()
    if not b: raise RuntimeError('No hay WeasyPrint funcional ni Edge/Chrome encontrado.')
    cp=subprocess.run([b,'--headless=new','--disable-gpu','--no-sandbox',f'--print-to-pdf={pdf_path}',html_path.resolve().as_uri()],capture_output=True,text=True,timeout=180)
    if cp.returncode!=0: raise RuntimeError(cp.stderr or cp.stdout)
    return 'browser'


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('source'); ap.add_argument('pdf')
    ap.add_argument('--html',default=None); ap.add_argument('--family',default='auto',choices=['auto','puerta','doctrina','sintesis','informe'])
    ap.add_argument('--engine',default='auto',choices=['auto','weasyprint','browser'])
    a=ap.parse_args(); src=Path(a.source).resolve(); pdf=Path(a.pdf).resolve(); root=Path(__file__).resolve().parents[1]
    meta,md=parse_frontmatter(src.read_text(encoding='utf-8'))
    num,title,subtitle,collection,author=infer_editorial_meta(meta,md,src.name)
    md=strip_redundant_top_metadata(md,num,title,subtitle,collection)
    family=family_for(num,meta.get('family',a.family) if a.family=='auto' else a.family)
    md,mathstash=preprocess(md)
    headings=extract_headings(md)
    body=inject_ids(md_to_html(md),headings)
    for i,formula in enumerate(mathstash):
        body=body.replace(f'@@IALPMATH{i}@@',f'<div class="math-block"><pre>{html.escape(formula)}</pre></div>')
    toc=build_toc(headings)
    cover_label=meta.get('cover_label',f'VOLUMEN {ROMAN.get(num,str(num))}')
    cover=f'''<section class="cover"><div class="eyebrow">{html.escape(collection)}</div><div class="vol">{html.escape(cover_label)}</div><h1>{html.escape(title)}</h1><p class="subtitle">{html.escape(subtitle)}</p><div class="rule"></div><p class="author">{html.escape(author)}</p></section>'''
    css_root=Path(__file__).resolve().parent
    css=(css_root/'ialp_base.css').read_text(encoding='utf-8')+'\n'+(css_root/f'ialp_{family}.css').read_text(encoding='utf-8')
    doc=f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><title>{html.escape(title)}</title><style>{css}</style></head><body>{cover}{toc}<main>{body}</main></body></html>'''
    html_path=Path(a.html).resolve() if a.html else pdf.with_suffix('.html'); html_path.parent.mkdir(parents=True,exist_ok=True); pdf.parent.mkdir(parents=True,exist_ok=True)
    html_path.write_text(doc,encoding='utf-8')
    doc=paginate_toc(doc,html_path,a.engine)
    html_path.write_text(doc,encoding='utf-8')
    used=render_pdf(html_path,pdf,a.engine)
    print(f'OK: {pdf} | motor={used} | familia={family}')

if __name__=='__main__': main()
