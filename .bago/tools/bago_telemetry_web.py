#!/usr/bin/env python3
"""bago_telemetry_web.py — Dashboard web de telemetría BAGO.

Servidor HTTP local, zero dependencias externas.
Funciona desde cualquier contexto: OpenClaw, CI, sin TTY.

Uso:
    python3 bago_telemetry_web.py             # puerto auto, abre browser
    python3 bago_telemetry_web.py --port 7788 # puerto fijo
    python3 bago_telemetry_web.py --no-open   # no abre browser
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

_xdg = os.environ.get("XDG_DATA_HOME")
TELEMETRY_DIR: Path = (
    (Path(_xdg) / "bago" / "telemetry") if _xdg
    else (Path.home() / ".bago" / "telemetry")
)
EVENTS_FILE = TELEMETRY_DIR / "events.jsonl"

# ── Página HTML completa (autocontenida, sin CDN) ─────────────────────────────

_HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>BAGO Telemetría Live</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0d1117;color:#e6edf3;font:14px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;min-height:100vh}

/* ── topbar FIFO ── */
#fifo{background:#161b22;border-bottom:1px solid #30363d;height:36px;overflow:hidden;
      display:flex;align-items:center;white-space:nowrap;position:sticky;top:0;z-index:10}
#fifo-label{background:#238636;color:#fff;font-weight:700;padding:0 12px;
            height:100%;display:flex;align-items:center;letter-spacing:.5px;flex-shrink:0}
#fifo-track{flex:1;overflow:hidden;height:100%;display:flex;align-items:center;position:relative}
#fifo-inner{display:inline-block;white-space:nowrap;will-change:transform;animation:scroll-left linear infinite}
@keyframes scroll-left{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}

/* ── header ── */
header{background:#161b22;border-bottom:1px solid #30363d;padding:10px 20px;
       display:flex;justify-content:space-between;align-items:center;gap:12px}
h1{font-size:16px;font-weight:700;color:#58a6ff}
#status{font-size:12px;color:#8b949e}
#refresh-badge{background:#21262d;border:1px solid #30363d;border-radius:6px;
               padding:3px 10px;font-size:11px;color:#8b949e;cursor:pointer;user-select:none}
#refresh-badge:hover{background:#30363d;color:#e6edf3}

/* ── nav tabs ── */
nav{background:#161b22;border-bottom:1px solid #30363d;display:flex;gap:2px;padding:0 16px}
.tab{padding:8px 18px;cursor:pointer;border-bottom:2px solid transparent;color:#8b949e;
     font-size:13px;transition:.15s}
.tab:hover{color:#e6edf3}
.tab.active{color:#58a6ff;border-color:#58a6ff}

/* ── views ── */
main{padding:20px;max-width:1400px;margin:0 auto}
.view{display:none}.view.active{display:block}

/* ── cards de resumen ── */
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:20px}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px 16px}
.card-val{font-size:28px;font-weight:700;line-height:1}
.card-lbl{font-size:11px;color:#8b949e;margin-top:4px}
.card-ok .card-val{color:#3fb950}
.card-fail .card-val{color:#f85149}
.card-info .card-val{color:#58a6ff}
.card-warn .card-val{color:#d29922}

/* ── tabla de comandos ── */
.table-wrap{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;padding:8px 12px;border-bottom:2px solid #30363d;color:#8b949e;
   font-size:11px;letter-spacing:.5px;text-transform:uppercase}
td{padding:7px 12px;border-bottom:1px solid #21262d}
tr:hover td{background:#161b22}
.bar-cell{min-width:120px}
.bar{height:10px;background:#1f6feb;border-radius:3px;transition:width .3s}
.bar-fail{background:#f85149}
.num-ok{color:#3fb950;font-weight:600}
.num-fail{color:#f85149;font-weight:600}

/* ── log de eventos ── */
#log-list{list-style:none;display:flex;flex-direction:column;gap:4px}
.log-item{background:#161b22;border:1px solid #21262d;border-radius:6px;
          padding:8px 12px;display:flex;gap:10px;align-items:flex-start;font-size:12px}
.log-icon{font-size:14px;flex-shrink:0;width:20px;text-align:center}
.log-ts{color:#8b949e;flex-shrink:0;width:88px}
.log-name{font-weight:600;flex-shrink:0;width:120px;color:#e6edf3}
.log-meta{color:#8b949e;flex:1}
.log-ok{border-left:3px solid #3fb950}
.log-fail{border-left:3px solid #f85149}
.log-event{border-left:3px solid #d29922}
.log-exc{border-left:3px solid #f85149;background:#1c0c0c}

/* ── error panel ── */
.exc-item{background:#1c0c0c;border:1px solid #491d1d;border-radius:6px;padding:12px 14px;margin-bottom:10px}
.exc-title{color:#f85149;font-weight:700;margin-bottom:6px}
.exc-cmd{color:#8b949e;font-size:12px;margin-bottom:4px}
.exc-msg{color:#e6edf3;margin-bottom:6px}
.exc-tb{background:#0d1117;border:1px solid #30363d;border-radius:4px;padding:8px;
        font-size:11px;color:#8b949e;white-space:pre-wrap;max-height:120px;overflow-y:auto}
.empty{color:#8b949e;padding:20px;text-align:center}
</style>
</head>
<body>

<!-- FIFO topbar -->
<div id="fifo">
  <div id="fifo-label">⚡ LIVE</div>
  <div id="fifo-track"><div id="fifo-inner"></div></div>
</div>

<!-- Header -->
<header>
  <div>
    <h1>📊 BAGO Telemetría</h1>
  </div>
  <div style="display:flex;gap:10px;align-items:center">
    <span id="status">cargando…</span>
    <span id="refresh-badge" onclick="loadData()" title="Click para refrescar">↻ auto 2s</span>
  </div>
</header>

<!-- Nav -->
<nav>
  <div class="tab active" data-view="dashboard" onclick="setView(this)">Dashboard</div>
  <div class="tab" data-view="stats" onclick="setView(this)">Stats</div>
  <div class="tab" data-view="log" onclick="setView(this)">Log</div>
  <div class="tab" data-view="errors" onclick="setView(this)">Errores</div>
</nav>

<main>

<!-- VIEW: Dashboard -->
<div class="view active" id="view-dashboard">
  <div class="cards" id="cards"></div>
  <div class="table-wrap"><table id="cmd-table">
    <thead><tr>
      <th>Comando</th><th>Barra</th><th>OK</th><th>Fail</th><th>Total</th>
      <th>Avg (s)</th><th>Max (s)</th>
    </tr></thead>
    <tbody id="cmd-body"></tbody>
  </table></div>
</div>

<!-- VIEW: Stats -->
<div class="view" id="view-stats">
  <div class="table-wrap"><table>
    <thead><tr>
      <th>Comando</th><th>OK</th><th>Fail</th><th>Total</th>
      <th>Avg (s)</th><th>Min (s)</th><th>Max (s)</th><th>P95 (s)</th>
    </tr></thead>
    <tbody id="stats-body"></tbody>
  </table></div>
</div>

<!-- VIEW: Log -->
<div class="view" id="view-log">
  <ul id="log-list"></ul>
</div>

<!-- VIEW: Errors -->
<div class="view" id="view-errors">
  <div id="errors-list"></div>
</div>

</main>

<script>
let _events = [];

// ── Fetch ──────────────────────────────────────────────────────────────────
async function loadData() {
  try {
    const r = await fetch('/api/events');
    if (!r.ok) throw new Error(r.status);
    _events = await r.json();
    render(_events);
    document.getElementById('status').textContent =
      new Date().toLocaleTimeString() + ' · ' + _events.length + ' registros';
  } catch(e) {
    document.getElementById('status').textContent = '⚠ error: ' + e;
  }
}

// ── Helpers ────────────────────────────────────────────────────────────────
function fmtTs(ts) {
  return ts ? ts.slice(0,19).replace('T',' ') : '?';
}
function avg(arr) { return arr.length ? arr.reduce((a,b)=>a+b,0)/arr.length : null; }
function p95(arr) {
  if (!arr.length) return null;
  const s = [...arr].sort((a,b)=>a-b);
  return s[Math.floor(s.length*0.95)];
}

// ── Render principal ───────────────────────────────────────────────────────
function render(events) {
  const cmds    = events.filter(e=>e.type==='command');
  const errors  = events.filter(e=>e.type==='exception');
  const custom  = events.filter(e=>e.type==='event');
  const metrics = events.filter(e=>e.type==='metric');

  const ok   = cmds.filter(e=>e.properties?.success===true).length;
  const fail = cmds.filter(e=>e.properties?.success===false).length;

  // ── Cards ──
  document.getElementById('cards').innerHTML = [
    {val: cmds.length,    lbl:'Comandos',  cls:'card-info'},
    {val: ok,             lbl:'✅ Exitosos', cls:'card-ok'},
    {val: fail,           lbl:'❌ Fallidos', cls:'card-fail'},
    {val: errors.length,  lbl:'💥 Excepciones', cls: errors.length?'card-fail':'card-ok'},
    {val: custom.length,  lbl:'◆ Eventos',  cls:'card-info'},
    {val: metrics.length, lbl:'📈 Métricas', cls:'card-warn'},
    {val: events.length,  lbl:'Total',      cls:'card-info'},
  ].map(c=>`<div class="card ${c.cls}">
    <div class="card-val">${c.val}</div>
    <div class="card-lbl">${c.lbl}</div>
  </div>`).join('');

  // ── Command stats ──
  const cmdMap = {};
  cmds.forEach(e=>{
    const n = e.name||'?';
    if (!cmdMap[n]) cmdMap[n]={ok:0,fail:0,durs:[]};
    if (e.properties?.success===true)  cmdMap[n].ok++;
    if (e.properties?.success===false) cmdMap[n].fail++;
    const d = e.metrics?.duration_s;
    if (d!=null) cmdMap[n].durs.push(d);
  });
  const cmdEntries = Object.entries(cmdMap).sort((a,b)=>
    (b[1].ok+b[1].fail)-(a[1].ok+a[1].fail));
  const maxTotal = cmdEntries.length ? (cmdEntries[0][1].ok+cmdEntries[0][1].fail) : 1;

  // Dashboard table
  document.getElementById('cmd-body').innerHTML = cmdEntries.map(([name,d])=>{
    const total  = d.ok + d.fail;
    const a      = avg(d.durs);
    const m      = d.durs.length ? Math.max(...d.durs) : null;
    const pct    = Math.round(total/maxTotal*100);
    const barCls = d.fail ? 'bar bar-fail' : 'bar';
    return `<tr>
      <td><strong>${name}</strong></td>
      <td class="bar-cell"><div class="${barCls}" style="width:${pct}%"></div></td>
      <td class="num-ok">${d.ok}</td>
      <td class="num-fail">${d.fail||''}</td>
      <td>${total}</td>
      <td>${a!=null?a.toFixed(2):'—'}</td>
      <td>${m!=null?m.toFixed(2):'—'}</td>
    </tr>`;
  }).join('') || '<tr><td colspan="7" class="empty">Sin datos</td></tr>';

  // Stats table (with P95)
  document.getElementById('stats-body').innerHTML = cmdEntries.map(([name,d])=>{
    const total = d.ok + d.fail;
    const a     = avg(d.durs);
    const mn    = d.durs.length ? Math.min(...d.durs) : null;
    const mx    = d.durs.length ? Math.max(...d.durs) : null;
    const p     = p95(d.durs);
    return `<tr>
      <td><strong>${name}</strong></td>
      <td class="num-ok">${d.ok}</td>
      <td class="num-fail">${d.fail||0}</td>
      <td>${total}</td>
      <td>${a!=null?a.toFixed(3):'—'}</td>
      <td>${mn!=null?mn.toFixed(3):'—'}</td>
      <td>${mx!=null?mx.toFixed(3):'—'}</td>
      <td>${p!=null?p.toFixed(3):'—'}</td>
    </tr>`;
  }).join('') || '<tr><td colspan="8" class="empty">Sin datos</td></tr>';

  // Event log (últimos 100, más recientes primero)
  const allSorted = [...events].sort((a,b)=>b.ts?.localeCompare(a.ts||'')||0).slice(0,100);
  document.getElementById('log-list').innerHTML = allSorted.map(e=>{
    const t = e.type;
    const s = e.properties?.success;
    let cls='', icon='·';
    if (t==='exception') { cls='log-exc'; icon='💥'; }
    else if (s===true)   { cls='log-ok';  icon='✓'; }
    else if (s===false)  { cls='log-fail'; icon='✗'; }
    else if (t==='event'){ cls='log-event'; icon='◆'; }
    const dur = e.metrics?.duration_s;
    const durS = dur!=null ? ` · ${dur.toFixed(2)}s` : '';
    const args = e.properties?.args?.join(' ') || '';
    return `<li class="log-item ${cls}">
      <span class="log-icon">${icon}</span>
      <span class="log-ts">${fmtTs(e.ts).slice(11)}</span>
      <span class="log-name">${e.name||'?'}</span>
      <span class="log-meta">${t}${durS}${args?' · '+args:''}</span>
    </li>`;
  }).join('') || '<li class="empty">Sin eventos</li>';

  // Errors
  document.getElementById('errors-list').innerHTML = errors.length
    ? errors.slice().reverse().slice(0,20).map(e=>{
        const p = e.properties||{};
        const tbLines = (p.traceback||'').split('\n')
          .filter(l=>l.includes('File ')).slice(-3).join('\n');
        return `<div class="exc-item">
          <div class="exc-title">💥 ${e.name||'?'}</div>
          <div class="exc-cmd">cmd: ${p.command||'?'}  ·  ${fmtTs(e.ts)}</div>
          <div class="exc-msg">${p.message||''}</div>
          ${tbLines?`<pre class="exc-tb">${tbLines}</pre>`:''}
        </div>`;
      }).join('')
    : '<div class="empty">✅ Sin excepciones registradas</div>';

  // FIFO ticker
  renderFifo(events);
}

// ── FIFO ticker ─────────────────────────────────────────────────────────────
function renderFifo(events) {
  const all = [...events].sort((a,b)=>(a.ts||'').localeCompare(b.ts||''));
  const tokens = all.slice(-80).map(e=>{
    const s = e.properties?.success;
    const d = e.metrics?.duration_s;
    const dur = d!=null?` ${d.toFixed(2)}s`:'';
    let icon = '·';
    if (e.type==='exception') icon='💥';
    else if (s===true)        icon='✓';
    else if (s===false)       icon='✗';
    else if (e.type==='event') icon='◆';
    const ts = (e.ts||'').slice(11,19);
    return `<span style="margin:0 6px">${icon} <strong>${e.name||'?'}</strong>${dur}</span><span style="opacity:.3">·</span>`;
  }).join('  ');

  // Duplicar para scroll infinito
  const inner = document.getElementById('fifo-inner');
  const content = tokens + '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;' + tokens;
  inner.innerHTML = content;

  // Calcular duración de animación (velocidad constante: ~60px/s)
  const w = inner.scrollWidth / 2;
  const duration = Math.max(8, w / 80);
  inner.style.animationDuration = duration + 's';
}

// ── Tabs ───────────────────────────────────────────────────────────────────
function setView(tab) {
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.view').forEach(v=>v.classList.remove('active'));
  tab.classList.add('active');
  document.getElementById('view-'+tab.dataset.view).classList.add('active');
}

// ── Auto-refresh ───────────────────────────────────────────────────────────
loadData();
setInterval(loadData, 2000);
</script>
</body>
</html>"""


# ── Servidor HTTP ─────────────────────────────────────────────────────────────

def _load_events() -> list[dict]:
    if not EVENTS_FILE.exists():
        return []
    events: list[dict] = []
    try:
        with EVENTS_FILE.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    except OSError:
        pass
    return events


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # silenciar logs de acceso
        pass

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            body = _HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

        elif self.path == "/api/events":
            body = json.dumps(_load_events(), ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

        elif self.path == "/api/ping":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        else:
            self.send_response(404)
            self.end_headers()


def _find_free_port(preferred: int = 7799) -> int:
    try:
        s = socket.socket()
        s.bind(("127.0.0.1", preferred))
        s.close()
        return preferred
    except OSError:
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        return port


def _open_browser(url: str) -> None:
    """Intenta abrir el browser en macOS/Linux/Windows."""
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", url])
        elif sys.platform.startswith("linux"):
            subprocess.Popen(["xdg-open", url])
        elif sys.platform == "win32":
            subprocess.Popen(["start", url], shell=True)
    except Exception:
        pass


def serve(port: int = 7799, open_browser: bool = True) -> None:
    port = _find_free_port(port)
    url  = f"http://127.0.0.1:{port}"

    server = HTTPServer(("127.0.0.1", port), _Handler)

    print(f"\n  📊 BAGO Telemetría Web")
    print(f"  URL     : {url}")
    print(f"  Datos   : {EVENTS_FILE}")
    print(f"  Refresco: cada 2s (automático en browser)")
    print(f"\n  Ctrl+C para detener\n")

    if open_browser:
        # Pequeña pausa para que el server arranque antes del browser
        threading.Timer(0.4, _open_browser, args=[url]).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Servidor detenido.")
        server.server_close()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    args     = sys.argv[1:]
    port     = 7799
    no_open  = "--no-open" in args

    if "--port" in args:
        idx = args.index("--port")
        if idx + 1 < len(args):
            try:
                port = int(args[idx + 1])
            except ValueError:
                pass

    serve(port=port, open_browser=not no_open)


if __name__ == "__main__":
    main()
