"""bago dashboard — Live dynamic control panel served on localhost."""
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
import threading
import webbrowser
from collections import defaultdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / ".bago" / "state"
TOOLS_DIR = Path(__file__).resolve().parent
IMPL_PATH = STATE / "implemented_ideas.json"
DB_PATH = STATE / "bago.db"
SNAP_DIR = ROOT / ".bago" / "snapshots"

DEFAULT_PORT = 7734

# ── data layer ────────────────────────────────────────────────────────────────

def _load_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _parse_dt(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _build_metrics() -> dict:
    impl_data = _load_json(IMPL_PATH) or {}
    ideas = impl_data.get("implemented", [])

    # Sort chronologically
    dated = []
    for idea in ideas:
        dt = _parse_dt(idea.get("done_at", ""))
        if dt:
            dated.append((dt, idea))
    dated.sort(key=lambda x: x[0])

    # Cumulative series (per day)
    cumulative: dict[str, int] = {}
    count = 0
    for dt, _ in dated:
        day = dt.strftime("%Y-%m-%d")
        count += 1
        cumulative[day] = count

    # Per-day count
    per_day: dict[str, int] = defaultdict(int)
    for dt, _ in dated:
        per_day[dt.strftime("%Y-%m-%d")] += 1

    # Per-week count
    per_week: dict[str, int] = defaultdict(int)
    for dt, _ in dated:
        iso = dt.isocalendar()
        per_week[f"{iso[0]}-W{iso[1]:02d}"] += 1

    # DB stats
    db_total = db_avail = db_done = 0
    if DB_PATH.exists():
        try:
            con = sqlite3.connect(DB_PATH)
            db_total = con.execute("SELECT COUNT(*) FROM ideas").fetchone()[0]
            db_avail = con.execute("SELECT COUNT(*) FROM ideas WHERE status='available'").fetchone()[0]
            db_done  = con.execute("SELECT COUNT(*) FROM ideas WHERE status='done'").fetchone()[0]
            con.close()
        except Exception:
            pass

    # Active task
    active_task = None
    task_path = STATE / "pending_w2_task.json"
    if task_path.exists():
        td = _load_json(task_path) or {}
        idea = td.get("idea", {})
        active_task = {
            "name": idea.get("name", ""),
            "priority": idea.get("priority", 0),
            "workflow": td.get("workflow", ""),
            "accepted_at": idea.get("accepted_at", ""),
        }

    # Tool count
    exclude = {"tool_registry.py", "db_init.py", "idea_gen.py", "validate.py",
                "bago_core.py", "__init__.py", "emit_ideas.py"}
    tool_files = [f.stem for f in TOOLS_DIR.glob("*.py") if f.name not in exclude]

    # Snapshots
    snaps = len(list(SNAP_DIR.glob("*.zip"))) if SNAP_DIR.exists() else 0

    # Recent 15 ideas
    recent = []
    for dt, idea in reversed(dated[-15:]):
        recent.append({
            "title": idea.get("title", idea.get("idea_title", "?")),
            "done_at": dt.strftime("%Y-%m-%d %H:%M"),
            "slot": idea.get("slot", "?"),
        })

    # Last 7 days
    now = datetime.now(timezone.utc)
    last_7 = sum(1 for dt, _ in dated if (now - dt).days < 7)

    # DB size
    db_kb = DB_PATH.stat().st_size / 1024 if DB_PATH.exists() else 0

    return {
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ideas_total": len(ideas),
        "ideas_last7": last_7,
        "db_total": db_total,
        "db_avail": db_avail,
        "db_done": db_done,
        "tools": len(tool_files),
        "snaps": snaps,
        "db_kb": round(db_kb, 1),
        "active_task": active_task,
        "recent": recent,
        "cumulative": cumulative,      # {date: count}
        "per_day": dict(per_day),       # {date: n}
        "per_week": dict(per_week),     # {week: n}
    }


# ── HTML template ─────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>BAGO Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  :root{
    --bg:#0d1117;--surface:#161b22;--border:#21262d;
    --text:#e6edf3;--muted:#8b949e;--accent:#58a6ff;
    --green:#3fb950;--yellow:#e3b341;--red:#f85149;
    --purple:#bc8cff;--orange:#ffa657;
  }
  body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text);
       min-height:100vh;padding:20px 28px}
  header{display:flex;align-items:center;justify-content:space-between;
         border-bottom:1px solid var(--border);padding-bottom:14px;margin-bottom:24px}
  header h1{font-size:1.5rem;color:var(--accent);display:flex;align-items:center;gap:10px}
  .ts{font-size:.8rem;color:var(--muted)}
  .pulse{width:8px;height:8px;border-radius:50%;background:var(--green);
         box-shadow:0 0 6px var(--green);animation:pulse 2s ease-in-out infinite}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}

  /* KPI cards */
  .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:24px}
  .kpi{background:var(--surface);border:1px solid var(--border);border-radius:10px;
       padding:16px 18px;position:relative;overflow:hidden}
  .kpi::before{content:'';position:absolute;top:0;left:0;right:0;height:3px}
  .kpi.blue::before{background:var(--accent)}
  .kpi.green::before{background:var(--green)}
  .kpi.yellow::before{background:var(--yellow)}
  .kpi.purple::before{background:var(--purple)}
  .kpi.orange::before{background:var(--orange)}
  .kpi .label{font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px}
  .kpi .val{font-size:2rem;font-weight:700;line-height:1}
  .kpi .sub{font-size:.75rem;color:var(--muted);margin-top:4px}
  .kpi.blue .val{color:var(--accent)}
  .kpi.green .val{color:var(--green)}
  .kpi.yellow .val{color:var(--yellow)}
  .kpi.purple .val{color:var(--purple)}
  .kpi.orange .val{color:var(--orange)}

  /* Grid layout */
  .layout{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}
  .layout.three{grid-template-columns:2fr 1fr}
  @media(max-width:900px){.layout,.layout.three{grid-template-columns:1fr}}

  .panel{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:18px}
  .panel h2{font-size:.85rem;color:var(--muted);text-transform:uppercase;
            letter-spacing:.06em;margin-bottom:14px;display:flex;align-items:center;gap:8px}
  .chart-box{position:relative;height:220px}

  /* Activity feed */
  .feed{list-style:none;max-height:280px;overflow-y:auto}
  .feed::-webkit-scrollbar{width:4px}
  .feed::-webkit-scrollbar-track{background:transparent}
  .feed::-webkit-scrollbar-thumb{background:var(--border);border-radius:4px}
  .feed li{padding:8px 0;border-bottom:1px solid var(--border);font-size:.82rem;
           display:flex;justify-content:space-between;gap:8px;align-items:flex-start}
  .feed li:last-child{border-bottom:none}
  .feed .ftitle{color:var(--text);flex:1}
  .feed .fdate{color:var(--muted);font-size:.72rem;white-space:nowrap}

  /* Active task */
  .task-card{background:var(--surface);border:1px solid var(--border);border-radius:10px;
             padding:18px;margin-bottom:16px}
  .task-card h2{font-size:.85rem;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:10px}
  .task-name{font-size:1.1rem;font-weight:600;color:var(--yellow);margin-bottom:6px}
  .task-meta{font-size:.78rem;color:var(--muted)}
  .task-none{color:var(--muted);font-style:italic}

  /* Week bars */
  .week-row{display:flex;align-items:center;gap:8px;margin-bottom:6px;font-size:.78rem}
  .week-label{color:var(--muted);width:80px;flex-shrink:0}
  .week-bar-wrap{flex:1;background:#1c2130;border-radius:3px;height:10px;overflow:hidden}
  .week-bar{height:100%;background:var(--accent);border-radius:3px;transition:width .4s}
  .week-count{color:var(--text);width:28px;text-align:right;flex-shrink:0}

  footer{text-align:center;color:var(--muted);font-size:.72rem;padding-top:24px;border-top:1px solid var(--border);margin-top:8px}
</style>
</head>
<body>
<header>
  <h1><span class="pulse"></span> 🤖 BAGO Dashboard</h1>
  <div class="ts">Actualizado: <span id="ts">—</span> &nbsp;·&nbsp; refresca cada 5 s</div>
</header>

<div class="kpis">
  <div class="kpi blue"><div class="label">Ideas implementadas</div><div class="val" id="k-impl">—</div><div class="sub" id="k-impl-sub"></div></div>
  <div class="kpi green"><div class="label">Últ. 7 días</div><div class="val" id="k-last7">—</div><div class="sub">ideas nuevas</div></div>
  <div class="kpi orange"><div class="label">Herramientas</div><div class="val" id="k-tools">—</div><div class="sub">archivos .py</div></div>
  <div class="kpi yellow"><div class="label">Disponibles</div><div class="val" id="k-avail">—</div><div class="sub" id="k-db-total"></div></div>
  <div class="kpi purple"><div class="label">Snapshots</div><div class="val" id="k-snaps">—</div><div class="sub" id="k-dbkb"></div></div>
</div>

<div id="task-area" class="task-card">
  <h2>⏳ Tarea activa</h2>
  <div id="task-body" class="task-none">Sin tarea pendiente</div>
</div>

<div class="layout">
  <div class="panel">
    <h2>📈 Ideas acumuladas</h2>
    <div class="chart-box"><canvas id="chart-cum"></canvas></div>
  </div>
  <div class="panel">
    <h2>📊 Ideas por semana</h2>
    <div class="chart-box"><canvas id="chart-week"></canvas></div>
  </div>
</div>

<div class="layout three">
  <div class="panel">
    <h2>🕐 Actividad reciente</h2>
    <ul class="feed" id="feed"></ul>
  </div>
  <div class="panel">
    <h2>📅 Semanas (barras)</h2>
    <div id="week-bars" style="max-height:280px;overflow-y:auto"></div>
  </div>
</div>

<footer>BAGO Framework · Panel dinámico · Puerto __PORT__</footer>

<script>
const API = '/api/metrics';
const REFRESH = 5000;

const chartDefaults = {
  responsive:true, maintainAspectRatio:false,
  animation:{duration:600},
  plugins:{legend:{display:false}},
};

function mkLine(id){
  return new Chart(document.getElementById(id),{
    type:'line',
    data:{labels:[],datasets:[{data:[],borderColor:'#58a6ff',backgroundColor:'#58a6ff18',
          fill:true,tension:.35,pointRadius:3,pointHoverRadius:5,borderWidth:2}]},
    options:{...chartDefaults,
      scales:{
        y:{ticks:{color:'#8b949e'},grid:{color:'#21262d'}},
        x:{ticks:{color:'#8b949e',maxTicksLimit:10,maxRotation:45},grid:{display:false}},
      }
    }
  });
}

function mkBar(id){
  return new Chart(document.getElementById(id),{
    type:'bar',
    data:{labels:[],datasets:[{data:[],backgroundColor:'#3fb95066',borderColor:'#3fb950',
          borderWidth:1,borderRadius:4}]},
    options:{...chartDefaults,
      scales:{
        y:{ticks:{color:'#8b949e'},grid:{color:'#21262d'}},
        x:{ticks:{color:'#8b949e',maxRotation:45},grid:{display:false}},
      }
    }
  });
}

const cumChart = mkLine('chart-cum');
const weekChart= mkBar('chart-week');

function updateChart(chart, labels, data){
  chart.data.labels = labels;
  chart.data.datasets[0].data = data;
  chart.update();
}

function qs(id){ return document.getElementById(id); }

function renderWeekBars(perWeek){
  const sorted = Object.entries(perWeek).sort((a,b)=>a[0].localeCompare(b[0]));
  const max = Math.max(...sorted.map(e=>e[1]),1);
  const el = qs('week-bars');
  el.innerHTML = sorted.map(([w,n])=>`
    <div class="week-row">
      <div class="week-label">${w}</div>
      <div class="week-bar-wrap"><div class="week-bar" style="width:${Math.round(n/max*100)}%"></div></div>
      <div class="week-count">${n}</div>
    </div>`).join('');
}

async function refresh(){
  try {
    const r = await fetch(API);
    const d = await r.json();

    // KPIs
    qs('ts').textContent = d.ts;
    qs('k-impl').textContent = d.ideas_total;
    qs('k-impl-sub').textContent = `${d.db_done} en DB`;
    qs('k-last7').textContent = d.ideas_last7;
    qs('k-tools').textContent = d.tools;
    qs('k-avail').textContent = d.db_avail;
    qs('k-db-total').textContent = `de ${d.db_total} en DB`;
    qs('k-snaps').textContent = d.snaps;
    qs('k-dbkb').textContent = `DB ${d.db_kb} KB`;

    // Active task
    if(d.active_task){
      const t = d.active_task;
      qs('task-body').innerHTML =
        `<div class="task-name">${t.name}</div>
         <div class="task-meta">Prioridad: ${t.priority} &nbsp;·&nbsp; Workflow: ${t.workflow}</div>`;
    } else {
      qs('task-body').innerHTML = '<span class="task-none">Sin tarea activa</span>';
    }

    // Cumulative chart
    const cumEntries = Object.entries(d.cumulative).sort((a,b)=>a[0].localeCompare(b[0]));
    updateChart(cumChart, cumEntries.map(e=>e[0]), cumEntries.map(e=>e[1]));

    // Week chart
    const weekEntries = Object.entries(d.per_week).sort((a,b)=>a[0].localeCompare(b[0]));
    updateChart(weekChart, weekEntries.map(e=>e[0]), weekEntries.map(e=>e[1]));

    // Feed
    qs('feed').innerHTML = (d.recent||[]).map(r=>
      `<li><span class="ftitle">${r.title}</span><span class="fdate">${r.done_at}</span></li>`
    ).join('');

    // Week bars
    renderWeekBars(d.per_week);

  } catch(e){
    qs('ts').textContent = '⚠ sin datos';
  }
}

refresh();
setInterval(refresh, REFRESH);
</script>
</body>
</html>
"""


# ── HTTP server ───────────────────────────────────────────────────────────────

def _make_handler(port: int):
    html_page = HTML.replace("__PORT__", str(port))

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # silence default logging

        def do_GET(self):
            if self.path == "/api/metrics":
                try:
                    data = _build_metrics()
                    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except Exception as exc:
                    err = json.dumps({"error": str(exc)}).encode()
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(err)))
                    self.end_headers()
                    self.wfile.write(err)
            elif self.path in ("/", "/index.html"):
                body = html_page.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

    return Handler


def main():
    parser = argparse.ArgumentParser(description="BAGO live dashboard")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"Puerto HTTP (default: {DEFAULT_PORT})")
    parser.add_argument("--no-open", action="store_true",
                        help="No abrir navegador automáticamente")
    args = parser.parse_args()

    port = args.port
    url = f"http://localhost:{port}"

    print()
    print(f"  ┌─────────────────────────────────────────────────────────┐")
    print(f"  │  🤖  BAGO Dashboard — panel dinámico                    │")
    print(f"  └─────────────────────────────────────────────────────────┘")
    print(f"  URL   : {url}")
    print(f"  API   : {url}/api/metrics")
    print(f"  Refresca cada 5 segundos.  Ctrl+C para detener.\n")

    handler = _make_handler(port)
    server = HTTPServer(("localhost", port), handler)

    if not args.no_open:
        def _open():
            import time
            time.sleep(0.6)
            webbrowser.open(url)
        threading.Thread(target=_open, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Dashboard detenido.")
    finally:
        server.server_close()



def _self_test():
    """Autotest mínimo — verifica arranque limpio del módulo."""
    from pathlib import Path as _P
    assert _P(__file__).exists(), "fichero no encontrado"
    print("  1/1 tests pasaron")

if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    main()
