// ── Node Control data flow ───────────────────────────────────
function setNodeTab(name){
  activeNodeTab=name;
  document.querySelectorAll('.section-tab').forEach(t=>t.classList.toggle('active',t.getAttribute('data-tab')===name));
  document.querySelectorAll('.node-tab-panel').forEach(p=>p.style.display='none');
  const panelId='node-'+name;
  const panel=document.getElementById(panelId);
  if(panel) panel.style.display='block';
  if(nodeCache.status) renderNodeTab(name);
}

async function loadNodeData(){
  const api=electronApi();
  if(!api||!api.runNodeStatus){
    nodePanel.style.display='block';
    nodeCache.status=null;
    nodeCache.matrix=null;
    nodeCache.pieces=null;
    nodeCache.connectors=null;
    nodeCache.evidence=null;
    nodeCmdLabel.textContent='bago node status --json · no disponible';
    document.getElementById('node-overview').innerHTML='<div class="notice" style="margin:0"><b>Node Control no está disponible sin Electron/backend operativo.</b></div>';
    document.getElementById('node-pieces').innerHTML='<div class="notice" style="margin:0"><b>Node Control no está disponible sin Electron/backend operativo.</b></div>';
    document.getElementById('node-matrix').innerHTML='<div class="notice" style="margin:0"><b>Node Control no está disponible sin Electron/backend operativo.</b></div>';
    document.getElementById('node-connectors').innerHTML='<div class="notice" style="margin:0"><b>Node Control no está disponible sin Electron/backend operativo.</b></div>';
    document.getElementById('node-evidence').innerHTML='<div class="notice" style="margin:0"><b>Node Control no está disponible sin Electron/backend operativo.</b></div>';
    renderPatchManager();
    showToast('Node Control no disponible sin Electron/backend operativo',false);
    return;
  }
  try{
    nodePanel.style.display='block';
    nodeCmdLabel.textContent='bago node status --json (cargando...)';
    const [sR,mR,pR,cR,eR]=await Promise.all([api.runNodeStatus(),api.runNodeMatrix(),api.runNodePieces(),api.runNodeConnectors(),api.runNodeEvidence?api.runNodeEvidence(50):Promise.resolve({ok:true,data:{entries:[]}})]);
    if(!sR.ok) throw new Error('status: '+(sR.error||'?'));
    if(!mR.ok) throw new Error('matrix: '+(mR.error||'?'));
    if(!pR.ok) throw new Error('pieces: '+(pR.error||'?'));
    if(!cR.ok) throw new Error('connectors: '+(cR.error||'?'));
    if(!eR.ok) throw new Error('evidence: '+(eR.error||'?'));
    nodeCache.status=sR.data; nodeCache.matrix=mR.data; nodeCache.pieces=pR.data; nodeCache.connectors=cR.data; nodeCache.evidence=eR.data;
    nodeCmdLabel.textContent=`bago node status --json · ${sR.data.installations} inst · ${sR.data.pieces} pieces · ${sR.data.connectors} connectors`;
    renderNodeTab(activeNodeTab);
    renderPatchManager();
    showToast('Node Control cargado',true);
  }catch(e){
    nodeCmdLabel.textContent='bago node status --json (error)';
    nodePanel.style.display='block';
    document.getElementById('node-overview').innerHTML='<div class="notice" style="margin:0">'
      +'<b>Node Control no pudo cargar.</b><br>'
      +'<span style="color:var(--muted)">Comando: <code>bago node status --json</code></span><br>'
      +'<span style="color:#fecaca">'+escapeHtml(e.message)+'</span>'
      +'</div>';
    renderPatchManager();
    showToast('Node Control falló: '+e.message,false);
  }
}

function renderNodeTab(name){
  if(name==='overview') renderNodeOverview();
  else if(name==='pieces') renderNodePieces();
  else if(name==='matrix') renderNodeMatrix();
  else if(name==='connectors') renderNodeConnectors();
  else if(name==='evidence') renderNodeEvidence();
}

function renderNodeOverview(){
  const d=nodeCache.status; if(!d) return;
  const mods=d.modes||{};
  const compatRows=Array.isArray(d.compatibility_data)?d.compatibility_data:[];
  const allowedCount=compatRows.filter(r=>r.allowed).length;
  const canExec=compatRows.filter(r=>r.can_execute).length;
  const container=document.getElementById('node-overview');
  container.innerHTML='<div class="kpi-row">'
    +kpi('Installations',d.installations,'ok')
    +kpi('Pieces',d.pieces,'ok')
    +kpi('Connectors',d.connectors,'ok')
    +kpi('Compat rows',`${allowedCount}/${compatRows.length}`,allowedCount===compatRows.length?'ok':'warn')
    +kpi('Can execute',canExec,'')
    +kpi('Compatibility','ver matrix','warn')
    +'</div>'
    +'<h4 style="margin:18px 0 8px;font-size:12px;text-transform:uppercase;letter-spacing:0.08em;color:var(--muted);">Modes</h4>'
    +'<div class="kpi-row">'+Object.entries(mods).map(([k,v])=>kpi(k,Array.isArray(v)?v.length:'-','')).join('')+'</div>'
    +'<h4 style="margin:18px 0 8px;font-size:12px;text-transform:uppercase;letter-spacing:0.08em;color:var(--muted);">Installations</h4>'
    +'<div class="piece-grid">'+(d.installations_data||[]).map(i=>'<div class="piece-card">'
        +'<div class="pid">'+escapeHtml(i.installation_id)+'</div>'
        +'<div class="meta">'+escapeHtml(i.path)+'</div>'
        +'<div style="margin-top:6px"><span class="badge badge-mode">'+escapeHtml(i.mode)+'</span>'
        +'<span class="badge badge-neutral">'+escapeHtml(i.profile||'-')+'</span>'
        +(i.tag?'<span class="badge badge-on">'+escapeHtml(i.tag)+'</span>':'<span class="badge badge-warn">no tag</span>')
        +(i.has_supervisor?(i.supervisor_alive?'<span class="badge badge-on">sup ●</span>':'<span class="badge badge-off">sup ○</span>'):'<span class="badge badge-neutral">no sup</span>')
        +'</div></div>').join('')+'</div>';
}

function renderNodePieces(){
  const d=nodeCache.pieces; if(!d) return;
  const list=d.pieces||[];
  const container=document.getElementById('node-pieces');
  if(!list.length){container.innerHTML='<p style="color:var(--muted)">No hay piezas.</p>';return;}
  container.innerHTML='<div class="piece-grid">'+list.map(p=>'<div class="piece-card">'
    +'<div class="pid">'+escapeHtml(p.piece_id)+'</div>'
    +'<div style="margin-bottom:4px"><span class="type-badge">'+escapeHtml(p.type||'?')+'</span><span class="type-badge" style="background:rgba(34,211,238,0.15);color:#67e8f9;border-color:rgba(34,211,238,0.3)">'+escapeHtml(p.scope||'-')+'</span></div>'
    +'<div class="meta">v'+escapeHtml(p.version||'-')+' · '+escapeHtml((p.hash||'').slice(0,12))+'...</div>'
    +'<div class="path">'+escapeHtml(p.store_path||p.materialized_path||'-')+'</div>'
    +(p.exists?'':'<div style="margin-top:6px"><span class="badge badge-warn">no materializada</span></div>')
    +'</div>').join('')+'</div>';
}

function renderNodeMatrix(){
  const d=nodeCache.matrix; if(!d) return;
  const insts=d.installations||[];
  const rows=d.rows||[];
  if(!rows.length){document.getElementById('node-matrix').innerHTML='<p style="color:var(--muted)">Registry vacío.</p>';return;}
  const modeCls=m=>'mode-'+(String(m||'detached').replace(/\s+/g,'-'));
  const shortId=id=>String(id||'').replace(/^inst-/,'').slice(0,10);
  const shortPid=pid=>String(pid||'').split('.').pop();
  let html='<div class="matrix-wrap"><table class="matrix-table"><thead><tr><th>piece / installation</th>';
  for(const inst of insts) html+='<th title="'+escapeHtml(inst.installation_id)+'">'+escapeHtml(shortId(inst.installation_id))+'</th>';
  html+='</tr></thead><tbody>';
  for(const r of rows){
    html+='<tr><th class="row-head" title="'+escapeHtml(r.piece_id)+'">'+escapeHtml(r.piece_id||'')+'<br><span style="color:var(--muted);font-size:10px">'+escapeHtml(r.type||'')+' · '+escapeHtml(r.scope||'')+'</span></th>';
    for(const inst of insts){
      const cell=(r.cells||{})[inst.installation_id];
      const mode=cell?cell.mode:'detached';
      const label=cell?mode:'—';
      html+='<td class="'+(cell?modeCls(mode):'empty')+'" title="'+(cell?escapeHtml(JSON.stringify(cell,Object.keys(cell).filter(k=>['mode','can_execute','can_modify','reason'].includes(k)),2).slice(0,300)):'sin connector')+'">'+escapeHtml(label)+'</td>';
    }
    html+='</tr>';
  }
  html+='</tbody></table></div>';
  document.getElementById('node-matrix').innerHTML=html;
}

function renderNodeConnectors(){
  const d=nodeCache.connectors; if(!d) return;
  const list=d.connectors||[];
  const container=document.getElementById('node-connectors');
  if(!list.length){container.innerHTML='<p style="color:var(--muted)">No hay connectors.</p>';return;}
  const insts=Array.from(new Set(list.map(c=>c.installation_id))).sort();
  const pieces=Array.from(new Set(list.map(c=>c.piece_id))).sort();
  const modes=Array.from(new Set(list.map(c=>c.mode))).sort();
  container.innerHTML='<div class="connector-filter">'
    +'<input id="conn-search" placeholder="buscar (inst/piece/connector)" oninput="renderNodeConnectorsFiltered()">'
    +'<select id="conn-inst" onchange="renderNodeConnectorsFiltered()"><option value="">toda instalación</option>'+insts.map(i=>'<option>'+escapeHtml(i)+'</option>').join('')+'</select>'
    +'<select id="conn-piece" onchange="renderNodeConnectorsFiltered()"><option value="">toda pieza</option>'+pieces.map(p=>'<option>'+escapeHtml(p)+'</option>').join('')+'</select>'
    +'<select id="conn-mode" onchange="renderNodeConnectorsFiltered()"><option value="">todo modo</option>'+modes.map(m=>'<option>'+escapeHtml(m)+'</option>').join('')+'</select>'
    +'<span class="chip" id="conn-count" style="font-size:11px;padding:4px 10px;">'+list.length+' connectors</span>'
    +'</div><div id="conn-list" class="connector-list"></div>';
  window.__connAll=list;
  window.__modeCls=m=>'mode-'+(String(m||'detached').replace(/\s+/g,'-'));
  renderNodeConnectorsFiltered();
}

function renderNodeConnectorsFiltered(){
  const list=window.__connAll||[];
  const q=(document.getElementById('conn-search')?.value||'').toLowerCase();
  const inst=document.getElementById('conn-inst')?.value||'';
  const piece=document.getElementById('conn-piece')?.value||'';
  const mode=document.getElementById('conn-mode')?.value||'';
  const filtered=list.filter(c=>{
    if(inst&&c.installation_id!==inst)return false;
    if(piece&&c.piece_id!==piece)return false;
    if(mode&&c.mode!==mode)return false;
    if(q){
      const hay=(c.connector_id+' '+c.installation_id+' '+c.piece_id+' '+(c.reason||'')).toLowerCase();
      if(!hay.includes(q))return false;
    }
    return true;
  });
  document.getElementById('conn-count').textContent=filtered.length+'/'+list.length+' connectors';
  const modeCls=window.__modeCls||(m=>'mode-'+(String(m||'detached').replace(/\s+/g,'-')));
  document.getElementById('conn-list').innerHTML=filtered.map(c=>{
    const cls='mode '+modeCls(c.mode);
    return'<div class="connector-row">'
      +'<div class="cid" title="'+escapeHtml(c.connector_id)+'">'+escapeHtml(String(c.connector_id||'').slice(0,14))+'</div>'
      +'<div class="ids" title="'+escapeHtml(c.installation_id)+'">'+escapeHtml(c.installation_id)+'</div>'
      +'<div class="ids" title="'+escapeHtml(c.piece_id)+'">'+escapeHtml(c.piece_id)+'</div>'
      +'<div class="'+cls+'">'+escapeHtml(c.mode)+'</div>'
      +'</div>';
  }).join('')||'<p style="color:var(--muted);text-align:center;padding:20px">Sin coincidencias.</p>';
}

function renderNodeEvidence(){
  const d=nodeCache.status; if(!d) return;
  const container=document.getElementById('node-evidence');
  const evidence=nodeCache.evidence||{};
  const entries=Array.isArray(evidence.entries)?evidence.entries:[];
  const ef=d.evidence_file||'(no evidence file)';
  const base=d.base_path||'';
  const store=d.store_root||'';
  container.innerHTML='<p style="color:var(--muted);margin-bottom:12px">Cada acción del registry (connect/disconnect/set-mode) deja un registro inmutable. El archivo está en JSONL y se acumula append-only.</p>'
    +'<div class="kpi-row">'
    +kpi('Base path',base,'')
    +kpi('Store root',store,'')
    +kpi('Evidence file',ef.slice(-30),'')
    +'</div>'
    +'<div class="evidence-strip"><b>Path completo:</b><br><code>'+escapeHtml(ef)+'</code></div>'
    +'<div style="margin-top:12px">'+entries.slice(0,12).map(entry=>'<div class="audit">'
      +'<span class="time">'+escapeHtml(String(entry.timestamp||'').slice(11,19))+'</span>'
      +'<p><strong>'+escapeHtml(entry.action||'event')+'</strong><br>'+escapeHtml((entry.actor||'?')+' · '+(entry.result||'?')+' · '+JSON.stringify(entry.target||{}))+'</p>'
      +'<span class="badge '+(entry.result==='pass'||entry.result==='ok'?'badge-on':'badge-warn')+'">'+escapeHtml(entry.result||'?')+'</span></div>').join('')+'</div>'
    +'<div style="margin-top:14px">'
    +'<button class="copy" data-cmd="bago node validate --json">copiar `bago node validate --json`</button> '
    +'<button class="copy" data-cmd="bago node export --output node-export.json">copiar `bago node export`</button> '
    +'</div>';
}

function kpi(label,value,cls){
  return'<div class="kpi"><div class="label">'+escapeHtml(label)+'</div><div class="value '+(cls||'')+'">'+escapeHtml(String(value))+'</div></div>';
}
