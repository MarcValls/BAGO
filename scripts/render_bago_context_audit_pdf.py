#!/usr/bin/env python3
"""Render the dated BAGO context and ecosystem audit as a colored PDF.

Requires PyMuPDF (fitz). This is a standalone editorial artifact generator;
it does not infer or refresh repository evidence.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "BAGO_contexto_auditoria_ecosistema_2026-09-27.pdf"
MIND_MAP_DATA = ROOT / "docs" / "architecture" / "bago_mind_map.data.json"
PAGE_W, PAGE_H = 842, 595  # A4 landscape, points
MARGIN = 42
FONT = Path(r"C:\Windows\Fonts\segoeui.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\segoeuib.ttf")

NAVY = (0.055, 0.09, 0.16)
INK = (0.12, 0.17, 0.25)
MUTED = (0.38, 0.44, 0.53)
PAPER = (0.97, 0.98, 0.99)
WHITE = (1, 1, 1)
CYAN = (0.08, 0.66, 0.78)
BLUE = (0.19, 0.39, 0.76)
VIOLET = (0.43, 0.31, 0.71)
GREEN = (0.13, 0.56, 0.39)
AMBER = (0.88, 0.51, 0.10)
RED = (0.74, 0.20, 0.20)
PALE_CYAN = (0.89, 0.96, 0.98)
PALE_BLUE = (0.91, 0.94, 0.99)
PALE_VIOLET = (0.95, 0.92, 0.98)
PALE_GREEN = (0.90, 0.96, 0.92)
PALE_AMBER = (1.00, 0.96, 0.87)
PALE_RED = (0.99, 0.92, 0.91)
PALE_GREY = (0.94, 0.95, 0.97)


class Report:
    def __init__(self, sha: str, output: Path):
        self.sha = sha
        self.output = output
        self.doc = fitz.open()
        self.page_no = 0

    def page(self, title: str, section: str = "INFORME DE ESTADO") -> fitz.Page:
        self.page_no += 1
        p = self.doc.new_page(width=PAGE_W, height=PAGE_H)
        p.insert_font(fontname="body", fontfile=str(FONT))
        p.insert_font(fontname="bold", fontfile=str(FONT_BOLD))
        p.draw_rect(p.rect, color=None, fill=PAPER)
        p.draw_rect(fitz.Rect(0, 0, PAGE_W, 8), color=None, fill=CYAN)
        p.insert_text((MARGIN, 31), section.upper(), fontname="bold", fontsize=8,
                      color=CYAN, overlay=True)
        p.insert_textbox(fitz.Rect(MARGIN, 43, PAGE_W - MARGIN, 78), title,
                         fontname="bold", fontsize=22, color=NAVY, overlay=True)
        p.draw_line((MARGIN, 83), (PAGE_W - MARGIN, 83), color=(0.84, 0.88, 0.92), width=0.8)
        p.draw_line((MARGIN, PAGE_H - 31), (PAGE_W - MARGIN, PAGE_H - 31),
                    color=(0.84, 0.88, 0.92), width=0.7)
        p.insert_text((MARGIN, PAGE_H - 17), f"BAGO 4.11.1  |  {self.sha}  |  27 SEP 2026",
                      fontname="body", fontsize=7.5, color=MUTED)
        p.insert_text((PAGE_W - MARGIN - 30, PAGE_H - 17), f"{self.page_no:02d}",
                      fontname="bold", fontsize=8, color=INK)
        return p

    def text(self, p: fitz.Page, box: tuple[float, float, float, float], value: str,
             size: float = 10, color=INK, bold: bool = False, align=0,
             lineheight: float = 1.18) -> float:
        return p.insert_textbox(fitz.Rect(*box), value, fontname="bold" if bold else "body",
                                fontsize=size, color=color, align=align,
                                lineheight=lineheight, overlay=True)

    def card(self, p: fitz.Page, x: float, y: float, w: float, h: float, title: str,
             body: str, accent=CYAN, fill=WHITE, body_size=9.3, tag: str | None = None):
        r = fitz.Rect(x, y, x + w, y + h)
        p.draw_rect(r, color=(0.88, 0.90, 0.93), fill=fill, width=0.7, radius=0.08, overlay=True)
        p.draw_rect(fitz.Rect(x, y, x + 5, y + h), color=None, fill=accent, overlay=True)
        self.text(p, (x + 16, y + 13, x + w - 13, y + 34), title, 11, NAVY, True)
        top = y + 39
        if tag:
            tag_w = max(58, len(tag) * 5.2 + 14)
            p.draw_rect(fitz.Rect(x + 16, top, x + 16 + tag_w, top + 17),
                        color=None, fill=accent, radius=0.08, overlay=True)
            self.text(p, (x + 22, top + 3, x + 14 + tag_w, top + 15), tag.upper(),
                      7.1, WHITE, True)
            top += 22
        result = self.text(p, (x + 16, top, x + w - 13, y + h - 10), body,
                           body_size, INK, lineheight=1.17)
        if result < 0:
            raise ValueError(f"Text overflow in card {title!r}: {result}")

    def pill(self, p, x, y, label, fill, width=None):
        width = width or max(52, len(label) * 5.1 + 18)
        p.draw_rect(fitz.Rect(x, y, x + width, y + 22), color=None, fill=fill,
                    radius=0.08, overlay=True)
        self.text(p, (x + 8, y + 4, x + width - 6, y + 18), label, 8, WHITE, True)

    def save(self):
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.doc.set_metadata({
            "title": "BAGO: mapa mental, auditoria del codigo y comparacion con el ecosistema MarcValls",
            "author": "BAGO project review",
            "subject": f"Estado ligado al worktree local con HEAD {self.sha}, 2026-09-27",
            "keywords": "BAGO, arquitectura, auditoria, sinks, ExecutionGateway, ecosistema MarcValls",
        })
        self.doc.save(self.output, garbage=4, deflate=True)


def build(sha: str, output: Path):
    r = Report(sha, output)

    # 1 - Cover and architecture at a glance.
    p = r.doc.new_page(width=PAGE_W, height=PAGE_H)
    r.page_no += 1
    p.insert_font(fontname="body", fontfile=str(FONT)); p.insert_font(fontname="bold", fontfile=str(FONT_BOLD))
    p.draw_rect(p.rect, color=None, fill=NAVY)
    p.draw_rect(fitz.Rect(0, 0, PAGE_W, 9), color=None, fill=CYAN)
    p.insert_text((MARGIN, 60), "ARQUITECTURA DE CONTEXTO  /  AUDITORIA ACTUALIZADA",
                  fontname="bold", fontsize=9, color=CYAN)
    r.text(p, (MARGIN, 95, 510, 226),
           "BAGO: mapa mental completo,\nauditoria del codigo y\ncomparacion con el ecosistema MarcValls",
           29, WHITE, True, lineheight=1.02)
    r.text(p, (MARGIN, 246, 470, 307),
           "Edicion actualizada al 27 de septiembre de 2026.\nVersion de producto: 4.11.1.\nCandidato observado: " + sha,
           11, (0.77, 0.83, 0.90), lineheight=1.35)
    # Authority flow diagram
    r.text(p, (520, 100, 798, 123), "MODELO OPERATIVO ACTUAL", 9, CYAN, True)
    nodes = [
        ("USUARIO", (0.12, 0.28, 0.45)),
        ("SESION + CONTEXTO", BLUE),
        ("POLITICA + ELEGIBILIDAD", VIOLET),
        ("AUTHORIZATION BOUNDARY", AMBER),
        ("EXECUTION GATEWAY", CYAN),
        ("OWNER DEL EFECTO", GREEN),
        ("SINK + RECEIPT", (0.25, 0.34, 0.46)),
    ]
    yy = 142
    for i, (label, color) in enumerate(nodes):
        rr = fitz.Rect(535, yy, 790, yy + 35)
        p.draw_rect(rr, color=None, fill=color, radius=0.08, overlay=True)
        r.text(p, (548, yy + 10, 778, yy + 27), label, 8.6, WHITE, True, align=1)
        if i < len(nodes) - 1:
            p.draw_line((662, yy + 36), (662, yy + 48), color=(0.47, 0.58, 0.72), width=1.3)
            p.draw_line((658, yy + 44), (662, yy + 48), color=(0.47, 0.58, 0.72), width=1.3)
            p.draw_line((666, yy + 44), (662, yy + 48), color=(0.47, 0.58, 0.72), width=1.3)
        yy += 53
    p.draw_rect(fitz.Rect(MARGIN, 355, 800, 450), color=None, fill=(0.10, 0.15, 0.23), radius=0.08)
    r.text(p, (MARGIN + 18, 372, 775, 402),
           "VEREDICTO ACTUAL: EL GATE GLOBAL DE EFECTOS SIGUE ABIERTO", 13, WHITE, True)
    r.text(p, (MARGIN + 18, 410, 775, 438),
           "4.491 findings  |  264 runtime-unbound  |  0 unclassified  |  strict-runtime FAIL  |  P0: bootstrap NSIS",
           10, (0.83, 0.88, 0.94), True)
    r.text(p, (MARGIN, 505, 800, 556),
           "Documento de orientacion arquitectonica, no recibo de release ni certificacion.\nHechos de BAGO ligados al worktree indicado; comparadores externos referenciados al final.",
           8.5, (0.65, 0.72, 0.81), lineheight=1.35)
    p.insert_text((MARGIN, PAGE_H - 21), "BAGO 4.11.1  |  LOCAL CANDIDATE  |  2026-09-27", fontname="body", fontsize=7.5, color=(0.65,0.72,0.81))
    p.insert_text((PAGE_W - MARGIN - 30, PAGE_H - 21), "01", fontname="bold", fontsize=8, color=WHITE)

    # 2 - Executive reading.
    p=r.page("Lectura ejecutiva", "01 / RESUMEN")
    r.card(p,42,102,244,144,"Tesis del producto",
           "BAGO funciona como un plano de control local centrado en la sesion. La sesion conserva contexto y estado mientras providers y modelos pueden cambiar. El backend decide; React y Electron presentan.",BLUE,PALE_BLUE)
    r.card(p,299,102,244,144,"Lo mejor consolidado",
           "Contratos de sesion, adapters de providers, recibos, claims y un ExecutionGateway que consume permisos antes de despachar a owners registrados.",GREEN,PALE_GREEN)
    r.card(p,556,102,244,144,"Bloqueo principal",
           "El instalador NSIS de maquina limpia produce efectos antes de cargar la frontera canonica. El scanner tampoco reconoce InitPluginsDir, asi que no cubre todos los efectos de esa ruta.",RED,PALE_RED,tag="P0 / STOP")
    r.card(p,42,263,371,171,"Que significa el inventario",
           "El scanner actual encuentra 4.491 findings. De estos, 264 son runtime-unbound y 0 quedan sin scope o binding.\n\nLa clasificacion estricta pasa para lo que el scanner detecta. No prueba que detecte todas las formas de efecto: falta cerrar cobertura NSIS antes de planificar el residual como completo.",AMBER,PALE_AMBER)
    r.card(p,428,263,372,171,"Que no se puede concluir aun",
           "No hay cierre global, ni autorizacion para declarar VERIFIED / VALIDATED. El resultado de 1.670 tests aportado corresponde al SHA 9633118, anterior a los nueve commits remotos y al merge local. No es evidencia del candidato actual 758790bb.",VIOLET,PALE_VIOLET)
    r.text(p,(42,456,800,514),"Orden coherente: cobertura del scanner y frontera de bootstrap -> particion completa -> trace de habituacion -> migraciones por owner -> gates globales -> suite backend -> revision independiente.",10,NAVY,True)

    # 3 - Snapshot.
    p=r.page("Snapshot y alcance de la auditoria", "02 / ESTADO Y EVIDENCIA")
    rows=[
      ("Repo / branch","BAGO / fix/spbe-runtime-fix1-20260927"),
      ("HEAD local","758790bb9681dd81e956625fb6f14f46a6abef28"),
      ("Version canonica","4.11.1 (release_version.txt)"),
      ("Estado remoto","PR #236: origin 3cdeadfe; merge local incluido; 4 commits locales por publicar"),
      ("Inventario","4.491 total | 4.129 unbound | 264 runtime-unbound | 2.568 high-confidence unbound"),
      ("Clasificacion","0 scope-unclassified | 0 binding-unclassified | strict-classification exit 0"),
      ("Runtime gate","strict-runtime exit 1; 264 runtime-unbound"),
      ("Suite informada","1.670 passed, 16 skipped, 213 subtests; SHA 9633118, evidencia historica"),
    ]
    y=104
    for i,(k,v) in enumerate(rows):
        fill=WHITE if i%2==0 else (0.94,0.96,0.98)
        p.draw_rect(fitz.Rect(42,y,800,y+43),color=None,fill=fill,overlay=True)
        r.text(p,(55,y+12,220,y+32),k,9,BLUE,True)
        r.text(p,(232,y+9,785,y+35),v,9,INK,False)
        y+=44
    r.card(p,42,458,758,78,"Limite de interpretacion",
           "El scan se ejecuto sobre el worktree limpio 758790bb. Scanner SHA AB436A4D7484D18CDB56600DA517305ECA1ABFD2FC722B444D02D929649D2F71; registry v1.24.0 SHA AB1EDAD052F705AE01092B120858C876CE1EC760E88875BEB89B37D55FD61F30. Los docs actualizados y el informe se publican despues de esta fotografia.",AMBER,PALE_AMBER,body_size=8.2)

    # 4 - Mental map.
    p=r.page("Mapa mental de BAGO", "03 / ARQUITECTURA")
    p.draw_rect(fitz.Rect(42,105,800,167),color=(0.86,0.89,0.93),fill=WHITE,radius=0.06,overlay=True)
    p.draw_rect(fitz.Rect(42,105,48,167),color=None,fill=CYAN,overlay=True)
    r.text(p,(60,116,780,139),"MAPA CANONICO COMPLETO · 12 RAMAS · 107 NODOS",12,NAVY,True)
    r.text(p,(60,143,780,160),"Fuente: docs/architecture/bago_mind_map.data.json. Anexo final: ramas completas con jerarquia, estado y detalle.",8.7,MUTED)
    map_data=json.loads(MIND_MAP_DATA.read_text(encoding="utf-8"))
    map_branches=map_data["branches"]
    palette=[(BLUE,PALE_BLUE),(CYAN,PALE_CYAN),(VIOLET,PALE_VIOLET),(GREEN,PALE_GREEN),
             (AMBER,PALE_AMBER),(RED,PALE_RED)]
    col_x=[42,431]
    for i,b in enumerate(map_branches):
        col=i%2; row=i//2; x=col_x[col]; y=184+row*55
        accent,fill=palette[i%len(palette)]
        p.draw_rect(fitz.Rect(x,y,x+369,y+43),color=(0.86,0.89,0.93),fill=fill,radius=0.06,overlay=True)
        p.draw_rect(fitz.Rect(x,y,x+5,y+43),color=None,fill=accent,overlay=True)
        r.text(p,(x+14,y+6,x+352,y+21),b["title"],9.1,NAVY,True)
        r.text(p,(x+14,y+24,x+352,y+38),b["summary"],7.3,INK)
    r.text(p,(42,534,800,553),"El anexo final despliega las 12 ramas; el mapa conserva su estado y no lo sustituye por el veredicto de auditoría.",8.3,MUTED)

    # 4a - Full canonical mind map, one complete branch per page.
    status_colors={"IMPLEMENTADO":GREEN,"ACTIVO":CYAN,"OWNER":BLUE,"PROPOSED":AMBER,
                   "ABIERTO":RED,"EVIDENCIA":VIOLET,"VERIFICADO":GREEN,"PENDIENTE":AMBER}
    def flatten_nodes(nodes, depth=0, parent=""):
        flattened=[]
        for node in nodes:
            title=node.get("title", "(sin titulo)")
            flattened.append((depth,parent,title,node.get("status",""),node.get("detail","")))
            flattened.extend(flatten_nodes(node.get("children",[]),depth+1,title))
        return flattened
    map_body_font=fitz.Font(fontfile=str(FONT))
    def wrapped_line_count(value, width, fontsize):
        if not value:
            return 1
        lines=1; current=""
        for word in value.split():
            candidate=f"{current} {word}".strip()
            if current and map_body_font.text_length(candidate,fontsize=fontsize)>width:
                lines+=1; current=word
            else:
                current=candidate
        return lines
    map_appendix_start=len(r.doc)
    for branch_no,branch in enumerate(map_branches,1):
        accent,fill=palette[(branch_no-1)%len(palette)]
        nodes=flatten_nodes(branch.get("children",[]))
        chunks=[nodes[i:i+8] for i in range(0,len(nodes),8)] or [[]]
        for part_no,chunk in enumerate(chunks,1):
            title=branch["title"] if len(chunks)==1 else f"{branch['title']} · parte {part_no}/{len(chunks)}"
            p=r.page(title,f"04 / MAPA COMPLETO · RAMA {branch_no:02d} DE {len(map_branches):02d}")
            r.text(p,(42,101,800,124),branch.get("summary",""),10,accent,True)
            p.draw_line((42,132),(800,132),color=(0.86,0.89,0.93),width=0.8,overlay=True)
            mid=(len(chunk)+1)//2
            columns=[chunk[:mid],chunk[mid:]]
            for ci,items in enumerate(columns):
                x=42 if ci==0 else 431; y=146
                for depth,parent,node_title,status,detail in items:
                    indent=min(depth*10,28)
                    body=detail or (f"Subnodo de {parent}." if parent else "")
                    title_x=x+10+indent
                    title_right=x+354
                    body_size=6.9
                    lines=wrapped_line_count(body,title_right-title_x,body_size)
                    h=max(43,34+lines*8)
                    if y+h>530:
                        raise ValueError(f"Mind-map branch overflow: {branch['title']} column {ci+1}")
                    p.draw_rect(fitz.Rect(x+indent,y,x+369,y+h),color=(0.88,0.90,0.93),fill=WHITE,radius=0.05,overlay=True)
                    p.draw_rect(fitz.Rect(x+indent,y,x+3+indent,y+h),color=None,fill=accent,overlay=True)
                    title_size=8.0 if len(node_title)<37 else 7.3
                    r.text(p,(title_x,y+5,title_right,y+17),node_title,title_size,NAVY,True)
                    if status:
                        status_color=status_colors.get(status.upper(),accent)
                        r.text(p,(title_x,y+19,title_right,y+29),status.upper(),6.2,status_color,True)
                        body_y=y+30
                    else:
                        body_y=y+19
                    if body:
                        result=r.text(p,(title_x,body_y,title_right,y+h-4),body,body_size,INK,lineheight=1.0)
                        if result<0:
                            raise ValueError(f"Mind-map detail overflow: {branch['title']} / {node_title}")
                    y+=h+5
            r.text(p,(42,536,800,554),"Fuente canónica: docs/architecture/bago_mind_map.data.json · Estado del nodo conservado tal como está declarado.",7.2,MUTED)
    map_appendix_pages=len(r.doc)-map_appendix_start

    # 5 - Code topology.
    p=r.page("Arbol de codigo y ownership", "04 / AUDITORIA DE CODIGO")
    r.card(p,42,103,369,222,"Backend",
           "backend/bago_core/\n  CLI, launcher, claims, release y evidencia\n\nbackend/.bago/core/\n  SessionManager, contexto, providers y runtime\n\nbackend/.bago/api/\n  bridge HTTP y handlers\n\nbackend/docs + contracts + tests\n  contratos, evidencia, pruebas y guias",
           BLUE,PALE_BLUE,body_size=10)
    r.card(p,431,103,369,222,"Superficies y distribucion",
           "frontend/\n  React + TypeScript + Vite\n\nelectron-viewer/ y manager/\n  shell, ciclo de vida y empaquetado\n\nreleases/\n  installers, helpers y versionado\n\n.github/workflows/\n  gates de fuente, build y clean-install",
           CYAN,PALE_CYAN,body_size=10)
    r.card(p,42,343,369,156,"Propiedad de autoridad",
           "Un effect_id debe tener un owner. El caller crea una intencion/request; AuthorizationBoundary evalua; el Permit se consume; ExecutionGateway resuelve el adapter. El sink vive bajo el owner o permanece en el inventario como runtime-unbound.",GREEN,PALE_GREEN)
    r.card(p,431,343,369,156,"Deuda visible en el corte",
           "Hay dos zonas de codigo con aspecto de core (bago_core y .bago/core), wrappers e imports historicos. Reducir duplicidad debe preservar una sola autoridad, contratos y rutas de ejecucion; mover archivos no es por si mismo una reparacion.",AMBER,PALE_AMBER)

    # 6 - Context and memory.
    p=r.page("Contexto y memoria: estado y limite", "05 / CONTEXTO")
    r.card(p,42,103,244,166,"Sesion y continuidad",
           "La sesion mantiene identidad, conversaciones, provider/modelo y workspace. SessionManager y ContextStore son las piezas de continuidad; el modelo es un motor reemplazable.",BLUE,PALE_BLUE)
    r.card(p,299,103,244,166,"Conocimiento persistente",
           "KnowledgeBase usa SQLite/FTS5 y EmbeddingStore aporta embeddings. El adapter database.write registrado por Gateway posee estas escrituras. SessionDB fue retirado como indice duplicado de la sesion JSON canonica.",CYAN,PALE_CYAN)
    r.card(p,556,103,244,166,"RL y aprendizaje",
           "La documentacion del producto declara RL shadow/off y fuera del MVP estable. Observacion o feedback no debe subir confianza, permisos o ejecucion sin una politica y evidencia explicitas.",VIOLET,PALE_VIOLET)
    r.card(p,42,288,371,194,"Brecha a cerrar en Contexto y memoria",
           "La existencia de stores no demuestra por si sola que todas las rutas de CLI/API/UI respeten la misma autoridad. Deben revisarse: persistencia de sesion, memoria, historial, cache, RL, decisiones previas, retry y rehidratacion.\n\nTrace requerido: estado historico -> decision -> seleccion de ruta/modelo/herramienta -> autorizacion vigente -> efecto -> resultado reincorporado al historial.",AMBER,PALE_AMBER)
    r.card(p,428,288,372,194,"No mezclar memoria con autoridad",
           "Contexto recuperado puede orientar la respuesta, pero no es un Permit. Prior success, confidence, reputation, cached approval y un resultado anterior no autorizan un efecto actual. Cada ejecucion debe volver a ligar operacion, sesion, recurso y policy version.",RED,PALE_RED)

    # 7 - semantic tool/model eligibility.
    p=r.page("Modelos y herramientas: elegibilidad semantica", "06 / ROUTING")
    columns=[
        (42, BLUE, "SELECCION SEMANTICA", [
            ("1  INTENCION", "Que resultado pide el usuario."),
            ("2  OPERACION", "Que accion y recurso hacen falta."),
            ("3  MATCH", "Capacidades y restricciones compatibles."),
            ("4  ELEGIBLE", "Candidato valido para esta tarea."),
        ]),
        (431, VIOLET, "AUTORIZACION Y EJECUCION", [
            ("5  AUTHORIZATION", "Decision vigente para la operacion."),
            ("6  PERMIT", "Sesion, recurso y operacion ligados."),
            ("7  GATEWAY", "Owner resuelto por el servidor."),
            ("8  EFFECT + RECEIPT", "Efecto material y resultado trazable."),
        ]),
    ]
    for x, accent, heading, items in columns:
        p.draw_rect(fitz.Rect(x, 103, x + 369, 134), color=None, fill=accent,
                    radius=0.08, overlay=True)
        r.text(p, (x + 12, 112, x + 357, 129), heading, 8.3, WHITE, True, align=1)
        y = 143
        for index, (label, desc) in enumerate(items):
            p.draw_rect(fitz.Rect(x, y, x + 369, y + 36),
                        color=(0.87, 0.90, 0.94), fill=WHITE, radius=0.06, overlay=True)
            p.draw_rect(fitz.Rect(x, y, x + 5, y + 36), color=None, fill=accent, overlay=True)
            r.text(p, (x + 15, y + 5, x + 145, y + 30), label, 7.4, accent, True)
            r.text(p, (x + 151, y + 5, x + 357, y + 30), desc, 7.6, INK)
            if index < len(items) - 1:
                connector_x = x + 184
                p.draw_line((connector_x, y + 36), (connector_x, y + 43),
                            color=(0.67, 0.73, 0.81), width=1.0, overlay=True)
            y += 43
    r.card(p,42,337,369,132,"Cuatro estados distintos",
           "CAPABLE: sabe ejecutar una clase de trabajo.\nELIGIBLE: encaja con la operacion, el recurso, los requisitos y las restricciones.\nAUTHORIZED: existe autoridad actual y ligada a esta operacion.\nEXECUTABLE: la capacidad, elegibilidad, autorizacion, runtime y precondiciones coinciden.",VIOLET,PALE_VIOLET,body_size=9.5)
    r.card(p,431,337,369,132,"Equidad entre herramientas/modelos",
           "Una puntuacion acumulada puede premiar al primer candidato usado y contaminarse por historial, aprobacion previa o resultados. Las comparaciones requieren presupuesto/criterios equivalentes, pruebas por combinacion modelo-herramienta y evaluaciones genericas separadas de pruebas por tarea.",BLUE,PALE_BLUE,body_size=9.5)
    r.card(p,42,477,758,71,"Regla de seguridad",
           "La mejor puntuacion o el historial de exito puede seleccionar un candidato, nunca conceder permiso. Seleccion semantica precede autorizacion; la autorizacion se recalcula para el recurso y la operacion actuales.",RED,PALE_RED,body_size=8.2)

    # 8 - Gateway and effects.
    p=r.page("Frontera de ejecucion material", "07 / SEGURIDAD")
    flow=[
      ("1  REQUEST", "effect_id + operacion + recurso", BLUE),
      ("2  CHALLENGE", "identidad de usuario y sesion", VIOLET),
      ("3  PERMIT", "policy + decision actual + consumo", AMBER),
      ("4  GATEWAY", "resuelve el adapter server-owned", CYAN),
      ("5  ADAPTER", "revalida y bloquea antes del efecto", GREEN),
      ("6  RECEIPT", "resultado e identidad trazables", NAVY),
    ]
    y=106
    for label,desc,col in flow:
        p.draw_rect(fitz.Rect(54,y,242,y+47),color=None,fill=col,radius=0.08,overlay=True)
        r.text(p,(64,y+15,232,y+34),label,8.4,WHITE,True,align=1)
        r.text(p,(265,y+15,666,y+34),desc,10,INK,True)
        if y<395:
            p.draw_line((148,y+48),(148,y+60),color=(0.69,0.75,0.83),width=1.1)
        y+=61
    r.card(p,560,452,240,74,"Invariante",
           "El nombre de una herramienta no es permiso. El caller no elige el executor autorizado.",RED,PALE_RED,body_size=8.2)

    # 9 - Installer P0.
    p=r.page("P0 confirmado: instalador de maquina limpia", "08 / INSTALACION")
    chain=[("NSIS", "staging temporal", AMBER), ("PowerShell", "helper sin ticket", RED), ("EXTRACT / COPY", "primer efecto", RED), ("REGISTRY / SHORTCUTS", "efectos NSIS", RED)]
    x=43
    for i,(a,b,col) in enumerate(chain):
        p.draw_rect(fitz.Rect(x,109,x+174,173),color=None,fill=(PALE_AMBER if col==AMBER else PALE_RED),radius=0.08,overlay=True)
        r.text(p,(x+9,122,x+165,143),a,8.4,col,True,align=1)
        r.text(p,(x+9,148,x+165,164),b,7.8,INK,False,align=1)
        if i<len(chain)-1:
            p.draw_line((x+176,141),(x+195,141),color=RED,width=1.8,overlay=True)
        x+=196
    r.card(p,43,196,369,191,"Por que es P0",
           "La ruta normal del instalador extrae y modifica destino, registro y accesos antes de SessionManager, AuthorizationBoundary, Permit consumido o ExecutionGateway. El bypass aparece al ejecutar setup; no exige modificar inputs.\n\nAlcance: bypass de autoridad probado. No equivale a prueba de elevacion remota; NSIS configura nivel de usuario.",RED,PALE_RED)
    r.card(p,431,196,369,191,"Owner existente y limite",
           "system.install.apply es el owner material correcto para instalar, pero el flujo NSIS no tiene host de autoridad antes del primer efecto. install-v4 y SystemInstallEffectAdapter ya exigen sesion, Permit y ticket; su garantia no se transfiere al helper embebido.",GREEN,PALE_GREEN)
    r.card(p,43,405,757,104,"Decision necesaria para reparar",
           "Conservar los owners canonicos system.install.apply, system.install.rollback y system.install.uninstall. Definir el host de bootstrap, su procedencia confiable, el handoff pre-efecto y la identidad ampliada del plan. El contrato bootstrap v1 aun es PROPOSED; su texto necesita corregir conflicto de ownership y el modelo de staging NSIS.",AMBER,PALE_AMBER)

    # 10 - inventory.
    p=r.page("Inventario y compresion pendiente", "09 / SINKS")
    bars=[("filesystem.write",2937,AMBER),("process.execute",588,BLUE),("filesystem.delete",442,RED),("network.read",181,CYAN),("state.write",95,GREEN),("system.configuration.write",31,VIOLET)]
    maxv=2937; y=111
    for label,val,col in bars:
        r.text(p,(50,y+2,224,y+22),label,8.7,INK,True)
        width=410*val/maxv
        p.draw_rect(fitz.Rect(232,y,232+width,y+19),color=None,fill=col,radius=0.08,overlay=True)
        r.text(p,(657,y+2,720,y+21),str(val),8.5,INK,True)
        y+=42
    r.card(p,42,382,368,123,"Conteos actuales",
      "4.491 findings totales\n4.129 unbound en el inventario\n264 runtime-unbound\n0 scope/binding sin clasificar\nstrict-runtime: FAIL",
           BLUE,PALE_BLUE)
    r.card(p,428,382,372,123,"Compresion todavia no cerrada",
           "El numero de sinks no es el numero de reparaciones. Falta demostrar el mapa completo: sinks -> callsites -> causas raiz -> clusters -> owners -> lanes. No asignar clusters finales con un scanner que omite una forma de efecto NSIS.",AMBER,PALE_AMBER)

    # 11 - scanner coverage and test evidence.
    p=r.page("Cobertura, pruebas y evidencia", "10 / VALIDACION")
    r.card(p,42,106,369,155,"Gate que pasa",
           "--strict-classification\n4.491 findings en este scan\n0 scope-unclassified\n0 binding-unclassified\nexit 0",
           GREEN,PALE_GREEN,tag="PASS ACOTADO")
    r.card(p,431,106,369,155,"Gate que falla",
           "--strict-runtime\n264 runtime-unbound\nexit 1\nCierre global: NO",
           RED,PALE_RED,tag="OPEN")
    r.card(p,42,279,369,174,"Grieta del scanner",
           "El trace del NSIS observa InitPluginsDir antes de establecer el output del payload. Los patrones actuales cubren otros comandos de output/Exec/registry/delete pero omiten ese sink previo. La cobertura completa del inventario no esta demostrada; mantener visible y ampliar deteccion.",AMBER,PALE_AMBER)
    r.card(p,431,279,369,174,"Suite backend aportada",
           "1.670 passed, 16 skipped, 213 subtests en 301.17 s. La ejecucion corresponde al SHA remoto 9633118. El arbol actual 758790bb integra main y nueve commits remotos posteriores; repetir la suite sobre el candidato final. No se consultaron los checks actuales por un fallo de red de GitHub CLI.",VIOLET,PALE_VIOLET)
    r.text(p,(42,477,800,516),"Receipts de system.install.apply y logs de la suite son pruebas del flujo de CI del SHA anterior. No demuestran que el P0 NSIS este cerrado ni que strict-runtime pase.",8.7,NAVY,True)

    # 12 - code audit findings.
    p=r.page("Auditoria del codigo: sintesis", "11 / HALLAZGOS")
    r.card(p,42,105,369,176,"Fortalezas verificadas",
           "- Contratos de autorizacion y efectos registrados.\n- Gateway consume Permit antes del adapter.\n- Adapters de instalacion revalidan plan y ticket.\n- Session-first y UI sin autoridad propia en la arquitectura declarada.\n- Suite backend amplia y clean-install gobernado en CI.",GREEN,PALE_GREEN)
    r.card(p,431,105,369,176,"Brechas que mandan el orden",
           "- P0 NSIS antes del primer efecto.\n- Hueco de cobertura scanner (InitPluginsDir).\n- 264 runtime-unbound en 90 archivos segun partition anterior; recapturar callsites sobre snapshot actual.\n- Contrato bootstrap propuesto con conflicto de owners.\n- Suite/remoto/revision no ligados aun al worktree local posterior al merge.",RED,PALE_RED)
    r.card(p,42,299,758,148,"Lectura arquitectonica",
           "La presencia de un ExecutionGateway y de adapters no convierte automaticamente todas las escrituras del producto en efectos gobernados. La frontera se prueba por ruta efectiva: caller que decide -> identidad y autorizacion -> dispatch -> adapter -> sink material -> receipt. El scanner ayuda a descubrir; no sustituye el trace de cobertura ni ownership.",BLUE,PALE_BLUE)
    r.text(p,(42,469,800,510),"No se propone eliminar findings por exclusions, lowering de confianza o movimiento de codigo. Resolver por ownership material y conservar los sinks visibles.",9,INK,True)

    # 13 - MarcValls ecosystem.
    p=r.page("Ecosistema MarcValls: mapa de fronteras", "12 / ECOSISTEMA")
    ecosystem=[
      ("bago-framework / BAG4.8","Linaje historico y snapshots","Archivo de referencia; no importar autoridad ni version a BAGO actual.",BLUE),
      ("bago-knowledge","Conocimiento versionable","KnowledgeProvider/pack externo; runtime de sesion conserva su estado propio.",CYAN),
      ("PANEL_ORQUESTADOR","Cliente y UX de proyectos","Consumir API estable; no crear otro SessionManager ni executor.",VIOLET),
      ("BAGO_NEURAL_FABRIC / IALAP","Experimentos de routing/evidencia","Transferir ideas y evaluaciones; no alojar un segundo motor de permisos/routing.",AMBER),
      ("MUSIC / SPRITE / WALLET","Capacidades de dominio","Plugins/servicios con contratos de capability, scope y permisos.",GREEN),
      ("TELEGRAM_BOT","Interfaz remota","Cliente API autenticado; no un tunel generico a comandos sensibles.",RED),
    ]
    y=103
    for name,role,rule,col in ecosystem:
        p.draw_rect(fitz.Rect(42,y,800,y+61),color=(0.88,0.90,0.93),fill=WHITE,radius=0.08,overlay=True)
        p.draw_rect(fitz.Rect(42,y,48,y+61),color=None,fill=col,overlay=True)
        r.text(p,(59,y+8,230,y+26),name,8.5,NAVY,True)
        r.text(p,(240,y+8,419,y+26),role,8.1,col,True)
        r.text(p,(430,y+7,787,y+52),rule,8,INK)
        y+=68
    r.text(p,(42,521,800,546),"Los estados actuales de esos repositorios no se volvieron a auditar desde este checkout. Esta comparacion es de fronteras y roles, no un inventario remoto vigente.",8.1,MUTED)

    # 14 - external comparison.
    p=r.page("Comparacion con herramientas abiertas", "13 / ECOSISTEMA")
    comps=[
      ("Aider","Mapa de repositorio de simbolos, contexto optimizado por ranking, edicion en terminal y flujo Git.","BAGO complementa repo understanding con estado de sesion, contexto persistente y owner de efectos.",BLUE),
      ("Continue","Modelos, reglas versionadas en workspace y herramientas MCP configurables.","Buen referente de configuracion y reglas locales; BAGO debe aportar identidad/autoridad de operacion.",CYAN),
      ("OpenHands","SDK/runtime para agentes de software, experiencias web/CLI y ejecucion aislada.","Referencia para runtimes componibles y aislamiento de ejecucion; comparar con limites y despliegues concretos.",VIOLET),
      ("Open Interpreter","CLI con sesiones, herramientas, sandbox y policies/approval seleccionables.","Referencia para harness local y multi-provider; distinguir sandbox/approval del ownership BAGO del efecto.",AMBER),
    ]
    y=105
    for name,what,diff,col in comps:
        r.card(p,42,y,758,79,name,what+"\nLectura para BAGO: "+diff,col,WHITE,body_size=8.3)
        y+=90
    r.text(p,(42,486,800,528),"No son equivalentes directos: Aider optimiza pair-programming con repo map; Continue configura modelos/reglas/tools; OpenHands organiza software agents y runtimes; Open Interpreter ofrece un coding-agent CLI con sandbox y aprobaciones. El rasgo a preservar en BAGO es la autoridad de sesion independiente del provider.",8.4,NAVY)

    # 15 - roadmap.
    p=r.page("Orden de cierre gobernado", "14 / PLAN")
    waves=[
      ("WAVE 0", "Cerrar cobertura del scanner y repetir snapshot HEAD + worktree fingerprint. No particionar globalmente sobre cobertura parcial.", RED),
      ("WAVE 1", "Bootstrap installer: fijar host de confianza, primer efecto, staging, identidad/target, policy version y ownership apply/rollback/uninstall.", AMBER),
      ("WAVE 2", "Trace de habituacion: history, memory, RL, confidence, approval cache, retry y resultado que reingresa al historial.", VIOLET),
      ("WAVE 3", "Particion por causa y owner: REUSE -> EXTEND -> NEW_OWNER; probar todos los sinks y mantener registry/shared security tests serializados.", BLUE),
      ("WAVE 4", "Strict classification + strict runtime; suite backend completa; CI limpio y revision independiente sobre el mismo SHA comiteado.", GREEN),
    ]
    y=105
    for label,body,col in waves:
        r.pill(p,52,y+7,label,col,78)
        r.text(p,(149,y+4,790,y+48),body,9,INK)
        if y<430:
            p.draw_line((90,y+31),(90,y+60),color=(0.74,0.79,0.85),width=1.1)
        y+=78
    r.card(p,42,492,758,66,"Paralelismo",
           "Solo trabajo local no solapado puede correr en paralelo. Registry, ExecutionGateway, AuthorizationBoundary, claims y contratos de seguridad son puntos de integracion serializados.",BLUE,PALE_BLUE,body_size=8.2)

    # 16 - decision record and references.
    p=r.page("Conclusiones y referencias", "15 / CIERRE")
    r.card(p,42,103,369,145,"Conclusion",
           "BAGO ya tiene una tesis clara: sesion duradera, providers intercambiables y efectos con autoridad/receipts. La implementacion todavia no demuestra unicidad global: hay 264 runtime-unbound, un P0 en NSIS y un hueco de scanner.",RED,PALE_RED)
    r.card(p,431,103,369,145,"Estado correcto",
           "STRICT CLASSIFICATION: PASS para findings detectados.\nSTRICT RUNTIME: FAIL.\nPARTITION: incompleta por cobertura scanner.\nGLOBAL CLOSE: NO.\nPDF: fotografia informativa, no gate receipt.",AMBER,PALE_AMBER)
    refs=(
      "Evidencia local: HEAD 758790bb; release_version.txt; backend/.bago/tools/effect_sink_inventory.py; "
      "backend/.bago/contracts/bago.effect-registry.v1.json; releases/bago-installer.nsi; "
      "releases/install-embedded-payload.ps1; backend/.bago/core/execution_gateway.py; "
      "backend/.bago/core/execution_adapters/system_install.py; backend/install-v4.ps1; "
      "backend/docs/contracts/bootstrap_authority.v1.md; docs/architecture/bago_mind_map.data.json.\n"
      "Scanner SHA-256 AB436A4D7484D18CDB56600DA517305ECA1ABFD2FC722B444D02D929649D2F71. "
      "Effect registry bago.effect-registry.v1 1.24.0 SHA-256 AB1EDAD052F705AE01092B120858C876CE1EC760E88875BEB89B37D55FD61F30.\n\n"
      "Comparadores: https://github.com/Aider-AI/aider/tree/main/aider/website/docs/repomap.md\n"
      "https://docs.continue.dev/guides/configuring-models-rules-tools\n"
      "https://www.openhands.dev/product/sdk\n"
      "https://www.openinterpreter.com/docs/terminal/cli-reference\n\n"
      "Las paginas oficiales de Aider, Continue, OpenHands y Open Interpreter se consultaron el 2026-09-27. "
      "El PDF fuente aportado se habia basado en un corte 2026-09-02; sus datos de version, PR, CI y releases quedan sustituidos por esta fotografia."
    )
    r.text(p,(52,278,790,489),refs,9,INK,lineheight=1.25)
    r.text(p,(42,520,800,542),"Generado en el checkout BAGO; confirmar el mismo SHA y reejecutar gates antes de citar como evidencia operativa.",8.1,MUTED)
    # Keep the core report pagination stable; the full structured map is an appendix.
    for _ in range(map_appendix_pages):
        r.doc.move_page(map_appendix_start,-1)
    for page_index,page in enumerate(r.doc):
        page.draw_rect(fitz.Rect(PAGE_W-MARGIN-43,PAGE_H-27,PAGE_W-MARGIN+3,PAGE_H-3),
                       color=None,fill=NAVY if page_index==0 else PAPER,overlay=True)
        page.insert_text((PAGE_W-MARGIN-30,PAGE_H-17),f"{page_index+1:02d}",
                         fontname="bold",fontsize=8,color=WHITE if page_index==0 else INK,overlay=True)
    r.save()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha",default="758790bb9681dd81e956625fb6f14f46a6abef28")
    parser.add_argument("--output",type=Path,default=OUTPUT)
    args=parser.parse_args()
    build(args.sha,args.output)
    print(f"WROTE {args.output.relative_to(ROOT) if args.output.is_relative_to(ROOT) else args.output}")
    check=fitz.open(args.output)
    print(f"PAGES {len(check)} BYTES {args.output.stat().st_size}")
    map_data=json.loads(MIND_MAP_DATA.read_text(encoding="utf-8"))
    def titles(nodes):
        values=[]
        for node in nodes:
            values.append(node.get("title",""))
            values.extend(titles(node.get("children",[])))
        return values
    map_titles=titles(map_data["branches"])
    def normalized(value):
        return re.sub(r"[^a-z0-9]", "", value.casefold())
    pdf_text=normalized("\n".join(page.get_text() for page in check))
    missing_titles=[title for title in map_titles if normalized(title) not in pdf_text]
    if missing_titles:
        raise SystemExit(f"mind-map nodes missing from PDF: {missing_titles}")
    print(f"MIND_MAP_NODES {len(map_titles)}")
    print("MIND_MAP_CHECK PASS")
    for i,page in enumerate(check):
        text=page.get_text()
        if len(text.strip())<120:
            raise SystemExit(f"page {i+1} appears empty")
        bounds=page.rect
        for word in page.get_text("words"):
            if word[0] < 0 or word[1] < 0 or word[2] > bounds.width or word[3] > bounds.height:
                raise SystemExit(f"text outside page {i+1}: {word[4]!r}")
        for drawing in page.get_drawings():
            rect=drawing["rect"]
            if rect.x0 < 0 or rect.y0 < 0 or rect.x1 > bounds.width or rect.y1 > bounds.height:
                raise SystemExit(f"graphic outside page {i+1}: {rect}")
    print("TEXT_CHECK PASS")


if __name__=="__main__":
    main()
