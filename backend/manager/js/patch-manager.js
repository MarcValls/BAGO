// ── Patch-first manager experience ───────────────────────────
const PM_VIEW_TITLES={
  control:'Control',
  route:'Ruta nodular',
  bago:'BAGO Chat',
  patch:'Registry nodular',
  installations:'Instalaciones',
  matrix:'Pipelines',
  pieces:'PieceStore',
  releases:'Releases',
  jobs:'Trabajos de release',
  sessions:'Sesiones',
  health:'Salud operativa',
  audit:'Auditoría',
  system:'Sistema'
};
const PM_MODE_COLORS={
  connected:'#34d399',
  shadow:'#fbbf24',
  locked:'#fb7185',
  'read-only':'#22d3ee',
  'writable overlay':'#c084fc',
  detached:'#94a3b8',
  available:'#64748b'
};
const PM_WIRE_MODES={
  connected:'connected',
  shadow:'shadow',
  locked:'locked',
  'read-only':'readonly',
  'writable overlay':'overlay'
};
let pmActiveView='matrix';
let pmSelectedInstallation='';
let pmSelectedPiece='';
let pmSearch='';
let pmModeFilter='';
let pmReleaseChannel='stable';
let pmManagerHealth=null;
let pmMutationBusy=false;
let pmSelectedJobId='';
let pmSessionAudit=[{time:new Date().toLocaleTimeString('es-ES',{hour:'2-digit',minute:'2-digit'}),action:'manager',detail:'Gestor Patch-first iniciado'}];
let pmAuditTab=localStorage.getItem('bago.pm.audit.tab')||'project';
let pmAuditMetricsOpen=localStorage.getItem('bago.pm.audit.metrics')==='1';
let pmAuditState={project:null,bago:null,loaded_at:'',events:[]};
let pmMatrixTransposed=localStorage.getItem('bago.pm.matrix.transposed')==='1';

function pmModeClass(mode){return String(mode||'available').replace(/\s+/g,'-');}
function pmFormatBytes(value){
  const bytes=Number(value||0);
  if(!bytes)return '0 B';
  const units=['B','KB','MB','GB','TB'];
  const index=Math.min(units.length-1,Math.floor(Math.log(bytes)/Math.log(1024)));
  return (bytes/Math.pow(1024,index)).toFixed(index?1:0)+' '+units[index];
}
function pmElectronBridgeReady(api, methodName, label){
  if(api && typeof api[methodName] !== 'function'){
    showToast((label || methodName) + ' no disponible en Electron', false);
    return false;
  }
  return true;
}
function pmShort(value,fallback='--'){
  const text=String(value||'').replace(/^inst-/,'').replace(/^[^.]+\./,'');
  return (text||fallback).slice(0,14);
}
function pmPathName(value){
  const parts=String(value||'').split(/[\\/]/).filter(Boolean);
  return parts[parts.length-1]||String(value||'BAGO');
}
function pmNodeInstallations(){
  const status=nodeCache.status||{};
  const rows=Array.isArray(status.installations_data)?status.installations_data:[];
  if(rows.length)return rows;
  return Array.isArray(nodeCache.matrix&&nodeCache.matrix.installations)?nodeCache.matrix.installations:[];
}
function pmPieces(){
  const status=nodeCache.status||{};
  const rows=Array.isArray(status.pieces_data)?status.pieces_data:[];
  if(rows.length)return rows;
  return Array.isArray(nodeCache.pieces&&nodeCache.pieces.pieces)?nodeCache.pieces.pieces:[];
}
function pmConnectors(){
  if(nodeCache.connectors&&Array.isArray(nodeCache.connectors.connectors))return nodeCache.connectors.connectors;
  return Array.isArray(nodeCache.status&&nodeCache.status.connectors_data)?nodeCache.status.connectors_data:[];
}
function pmFindInstallation(id){return pmNodeInstallations().find(i=>i.installation_id===id)||null;}
function pmFindPiece(id){return pmPieces().find(p=>p.piece_id===id)||null;}
function pmFindConnector(installationId,pieceId){
  return pmConnectors().find(c=>c.installation_id===installationId&&c.piece_id===pieceId)||null;
}
function pmStableReleases(){return releaseItems.filter(rel=>!rel.prerelease);}
function pmPrereleases(){return releaseItems.filter(rel=>rel.prerelease);}
function pmReleaseContract(rel){
  const assets=Array.isArray(rel&&rel.assets)?rel.assets:[];
  const bundles=assets.filter(asset=>/\.zip$/i.test(asset.name||'')&&!/\.sha256$/i.test(asset.name||''));
  const exactChecksum=bundle=>assets.find(asset=>String(asset.name||'').toLowerCase()===(bundle.name+'.sha256').toLowerCase())||null;
  const bundle=bundles.find(item=>exactChecksum(item))||bundles[0]||null;
  const checksum=bundle&&exactChecksum(bundle)||null;
  const manager=assets.find(asset=>/BAGO-Installation-Manager.*\.exe$/i.test(asset.name||''))||null;
  const warnings=[];
  if(!bundle)warnings.push('sin bundle ZIP');
  if(!checksum)warnings.push('sin checksum SHA256');
  if(bundle&&!bundle.digest)warnings.push('digest remoto no publicado');
  return {bundle,checksum,manager,warnings,ok:!!(bundle&&checksum)};
}
function pmMatrixCell(installationId,pieceId){
  const rows=Array.isArray(nodeCache.matrix&&nodeCache.matrix.rows)?nodeCache.matrix.rows:[];
  const row=rows.find(r=>r.piece_id===pieceId);
  if(!row)return null;
  if(Array.isArray(row.cells))return row.cells.find(c=>c.installation_id===installationId)||null;
  return row.cells&&row.cells[installationId]||null;
}
function pmMatrixSortValue(entity, key, refsCount){
  if(key==='refs') return Number(refsCount||0);
  if(!entity) return '';
  if(key==='name') return pmPathName(entity.path||entity.name||entity.installation_id||'');
  if(key==='mode') return entity.mode||entity.profile||'';
  if(key==='scope') return entity.scope||'';
  if(key==='id') return entity.piece_id||entity.installation_id||entity.id||'';
  return entity.type||entity.profile||entity.piece_id||entity.installation_id||'';
}
function pmCompareMatrixValues(a,b,direction){
  if(a===b)return 0;
  const factor=direction==='desc'?-1:1;
  if(typeof a==='number' || typeof b==='number'){
    return (Number(a||0)-Number(b||0))*factor;
  }
  return String(a||'').localeCompare(String(b||''), 'es', { sensitivity:'base' })*factor;
}
function pmMatrixToggleTransposed(next){
  pmMatrixTransposed=!!next;
  localStorage.setItem('bago.pm.matrix.transposed', pmMatrixTransposed ? '1' : '0');
}
function pmTransposeMatrix(){
  pmMatrixToggleTransposed(!pmMatrixTransposed);
  const btn=document.getElementById('pm-matrix-transpose');
  if(btn){
    btn.title=pmMatrixTransposed ? 'Volver a la vista normal' : 'Cambiar orientación de la matriz';
    btn.setAttribute('aria-pressed', pmMatrixTransposed ? 'true' : 'false');
  }
  pmAudit('matrix', pmMatrixTransposed ? 'Matriz transpuesta' : 'Matriz normal');
  showToast(pmMatrixTransposed ? 'Matriz transpuesta' : 'Matriz normal', true);
  pmRenderMatrix();
}
function pmEnsureSelection(){
  const installs=pmNodeInstallations();
  if(!installs.some(i=>i.installation_id===pmSelectedInstallation)){
    pmSelectedInstallation=(installs.find(i=>i.mode==='work')||installs.find(i=>i.mode==='source')||installs[0]||{}).installation_id||'';
  }
  const pieces=pmPieces();
  if(!pieces.some(p=>p.piece_id===pmSelectedPiece))pmSelectedPiece=(pieces[0]||{}).piece_id||'';
}
function pmBadge(text,cls=''){
  return '<span class="pm-badge '+cls+'">'+escapeHtml(text)+'</span>';
}
function pmModeBadge(mode){
  return '<span class="pm-mode '+pmModeClass(mode)+'">'+escapeHtml(mode||'available')+'</span>';
}
function pmAudit(action,detail){
  pmSessionAudit.unshift({time:new Date().toLocaleTimeString('es-ES',{hour:'2-digit',minute:'2-digit'}),action,detail});
  pmSessionAudit=pmSessionAudit.slice(0,60);
  pmRenderAudit();
}
function pmAuditSeverityBadge(severity){
  const tone=severity==='high'?'bad':severity==='medium'?'warn':'info';
  return pmBadge(severity||'info',tone);
}
function pmAuditMetric(label, value){
  return '<div class="pm-audit-metric"><span>'+escapeHtml(label)+'</span><strong>'+escapeHtml(String(value || '0'))+'</strong></div>';
}
function pmAuditFindingHtml(finding){
  const sev=String(finding&&finding.severity||'low').toLowerCase();
  const title=finding&&finding.title||finding&&finding.code||'Hallazgo';
  const detail=finding&&finding.detail||'';
  const file=finding&&finding.file||'';
  return '<div class="pm-audit-finding">'
    +pmAuditSeverityBadge(sev)
    +'<div><strong>'+escapeHtml(title)+'</strong><span>'+escapeHtml(detail)+'</span>'+ (file ? '<code>'+escapeHtml(file)+'</code>' : '') +'</div>'
    +'<div>'+pmBadge(String(finding&&finding.scope||'audit').toUpperCase(),'info')+'</div>'
    +'</div>';
}
function pmAuditEventHtml(entry){
  return '<div class="pm-audit-event">'
    +'<time>'+escapeHtml(String(entry&&entry.timestamp||'').slice(11,19))+'</time>'
    +'<strong>'+escapeHtml(entry&&entry.scope||'event')+'</strong>'
    +'<span>'+escapeHtml(entry&&entry.detail||entry&&entry.action||'')+'</span>'
    +'<code>'+escapeHtml(entry&&entry.source||'local')+'</code>'
    +'</div>';
}
function pmAuditActionHtml(label, action, tone=''){
  return '<button class="pm-btn '+escapeHtml(tone)+'" data-audit-action="'+escapeHtml(action)+'">'+escapeHtml(label)+'</button>';
}
function pmAuditQuickActions(kind, payload){
  const actions=[];
  if(kind==='project'){
    const findings=Array.isArray(payload&&payload.findings)?payload.findings:[];
    const codes=findings.map(item=>String(item.code||item.title||'').toLowerCase());
    if(codes.some(code=>code.includes('version')||code.includes('drift'))) actions.push(pmAuditActionHtml('Revisar versiones','project-fix-version','primary'));
    if(codes.some(code=>code.includes('duplicate')||code.includes('duplicate-id'))) actions.push(pmAuditActionHtml('Eliminar duplicados','project-fix-duplicates'));
    if(codes.some(code=>code.includes('missing')||code.includes('absent'))) actions.push(pmAuditActionHtml('Crear ausentes','project-fix-missing'));
    actions.push(pmAuditActionHtml('Exportar','project-export'));
  }
  if(kind==='bago'){
    const health=payload&&payload.health||{};
    const startup=health.startup||{};
    const missing=Array.isArray(startup.missing_core)?startup.missing_core:[];
    if(missing.length) actions.push(pmAuditActionHtml('Instalar faltantes','bago-install-missing','primary'));
    actions.push(pmAuditActionHtml('Abrir salud','bago-open-health'));
    actions.push(pmAuditActionHtml('Ver jobs','bago-open-jobs'));
    actions.push(pmAuditActionHtml('Exportar','bago-export'));
  }
  if(kind==='events'){
    actions.push(pmAuditActionHtml('Actualizar','events-refresh','primary'));
    actions.push(pmAuditActionHtml('Exportar','events-export'));
    actions.push(pmAuditActionHtml('Filtrar UI','events-filter-ui'));
  }
  return actions.join('');
}
function pmSwitchView(view){
  pmActiveView=view;
  window.__bagoInteractionLogPush && window.__bagoInteractionLogPush('view-switch', { view });
  document.querySelectorAll('[data-pm-view]').forEach(b=>b.classList.toggle('active',b.getAttribute('data-pm-view')===view));
  document.querySelectorAll('.pm-view').forEach(v=>v.classList.toggle('active',v.id==='pm-view-'+view));
  document.getElementById('pm-title').textContent=PM_VIEW_TITLES[view]||'BAGO Manager';
  if(view==='patch')setTimeout(pmUpdatePatchLines,30);
  if(view==='route'&&typeof pmUpdateRouteLines==='function')setTimeout(pmUpdateRouteLines,30);
  if(view==='matrix'&&typeof pmRenderPipelineRail==='function')setTimeout(pmRenderPipelineRail,30);
}
function pmFilteredPieceRows(){
  const inst=pmFindInstallation(pmSelectedInstallation);
  return pmPieces().map(piece=>{
    const connector=pmFindConnector(pmSelectedInstallation,piece.piece_id);
    const cell=pmMatrixCell(pmSelectedInstallation,piece.piece_id);
    const mode=connector&&connector.mode||cell&&cell.mode||'available';
    return {piece,connector,cell,mode,inst};
  }).filter(row=>{
    if(pmModeFilter&&row.mode!==pmModeFilter)return false;
    if(!pmSearch)return true;
    return [row.piece.piece_id,row.piece.type,row.piece.scope,row.mode,row.connector&&row.connector.connector_id,inst&&inst.path].join(' ').toLowerCase().includes(pmSearch);
  });
}
function pmRenderStats(){
  const status=nodeCache.status||{};
  const connectors=pmConnectors();
  const modes={};
  connectors.forEach(c=>{modes[c.mode]=(modes[c.mode]||0)+1;});
  const matrixPairs=pmNodeInstallations().length*pmPieces().length;
  const unmaterialized=Number.isFinite(status.unmaterialized_connectors)?status.unmaterialized_connectors:Math.max(0,matrixPairs-connectors.length);
  const scanRows=existingInstallations();
  const alive=scanRows.filter(i=>i.supervisor_alive).length;
  const stats=[
    ['Instalaciones',status.installations||pmNodeInstallations().length,scanRows.length?'detección en runtime + registry':'registry'],
    ['Piezas',status.pieces||pmPieces().length,'PieceStore compartido'],
    ['Connectors',status.connectors||connectors.length,unmaterialized+' cruces disponibles'],
    ['Connected',modes.connected||0,'ejecución permitida'],
    ['Overlays',modes['writable overlay']||0,'modificación aislada'],
    ['Supervisores',alive+'/'+scanRows.length,'procesos vivos']
  ];
  document.getElementById('pm-stats').innerHTML=stats.map(s=>'<article class="pm-stat"><span>'+escapeHtml(s[0])+'</span><strong>'+escapeHtml(s[1])+'</strong><small>'+escapeHtml(s[2])+'</small></article>').join('');
  document.getElementById('pm-store-installs').textContent=status.installations||pmNodeInstallations().length||0;
  document.getElementById('pm-store-pieces').textContent=status.pieces||pmPieces().length||0;
  document.getElementById('pm-store-connectors').textContent=status.connectors||connectors.length||0;
  const store=document.getElementById('pm-store-root');
  store.textContent=status.store_root?'shared':'sin datos';
  store.title=status.store_root||'';
}
function pmRenderInstallSelector(){
  const select=document.getElementById('pm-install-filter');
  const rows=pmNodeInstallations();
  select.innerHTML=rows.map(i=>'<option value="'+escapeHtml(i.installation_id)+'">'+escapeHtml(pmPathName(i.path))+' · '+escapeHtml(i.mode||i.profile||'')+'</option>').join('');
  select.value=pmSelectedInstallation;
}
function pmStoredPosition(key){
  try{return JSON.parse(localStorage.getItem('bago.pm.pos.'+key)||'null');}catch{return null;}
}
function pmRenderPatch(){
  pmEnsureSelection();
  pmRenderInstallSelector();
  const stage=document.getElementById('pm-stage');
  const inst=pmFindInstallation(pmSelectedInstallation);
  const rows=pmFilteredPieceRows();
  document.getElementById('pm-patch-caption').textContent=inst?inst.path+' · '+rows.length+' cruces visibles':'Sin instalación seleccionada';
  if(!inst||!rows.length){
    stage.innerHTML='<div class="pm-empty">No hay cruces visibles con el filtro actual.</div>';
    pmRenderDetail();
    return;
  }
  if(!rows.some(r=>r.piece.piece_id===pmSelectedPiece))pmSelectedPiece=rows[0].piece.piece_id;
  const height=650;
  const yAt=(idx,total)=>total<2?height/2:42+(height-84)*idx/(total-1);
  const paths=[];
  const pieces=[];
  const connectors=[];
  rows.forEach((row,index)=>{
    const y=yAt(index,rows.length);
    const key=pmSelectedInstallation+'__'+row.piece.piece_id;
    const stored=pmStoredPosition(key);
    const cx=stored&&stored.x||50;
    const cy=stored&&stored.y||y/height*100;
    const connectorDom='pm-connector-node-'+index;
    const pieceDom='pm-piece-node-'+index;
    const color=PM_MODE_COLORS[row.mode]||PM_MODE_COLORS.available;
    paths.push('<path data-from="pm-inst-node" data-to="'+connectorDom+'" stroke="'+color+'" stroke-width="2" fill="none" opacity=".68"/><path data-from="'+connectorDom+'" data-to="'+pieceDom+'" stroke="'+color+'" stroke-width="2" fill="none" opacity=".68" '+(row.mode==='locked'||row.mode==='detached'||row.mode==='available'?'stroke-dasharray="5 7"':'')+'/>');
    connectors.push('<div id="'+connectorDom+'" class="pm-node connector '+pmModeClass(row.mode)+' '+(row.piece.piece_id===pmSelectedPiece?'selected':'')+' '+(!row.connector?'available':'')+'" data-pm-piece="'+escapeHtml(row.piece.piece_id)+'" data-pm-drag="'+escapeHtml(key)+'" style="left:'+cx+'%;top:'+cy+'%"><strong>'+escapeHtml(row.connector&&row.connector.connector_id||'sin connector')+'</strong><small>'+escapeHtml(pmShort(inst.installation_id))+' → '+escapeHtml(pmShort(row.piece.piece_id))+'</small>'+pmModeBadge(row.mode)+'</div>');
    pieces.push('<div id="'+pieceDom+'" class="pm-node piece" data-pm-piece="'+escapeHtml(row.piece.piece_id)+'" style="top:'+(y/height*100)+'%"><strong>'+escapeHtml(row.piece.piece_id)+'</strong><small>'+escapeHtml(row.piece.type||'piece')+' · '+escapeHtml(row.piece.scope||'')+'</small></div>');
  });
  stage.innerHTML='<svg class="pm-patch-svg" id="pm-patch-svg">'+paths.join('')+'</svg>'
    +'<div id="pm-inst-node" class="pm-node installation" style="top:50%"><strong>'+escapeHtml(pmPathName(inst.path))+'</strong><small>'+escapeHtml(inst.installation_id)+' · '+escapeHtml(inst.profile||inst.mode||'')+'</small></div>'
    +connectors.join('')+pieces.join('');
  stage.querySelectorAll('[data-pm-piece]').forEach(node=>node.addEventListener('click',()=>{pmSelectedPiece=node.getAttribute('data-pm-piece')||'';pmRenderPatch();}));
  stage.querySelectorAll('[data-pm-drag]').forEach(node=>node.addEventListener('pointerdown',pmStartDrag));
  pmRenderDetail();
  setTimeout(pmUpdatePatchLines,20);
}
function pmUpdatePatchLines(){
  const stage=document.getElementById('pm-stage');
  if(!stage||!document.getElementById('pm-patch-svg'))return;
  const rect=stage.getBoundingClientRect();
  stage.querySelectorAll('#pm-patch-svg path').forEach(path=>{
    const a=document.getElementById(path.getAttribute('data-from'));
    const b=document.getElementById(path.getAttribute('data-to'));
    if(!a||!b)return;
    const ar=a.getBoundingClientRect(),br=b.getBoundingClientRect();
    const x1=ar.left+ar.width/2-rect.left,y1=ar.top+ar.height/2-rect.top;
    const x2=br.left+br.width/2-rect.left,y2=br.top+br.height/2-rect.top;
    const mx=x1+(x2-x1)*.55;
    path.setAttribute('d','M '+x1+' '+y1+' C '+mx+' '+y1+', '+mx+' '+y2+', '+x2+' '+y2);
  });
}
function pmStartDrag(event){
  const node=event.currentTarget;
  const stage=document.getElementById('pm-stage');
  const rect=stage.getBoundingClientRect();
  const startX=event.clientX,startY=event.clientY;
  const originX=parseFloat(node.style.left)||50,originY=parseFloat(node.style.top)||50;
  const key=node.getAttribute('data-pm-drag')||'';
  let moved=false;
  node.setPointerCapture(event.pointerId);
  const move=ev=>{
    const x=Math.max(26,Math.min(74,originX+(ev.clientX-startX)/rect.width*100));
    const y=Math.max(5,Math.min(95,originY+(ev.clientY-startY)/rect.height*100));
    if(Math.abs(ev.clientX-startX)+Math.abs(ev.clientY-startY)>4)moved=true;
    node.style.left=x+'%';node.style.top=y+'%';
    localStorage.setItem('bago.pm.pos.'+key,JSON.stringify({x,y}));
    pmUpdatePatchLines();
  };
  const up=()=>{node.removeEventListener('pointermove',move);if(moved)pmAudit('layout','Connector recolocado: '+key);};
  node.addEventListener('pointermove',move);
  node.addEventListener('pointerup',up,{once:true});
}
function pmRenderDetail(){
  const container=document.getElementById('pm-patch-detail-body');
  const inst=pmFindInstallation(pmSelectedInstallation);
  const piece=pmFindPiece(pmSelectedPiece);
  if(!inst||!piece){container.innerHTML='<div class="pm-empty">Selecciona un cruce.</div>';return;}
  const connector=pmFindConnector(inst.installation_id,piece.piece_id);
  const cell=pmMatrixCell(inst.installation_id,piece.piece_id)||{};
  const policy=connector&&connector.policy||cell||{};
  const mode=connector&&connector.mode||cell.mode||'available';
  container.classList.toggle('pm-busy',pmMutationBusy);
  container.innerHTML='<h3>'+escapeHtml(connector&&connector.connector_id||'Connector no materializado')+'</h3>'
    +'<div class="pm-detail-sub">'+escapeHtml(inst.path)+' → '+escapeHtml(piece.piece_id)+'</div>'
    +pmModeBadge(mode)
    +'<div class="pm-kv">'
    +'<div><span>Instalación</span><strong>'+escapeHtml(inst.installation_id)+'</strong></div>'
    +'<div><span>Pieza</span><strong>'+escapeHtml(piece.type||'')+' / '+escapeHtml(piece.scope||'')+'</strong></div>'
    +'<div><span>Estado</span><strong>'+escapeHtml(connector?mode:'not-created / available')+'</strong></div>'
    +'<div><span>Versión</span><strong>'+escapeHtml(piece.version||'-')+'</strong></div>'
    +'<div><span>Ejecuta</span><strong>'+escapeHtml(String(policy.can_execute===true))+'</strong></div>'
    +'<div><span>Modifica</span><strong>'+escapeHtml(String(policy.can_modify===true))+'</strong></div>'
    +'<div><span>Sync</span><strong>'+escapeHtml(policy.sync_mode||'-')+'</strong></div>'
    +'<div><span>Razón</span><strong>'+escapeHtml(connector&&connector.reason||(!connector?'catálogo sin connector':'-'))+'</strong></div>'
    +'</div><div class="pm-mode-actions">'
    +'<button data-pm-mode="connected">Connect</button><button data-pm-mode="shadow">Shadow</button>'
    +'<button data-pm-mode="read-only">Read only</button><button data-pm-mode="writable overlay">Overlay</button>'
    +'<button data-pm-mode="locked">Lock</button><button data-pm-mode="detached">Detach</button>'
    +'</div>';
  container.querySelectorAll('[data-pm-mode]').forEach(btn=>btn.addEventListener('click',()=>pmMutateConnector(btn.getAttribute('data-pm-mode')||'')));
}
async function pmValidateRegistry(){
  const api=electronApi();
  if(api && !pmElectronBridgeReady(api,'runNodeValidate','runNodeValidate')) return {ok:false,error:'runNodeValidate no disponible en Electron'};
  if(!api||!api.runNodeValidate)return pmLocalNodeValidate();
  try{
    const result=await api.runNodeValidate();
    const data=result&&result.data||{};
    return {ok:!!(result&&result.ok&&Number(data.failures||0)===0),data,error:result&&result.error||''};
  }catch(e){
    return {ok:false,error:e.message};
  }
}
function pmMutationArgs(action,installationId,pieceId,mode){
  if(action==='disconnect'||mode==='detached'){
    return ['node','disconnect','--installation',installationId,'--piece',pieceId,'--json'];
  }
  return ['node',action,'--installation',installationId,'--piece',pieceId,'--mode',PM_WIRE_MODES[mode]||mode,'--json'];
}
function pmRollbackArgs(preview){
  const target=preview.target||{};
  if(!preview.current){
    return pmMutationArgs('disconnect',target.installation_id,target.piece_id,'detached');
  }
  const previous=preview.current_state||preview.current.mode||'detached';
  return pmMutationArgs(previous==='detached'?'disconnect':'set-mode',target.installation_id,target.piece_id,previous);
}
function pmConfirmMutation(preview){
  const dialog=document.getElementById('pm-mutation-dialog');
  if(!dialog||typeof dialog.showModal!=='function'){
    return Promise.resolve(window.confirm(preview.action+' '+preview.current_state+' → '+preview.proposed.mode+'?'));
  }
  document.getElementById('pm-mutation-title').textContent='Preflight · '+preview.action;
  document.getElementById('pm-mutation-target').textContent=(preview.target.installation_path||preview.target.installation_id)+' → '+preview.target.piece_id;
  const risk=document.getElementById('pm-mutation-risk');
  risk.textContent=preview.risk||'low';risk.className='pm-risk '+(preview.risk||'low');
  const warnings=(preview.warnings||[]).map(w=>pmBadge(w,'warn')).join('')||pmBadge('sin advertencias','ok');
  document.getElementById('pm-mutation-body').innerHTML=''
    +'<div class="pm-preview-row"><span>Estado actual</span><strong>'+escapeHtml(preview.current_state||'available')+'</strong></div>'
    +'<div class="pm-preview-row"><span>Estado propuesto</span><strong>'+escapeHtml(preview.proposed.mode||'')+'</strong></div>'
    +'<div class="pm-preview-row"><span>Política perfil</span><strong>'+escapeHtml(preview.recommended.mode||'')+'</strong></div>'
    +'<div class="pm-preview-row"><span>Permisos</span><strong>exec '+escapeHtml(String(preview.proposed.policy.can_execute))+' · modify '+escapeHtml(String(preview.proposed.policy.can_modify))+' · '+escapeHtml(preview.proposed.policy.sync_mode||'')+'</strong></div>'
    +'<div class="pm-preview-row"><span>Advertencias</span><strong>'+warnings+'</strong></div>';
  return new Promise(resolve=>{
    const onClose=()=>{dialog.removeEventListener('close',onClose);resolve(dialog.returnValue==='apply');};
    dialog.addEventListener('close',onClose);
    dialog.showModal();
  });
}
async function pmMutateConnector(mode){
  const inst=pmFindInstallation(pmSelectedInstallation),piece=pmFindPiece(pmSelectedPiece);
  if(!inst||!piece||pmMutationBusy)return;
  const existing=pmFindConnector(inst.installation_id,piece.piece_id);
  const action=mode==='detached'?'disconnect':existing?'set-mode':'connect';
  const args=pmMutationArgs(action,inst.installation_id,piece.piece_id,mode);
  const api=electronApi();
  if(api && (!pmElectronBridgeReady(api,'runNodeCommand','runNodeCommand') || !pmElectronBridgeReady(api,'runNodePreview','runNodePreview'))){
    return;
  }
  if(!api||!api.runNodeCommand||!api.runNodePreview){
    await copyText('bago '+args.filter(arg=>arg!=='--json').join(' '));
    pmAudit('copy',action+' preparado para '+piece.piece_id);
    return;
  }
  pmMutationBusy=true;pmRenderDetail();
  try{
    const baseline=await pmValidateRegistry();
    if(!baseline.ok)throw new Error('preflight bloqueado: '+(baseline.error||'Node Control no válido'));
    const previewResult=await api.runNodePreview(inst.installation_id,piece.piece_id,PM_WIRE_MODES[mode]||mode);
    if(!previewResult||!previewResult.ok)throw new Error(previewResult&&previewResult.error||'preview rechazado');
    const preview=previewResult.data;
    if(!preview.requires_confirmation){
      showToast('El connector ya está en '+mode,true);
      return;
    }
    if(!await pmConfirmMutation(preview)){
      pmAudit('cancel',piece.piece_id+' · '+mode);
      return;
    }
    const result=await api.runNodeCommand(args);
    if(!result||!result.ok)throw new Error(result&&result.error||'operación rechazada');
    const after=await pmValidateRegistry();
    if(!after.ok){
      let rollback='no ejecutado';
      try{
        const reverted=await api.runNodeCommand(pmRollbackArgs(preview));
        rollback=reverted&&reverted.ok?'aplicado':'falló';
      }catch(e){rollback='falló: '+e.message;}
      pmAudit('rollback',piece.piece_id+' · '+rollback);
      throw new Error('validación posterior falló; rollback '+rollback);
    }
    pmAudit(action,piece.piece_id+' · '+preview.current_state+' → '+mode+' · validado');
    await loadNodeData();
    showToast('Connector actualizado y validado',true);
  }catch(e){
    await loadNodeData().catch(()=>{});
    showToast('Node Control: '+e.message,false);
  }finally{
    pmMutationBusy=false;pmRenderDetail();
  }
}
function pmRenderInstallations(){
  const container=document.getElementById('pm-installations-list');
  const nodeRows=pmNodeInstallations();
  const scanRows=existingInstallations();
  const merged=nodeRows.map(node=>Object.assign({},scanRows.find(scan=>normalizePathKey(scan.path)===normalizePathKey(node.path))||{},node));
  scanRows.forEach(scan=>{if(!merged.some(node=>normalizePathKey(node.path)===normalizePathKey(scan.path)))merged.push(scan);});
  const filtered=merged.filter(i=>!pmSearch||[i.path,i.mode,i.profile,i.version,i.tag,i.description].join(' ').toLowerCase().includes(pmSearch));
  container.innerHTML=filtered.map(inst=>{
    const nodeId=inst.installation_id||'';
    const version=inst.version||inst.tag||'-';
    const roles=inst.selection_roles||[];
    const update=updateState(inst);
    return '<article class="pm-row" data-pm-install="'+escapeHtml(nodeId)+'"><div class="pm-row-icon">'+escapeHtml(pmShort(inst.mode||nodeId))+'</div>'
      +'<div><h3>'+escapeHtml(pmPathName(inst.path))+' · '+escapeHtml(version)+'</h3><p>'+escapeHtml(inst.path)+'</p><div class="pm-badges">'
      +pmBadge(inst.mode||'manual','info')+pmBadge(inst.profile||'sin perfil')+pmBadge(update.label,update.cls==='badge-on'?'ok':'warn')
      +(inst.supervisor_alive?pmBadge('supervisor vivo','ok'):pmBadge('supervisor parado','bad'))
      +roles.map(r=>pmBadge('rol '+roleBadgeLabel(r),'ok')).join('')+'</div></div>'
      +'<div class="pm-row-actions"><button data-pm-install-action="focus" data-id="'+escapeHtml(nodeId)+'">Patch</button>'
      +'<button data-pm-install-action="active" data-path="'+escapeHtml(inst.path)+'">Activa</button><button data-pm-install-action="dev" data-path="'+escapeHtml(inst.path)+'">Dev</button>'
      +'<button data-pm-install-action="launch" data-path="'+escapeHtml(inst.path)+'">Ign</button><button data-pm-install-action="update" data-path="'+escapeHtml(inst.path)+'">Actualizar</button><button data-pm-install-action="uninstall-impact" data-path="'+escapeHtml(inst.path)+'">Impacto</button><button class="danger" data-pm-install-action="uninstall" data-path="'+escapeHtml(inst.path)+'">Archivar</button></div></article>';
  }).join('')||'<div class="pm-empty">Sin instalaciones visibles.</div>';
  container.querySelectorAll('[data-pm-install-action]').forEach(btn=>btn.addEventListener('click',async ev=>{
    ev.stopPropagation();
    const action=btn.getAttribute('data-pm-install-action')||'';
    const path=btn.getAttribute('data-path')||'';
    if(action==='focus'){
      pmSelectedInstallation=btn.getAttribute('data-id')||pmSelectedInstallation;pmSwitchView('patch');pmRenderPatch();return;
    }
    if(['active','dev','launch'].includes(action)){
      if(!window.confirm('Asignar '+action+' a '+path+'?'))return;
      await setInstallRole(action,path);pmAudit('rol',action+' → '+path);renderPatchManager();return;
    }
    if(action==='update'){
      if(!latestRelease){showToast('No hay release stable disponible',false);return;}
      await pmPrepareRelease(latestRelease,path,'update');
    }
    if(action==='uninstall-impact')await pmInspectUninstall(path);
    if(action==='uninstall')await pmUninstallInstallation(path);
  }));
}
function pmRenderMatrix(containerId='pm-matrix'){
  const container=document.getElementById(containerId);
  if(!container)return;
  const installs=pmNodeInstallations();
  const pieces=pmPieces().filter(p=>!pmSearch||[p.piece_id,p.type,p.scope].join(' ').toLowerCase().includes(pmSearch));
  if(!installs.length||!pieces.length){container.innerHTML='<div class="pm-empty">Registry sin datos.</div>';return;}
  const pieceSort=document.getElementById('pm-matrix-piece-sort')&&document.getElementById('pm-matrix-piece-sort').value||'type';
  const installSort=document.getElementById('pm-matrix-install-sort')&&document.getElementById('pm-matrix-install-sort').value||'profile';
  const direction=document.getElementById('pm-matrix-direction')&&document.getElementById('pm-matrix-direction').value||'asc';
  const refsByPiece=new Map(pieces.map(piece=>[piece.piece_id,pmConnectors().filter(c=>c.piece_id===piece.piece_id).length]));
  const installsSorted=installs.slice().sort((a,b)=>pmCompareMatrixValues(pmMatrixSortValue(a,installSort,0),pmMatrixSortValue(b,installSort,0),direction));
  const piecesSorted=pieces.slice().sort((a,b)=>pmCompareMatrixValues(pmMatrixSortValue(a,pieceSort,refsByPiece.get(a.piece_id)||0),pmMatrixSortValue(b,pieceSort,refsByPiece.get(b.piece_id)||0),direction));
  const rows=pmMatrixTransposed?installsSorted:piecesSorted;
  const cols=pmMatrixTransposed?piecesSorted:installsSorted;
  let html='<table class="pm-matrix"><thead><tr><th>'+(pmMatrixTransposed?'Instalación':'Pieza')+'</th>'+cols.map(item=>{
    if(pmMatrixTransposed){
      return '<th>'+escapeHtml(item.piece_id)+'<br><span>'+escapeHtml(item.type||'')+' · '+escapeHtml(item.scope||'')+'</span></th>';
    }
    return '<th>'+escapeHtml(pmPathName(item.path))+'<br><span>'+escapeHtml(item.profile||item.mode||'')+'</span></th>';
  }).join('')+'</tr></thead><tbody>';
  rows.forEach(row=>{
    if(pmMatrixTransposed){
      const inst=row;
      html+='<tr><td><strong>'+escapeHtml(pmPathName(inst.path))+'</strong><br><span>'+escapeHtml(inst.profile||inst.mode||'')+'</span></td>';
      cols.forEach(piece=>{
        const connector=pmFindConnector(inst.installation_id,piece.piece_id),cell=pmMatrixCell(inst.installation_id,piece.piece_id)||{};
        const mode=connector&&connector.mode||cell.mode||'available';
        html+='<td><div class="pm-cell" data-pm-matrix-inst="'+escapeHtml(inst.installation_id)+'" data-pm-matrix-piece="'+escapeHtml(piece.piece_id)+'"><strong>'+escapeHtml(mode)+'</strong><span>exec '+escapeHtml(String((connector&&connector.policy&&connector.policy.can_execute)||cell.can_execute||false))+' · mod '+escapeHtml(String((connector&&connector.policy&&connector.policy.can_modify)||cell.can_modify||false))+'</span>'+pmModeBadge(mode)+'</div></td>';
      });
      html+='</tr>';
      return;
    }
    const piece=row;
    html+='<tr><td><strong>'+escapeHtml(piece.piece_id)+'</strong><br><span>'+escapeHtml(piece.type||'')+' · '+escapeHtml(piece.scope||'')+'</span></td>';
    cols.forEach(inst=>{
      const connector=pmFindConnector(inst.installation_id,piece.piece_id),cell=pmMatrixCell(inst.installation_id,piece.piece_id)||{};
      const mode=connector&&connector.mode||cell.mode||'available';
      html+='<td><div class="pm-cell" data-pm-matrix-inst="'+escapeHtml(inst.installation_id)+'" data-pm-matrix-piece="'+escapeHtml(piece.piece_id)+'"><strong>'+escapeHtml(mode)+'</strong><span>exec '+escapeHtml(String((connector&&connector.policy&&connector.policy.can_execute)||cell.can_execute||false))+' · mod '+escapeHtml(String((connector&&connector.policy&&connector.policy.can_modify)||cell.can_modify||false))+'</span>'+pmModeBadge(mode)+'</div></td>';
    });
    html+='</tr>';
  });
  container.innerHTML=html+'</tbody></table>';
  container.classList.toggle('pm-matrix-transposed',pmMatrixTransposed);
  const transposeBtn=document.getElementById('pm-matrix-transpose');
  if(transposeBtn){
    transposeBtn.setAttribute('aria-pressed',pmMatrixTransposed?'true':'false');
    transposeBtn.title=pmMatrixTransposed?'Volver a la vista normal':'Cambiar orientación de la matriz';
  }
  container.querySelectorAll('[data-pm-matrix-inst]').forEach(cell=>cell.addEventListener('click',()=>{
    pmSelectedInstallation=cell.getAttribute('data-pm-matrix-inst')||'';
    pmSelectedPiece=cell.getAttribute('data-pm-matrix-piece')||'';
    pmSwitchView('patch');pmRenderPatch();
  }));
}
function pmRenderPieces(){
  const container=document.getElementById('pm-pieces');
  const inventory=new Map(((nodeCache.status&&nodeCache.status.piece_inventory)||[]).map(x=>[x.piece_id,x]));
  const pieces=pmPieces().filter(p=>!pmSearch||[p.piece_id,p.type,p.scope,p.store_path].join(' ').toLowerCase().includes(pmSearch));
  container.innerHTML=pieces.map(piece=>{
    const inv=inventory.get(piece.piece_id)||{};
    const refs=pmConnectors().filter(c=>c.piece_id===piece.piece_id).length;
    return '<article class="pm-row" data-pm-piece-focus="'+escapeHtml(piece.piece_id)+'"><div class="pm-row-icon">'+escapeHtml(pmShort(piece.type))+'</div><div><h3>'+escapeHtml(piece.piece_id)+'</h3><p>'+escapeHtml(piece.store_path||inv.path||'-')+'</p><div class="pm-badges">'+pmBadge(piece.type||'piece','info')+pmBadge(piece.scope||'')+pmBadge('v'+(piece.version||'-'))+pmBadge(refs+' refs',refs?'ok':'warn')+(inv.exists?pmBadge('materializada','ok'):pmBadge('sin materializar','warn'))+'</div></div><div class="pm-row-actions"><button>Abrir en patch</button></div></article>';
  }).join('')||'<div class="pm-empty">Sin piezas visibles.</div>';
  container.querySelectorAll('[data-pm-piece-focus]').forEach(row=>row.addEventListener('click',()=>{pmSelectedPiece=row.getAttribute('data-pm-piece-focus')||'';pmSwitchView('patch');pmRenderPatch();}));
}
function pmRenderReleases(){
  const container=document.getElementById('pm-releases');
  const stable=pmStableReleases(),beta=pmPrereleases();
  const selected=pmReleaseChannel==='stable'?stable:pmReleaseChannel==='prerelease'?beta:releaseItems;
  const stableLatest=stable[0]||null,betaLatest=beta[0]||null;
  document.getElementById('pm-release-caption').textContent=releaseItems.length
    ?'stable '+(stableLatest&&stableLatest.tag_name||'-')+' · prerelease '+(betaLatest&&betaLatest.tag_name||'-')+' · selección explícita'
    :'Sin releases cargadas';
  document.getElementById('pm-release-summary').innerHTML=[
    ['Latest stable',stableLatest&&stableLatest.tag_name||'-','destino por defecto'],
    ['Latest prerelease',betaLatest&&betaLatest.tag_name||'-','solo selección explícita'],
    ['Contratos válidos',releaseItems.filter(rel=>pmReleaseContract(rel).ok).length+'/'+releaseItems.length,'ZIP + SHA256']
  ].map(s=>'<article class="pm-stat"><span>'+escapeHtml(s[0])+'</span><strong>'+escapeHtml(s[1])+'</strong><small>'+escapeHtml(s[2])+'</small></article>').join('');
  container.innerHTML=selected.map(rel=>{
    const contract=pmReleaseContract(rel);
    const asset=contract.bundle||{};
    const disabled=contract.ok?'':' disabled';
    const related=releaseJobs.find(job=>job.release&&job.release.tag_name===rel.tag_name);
    return '<article class="pm-row"><div class="pm-row-icon">⇧</div><div><h3>'+escapeHtml(rel.tag_name||rel.name||'release')+'</h3><p>'+escapeHtml(asset.name||'sin asset zip')+' · '+escapeHtml(rel.published_at?new Date(rel.published_at).toLocaleString():'sin fecha')+'</p><div class="pm-badges">'+pmBadge(rel.prerelease?'prerelease':'stable',rel.prerelease?'warn':'ok')+pmBadge(contract.ok?'ZIP + SHA256':'contrato incompleto',contract.ok?'ok':'warn')+pmBadge((rel.assets||[]).length+' assets','info')+(asset.digest?pmBadge('digest publicado','ok'):pmBadge('sin digest','warn'))+(related?pmBadge('job '+related.state,related.state==='ready'||related.state==='completed'?'ok':'info'):'')+'</div></div><div class="pm-row-actions"><button data-pm-release="install" data-tag="'+escapeHtml(rel.tag_name||'')+'"'+disabled+'>Preparar</button><button data-pm-release="separate" data-tag="'+escapeHtml(rel.tag_name||'')+'"'+disabled+'>Aparte</button><button data-pm-release="copy" data-url="'+escapeHtml(asset.browser_download_url||rel.html_url||'')+'">URL</button></div></article>';
  }).join('')||'<div class="pm-empty">No se pudieron cargar releases.</div>';
  container.querySelectorAll('[data-pm-release]').forEach(btn=>btn.addEventListener('click',async()=>{
    const action=btn.getAttribute('data-pm-release')||'',tag=btn.getAttribute('data-tag')||'';
    if(action==='copy'){copyText(btn.getAttribute('data-url')||'');return;}
    const rel=releaseItems.find(item=>item.tag_name===tag),contract=pmReleaseContract(rel);
    const selected=pmFindInstallation(pmSelectedInstallation);
    const base=selected&&selected.path||'C:\\Program Files\\BAGO';
    const target=action==='separate'?base+'-'+versionText(tag).replace(/[^A-Za-z0-9._-]/g,'_'):base;
    await pmPrepareRelease(rel,target,action==='separate'?'separate':'install');
  }));
}
function pmReleasePreflightDialog(preflight){
  const dialog=document.getElementById('pm-release-dialog');
  if(!dialog||typeof dialog.showModal!=='function'){
    return Promise.resolve(window.confirm('Crear trabajo verificado para '+preflight.release.tag_name+'?'));
  }
  document.getElementById('pm-release-dialog-title').textContent='Preflight · '+preflight.action+' · '+preflight.release.tag_name;
  document.getElementById('pm-release-dialog-target').textContent=preflight.target.path;
  const risk=document.getElementById('pm-release-dialog-risk');
  const riskValue=preflight.blockers.length?'high':preflight.warnings.length?'medium':'low';
  risk.textContent=riskValue;risk.className='pm-risk '+riskValue;
  const issues=preflight.blockers.map(item=>pmBadge(item,'bad')).concat(preflight.warnings.map(item=>pmBadge(item,'warn'))).join('')||pmBadge('sin incidencias','ok');
  document.getElementById('pm-release-dialog-body').innerHTML=''
    +'<div class="pm-preview-row"><span>Bundle</span><strong>'+escapeHtml(preflight.contract.bundle&&preflight.contract.bundle.name||'-')+'</strong></div>'
    +'<div class="pm-preview-row"><span>Integridad</span><strong>SHA256 obligatorio · firma '+escapeHtml(preflight.contract.signature?'publicada':'no publicada')+'</strong></div>'
    +'<div class="pm-preview-row"><span>Destino</span><strong>'+escapeHtml(preflight.target.exists?'existente · backup atómico':'instalación nueva')+'</strong></div>'
    +'<div class="pm-preview-row"><span>Permisos</span><strong>'+escapeHtml(preflight.target.writable?'escritura disponible':preflight.target.requires_elevation?'requiere administrador':'sin escritura')+'</strong></div>'
    +'<div class="pm-preview-row"><span>Disco</span><strong>'+escapeHtml(pmFormatBytes(preflight.disk.free_bytes))+' libres · '+escapeHtml(pmFormatBytes(preflight.disk.required_bytes))+' requeridos</strong></div>'
    +'<div class="pm-preview-row"><span>Impacto</span><strong>PieceStore y registry preservados · rollback '+escapeHtml(preflight.impact.backup_required?'requerido':'de instalación nueva')+'</strong></div>'
    +'<div class="pm-preview-row"><span>Incidencias</span><strong>'+issues+'</strong></div>'
    +'<label class="pm-preview-row"><span>Política</span><strong><input type="checkbox" id="pm-require-signature"> Exigir firma detached</strong></label>';
  const apply=dialog.querySelector('[value="apply"]');
  apply.textContent='Crear trabajo verificado';
  apply.disabled=(preflight.prepare_blockers||preflight.blockers||[]).length>0;
  return new Promise(resolve=>{
    const onClose=()=>{dialog.removeEventListener('close',onClose);resolve(dialog.returnValue==='apply');};
    dialog.addEventListener('close',onClose);
    dialog.showModal();
  });
}
async function pmInspectUninstall(target){
  const api=electronApi();
  if(!api||!api.preflightRelease){
    pmAudit('uninstall-preflight',target+' · no disponible sin Electron/backend operativo');
    showToast('Preflight de desinstalación no disponible sin Electron/backend operativo',false);
    return;
  }
  try{
    const preflight=await api.preflightRelease({release:{},target,action:'uninstall'});
    const dialog=document.getElementById('pm-release-dialog');
    document.getElementById('pm-release-dialog-title').textContent='Impacto de desinstalación';
    document.getElementById('pm-release-dialog-target').textContent=preflight.target.path;
    const risk=document.getElementById('pm-release-dialog-risk');
    const riskValue=preflight.blockers.length?'high':'medium';
    risk.textContent=riskValue;risk.className='pm-risk '+riskValue;
    const issues=preflight.blockers.map(item=>pmBadge(item,'bad')).concat(preflight.warnings.map(item=>pmBadge(item,'warn'))).join('')||pmBadge('sin bloqueos','ok');
    document.getElementById('pm-release-dialog-body').innerHTML=''
      +'<div class="pm-preview-row"><span>Runtime</span><strong>'+escapeHtml(preflight.target.current_version||'versión no resuelta')+' · '+escapeHtml(pmFormatBytes(preflight.target.size))+'</strong></div>'
      +'<div class="pm-preview-row"><span>Permisos</span><strong>'+escapeHtml(preflight.target.writable?'escritura disponible':preflight.target.requires_elevation?'requiere administrador':'sin escritura')+'</strong></div>'
      +'<div class="pm-preview-row"><span>Backup</span><strong>'+escapeHtml(pmFormatBytes(preflight.disk.required_bytes))+' requeridos para recuperación</strong></div>'
      +'<div class="pm-preview-row"><span>Preservado</span><strong>PieceStore compartido · connector registry · evidencia</strong></div>'
      +'<div class="pm-preview-row"><span>Incidencias</span><strong>'+issues+'</strong></div>';
    const apply=dialog.querySelector('[value="apply"]');
    apply.textContent='Cerrar';apply.disabled=false;
    await new Promise(resolve=>{
      const close=()=>{dialog.removeEventListener('close',close);resolve();};
      dialog.addEventListener('close',close);dialog.showModal();
    });
    pmAudit('uninstall-preflight',target+' · '+(preflight.ok?'viable':'bloqueado'));
  }catch(e){showToast('Preflight uninstall: '+e.message,false);}
}
async function pmUninstallInstallation(target){
  const api=electronApi();
  if(!window.confirm('Archivar esta instalación de BAGO?\n\n'+target))return;
  if(!pmElectronBridgeReady(api,'installAction','installAction')){
    showToast('Desinstalación no disponible sin Electron/backend operativo',false);
    return;
  }
  try{
    await api.installAction({action:'uninstall',targetDir:target,purgeState:false});
    pmAudit('uninstall',target);
    await refreshAll([]);
    await pmLoadHealth();
    showToast('Instalación archivada',true);
  }catch(e){
    showToast('Archivar instalación: '+e.message,false);
  }
}
async function pmPrepareRelease(release,target,action){
  const api=electronApi();
  if(api && (!pmElectronBridgeReady(api,'preflightRelease','preflightRelease') || !pmElectronBridgeReady(api,'startReleaseJob','startReleaseJob'))){
    return;
  }
  if(!api||!api.preflightRelease||!api.startReleaseJob){
    pmAudit('release-copy',(release&&release.tag_name||'release')+' → '+target+' · no disponible sin Electron/backend operativo');
    showToast('Preparación de release no disponible sin Electron/backend operativo',false);
    return;
  }
  try{
    let preflight=await api.preflightRelease({release,target,action,mode:'Express',require_signature:false});
    if(!await pmReleasePreflightDialog(preflight))return;
    const requireSignature=!!document.getElementById('pm-require-signature')?.checked;
    if(requireSignature){
      preflight=await api.preflightRelease({release,target,action,mode:'Express',require_signature:true});
      if(!preflight.prepare_ready)throw new Error((preflight.prepare_blockers||preflight.blockers).join(' '));
    }
    const job=await api.startReleaseJob({release,target,action,mode:'Express',require_signature:requireSignature});
    releaseJobs.unshift(job);pmSelectedJobId=job.id;
    pmAudit('release-job',job.id+' · '+release.tag_name+' → '+target);
    pmSwitchView('jobs');pmRenderJobs();pmRenderReleases();
    showToast('Trabajo de descarga verificada creado',true);
  }catch(e){showToast('Release job: '+e.message,false);}
}
function pmJobClass(job){
  if(['ready','completed'].includes(job.state))return 'ok';
  if(['failed'].includes(job.state))return 'bad';
  if(['cancelled','rolling-back','rolled-back'].includes(job.state))return 'warn';
  return 'info';
}
function pmRenderJobs(){
  const container=document.getElementById('pm-jobs');
  const summary=document.getElementById('pm-jobs-summary');
  const log=document.getElementById('pm-job-log');
  if(!container||!summary||!log)return;
  const active=releaseJobs.filter(job=>!['ready','completed','cancelled','failed','rolled-back'].includes(job.state)).length;
  const verified=releaseJobs.filter(job=>job.verification&&job.verification.actual_sha256).length;
  const rollback=releaseJobs.filter(job=>job.rollback_available).length;
  summary.innerHTML=[
    ['Activos',active,'descarga o instalación'],
    ['Verificados',verified,'SHA256 sobre bytes'],
    ['Rollback',rollback,'restauración disponible']
  ].map(item=>'<article class="pm-stat"><span>'+item[0]+'</span><strong>'+item[1]+'</strong><small>'+item[2]+'</small></article>').join('');
  document.getElementById('pm-jobs-caption').textContent=releaseJobs.length+' trabajos persistentes · '+active+' activos';
  container.innerHTML=releaseJobs.map(job=>{
    const progress=job.progress||{},percent=Math.max(0,Math.min(100,Number(progress.percent||0)));
    const actions=[];
    if(!['ready','completed','cancelled','failed','rolled-back'].includes(job.state))actions.push('<button data-pm-job-action="cancel" data-id="'+escapeHtml(job.id)+'">Cancelar</button>');
    if(['cancelled','failed'].includes(job.state))actions.push('<button data-pm-job-action="resume" data-id="'+escapeHtml(job.id)+'">Reanudar</button>');
    if(job.state==='ready')actions.push('<button data-pm-job-action="install" data-id="'+escapeHtml(job.id)+'">Instalar verificado</button>');
    if(job.rollback_available)actions.push('<button data-pm-job-action="rollback" data-id="'+escapeHtml(job.id)+'">Rollback</button>');
    actions.push('<button data-pm-job-action="logs" data-id="'+escapeHtml(job.id)+'">Logs</button>');
    if(['ready','completed','cancelled','failed','rolled-back'].includes(job.state))actions.push('<button class="danger" data-pm-job-action="delete" data-id="'+escapeHtml(job.id)+'">Archivar</button>');
    return '<article class="pm-job '+(job.id===pmSelectedJobId?'selected':'')+'"><div class="pm-job-head"><div><h3>'+escapeHtml(job.release&&job.release.tag_name||job.id)+' · '+escapeHtml(job.action||'install')+'</h3><p>'+escapeHtml(job.target||'')+'</p></div>'+pmBadge(job.state,pmJobClass(job))+'</div>'
      +'<div class="pm-progress"><span style="width:'+percent+'%"></span></div><div class="pm-badges">'+pmBadge(progress.phase||job.state,'info')+pmBadge(percent+'%')+pmBadge(pmFormatBytes(progress.transferred)+' / '+pmFormatBytes(progress.total))+(job.verification?pmBadge('SHA256 verificado','ok'):'')+(job.error?pmBadge(job.error,'bad'):'')+'</div><div class="pm-row-actions">'+actions.join('')+'</div></article>';
  }).join('')||'<div class="pm-empty">Sin trabajos todavía. Prepara una release desde Releases.</div>';
  container.querySelectorAll('[data-pm-job-action]').forEach(btn=>btn.addEventListener('click',()=>pmJobAction(btn.getAttribute('data-pm-job-action')||'',btn.getAttribute('data-id')||'')));
  pmRenderJobLog();
}
async function pmJobAction(action,id){
  const api=electronApi();if(!api)return;
  if(action==='cancel' && !pmElectronBridgeReady(api,'cancelReleaseJob','cancelReleaseJob')) return;
  if(action==='resume' && !pmElectronBridgeReady(api,'resumeReleaseJob','resumeReleaseJob')) return;
  if(action==='install' && !pmElectronBridgeReady(api,'installReleaseJob','installReleaseJob')) return;
  if(action==='rollback' && !pmElectronBridgeReady(api,'rollbackReleaseJob','rollbackReleaseJob')) return;
  if(action==='delete' && !pmElectronBridgeReady(api,'deleteReleaseJob','deleteReleaseJob')) return;
  pmSelectedJobId=id;pmRenderJobLog();
  try{
    if(action==='cancel')await api.cancelReleaseJob(id);
    if(action==='resume')await api.resumeReleaseJob(id);
    if(action==='install'){
      if(!window.confirm('Instalar el bundle verificado? Se creará backup atómico antes de modificar el destino.'))return;
      await api.installReleaseJob(id);
    }
    if(action==='rollback'){
      if(!window.confirm('Restaurar el runtime anterior mediante rollback?'))return;
      await api.rollbackReleaseJob(id);
    }
    if(action==='delete'){
      if(!api.deleteReleaseJob)throw new Error('deleteReleaseJob no disponible');
      if(!window.confirm('Archivar el trabajo persistido?\n\n'+id))return;
      await api.deleteReleaseJob(id);
      pmSelectedJobId='';
    }
    await pmLoadJobs();
  }catch(e){showToast('Job: '+e.message,false);}
}
async function pmRenderJobLog(){
  const api=electronApi(),container=document.getElementById('pm-job-log'),caption=document.getElementById('pm-job-log-caption');
  if(!container||!caption)return;
  const job=releaseJobs.find(item=>item.id===pmSelectedJobId);
  caption.textContent=job?job.id:'Selecciona un trabajo';
  if(api && !pmElectronBridgeReady(api,'releaseJobLogs','releaseJobLogs')){container.innerHTML='<div class="pm-empty">Bridge no disponible.</div>';return;}
  if(!job||!api||!api.releaseJobLogs){container.innerHTML='<div class="pm-empty">Sin log seleccionado.</div>';return;}
  try{
    const rows=await api.releaseJobLogs(job.id,300);
    container.innerHTML=(rows||[]).map(row=>'<div class="pm-job-log-row"><time>'+escapeHtml(String(row.timestamp||'').slice(11,19))+'</time><strong>'+escapeHtml(row.level||'info')+'</strong><span>'+escapeHtml(row.message||'')+'</span></div>').join('')||'<div class="pm-empty">Log vacío.</div>';
    container.scrollTop=container.scrollHeight;
  }catch(e){container.innerHTML='<div class="pm-empty">'+escapeHtml(e.message)+'</div>';}
}
async function pmLoadJobs(){
  const api=electronApi();
  if(api && !pmElectronBridgeReady(api,'listReleaseJobs','listReleaseJobs')){releaseJobs=[];pmRenderJobs();return;}
  if(!api||!api.listReleaseJobs){releaseJobs=[];pmRenderJobs();return;}
  try{releaseJobs=await api.listReleaseJobs();}catch(e){releaseJobs=[];}
  pmRenderJobs();pmRenderReleases();
}
async function pmLoadHealth(){
  const api=electronApi();
  if(api && !pmElectronBridgeReady(api,'managerHealth','managerHealth')){pmManagerHealth={checked_at:new Date().toISOString(),runtime_root:'',mutation:null,checks:[{name:'Electron bridge',ok:false,detail:'bridge missing'}]};pmRenderHealth();return;}
  if(!api||!api.managerHealth){
    pmManagerHealth={checked_at:new Date().toISOString(),runtime_root:'',mutation:null,checks:[{name:'Electron bridge',ok:false,detail:'modo web: diagnóstico local no disponible'}]};
    pmRenderHealth();
    return;
  }
  try{
    pmManagerHealth=await api.managerHealth();
  }catch(e){
    pmManagerHealth={checked_at:new Date().toISOString(),runtime_root:'',mutation:null,checks:[{name:'Manager health',ok:false,detail:e.message}]};
  }
  pmRenderHealth();
}
function pmRenderHealth(){
  const health=pmManagerHealth||{checks:[]};
  const checks=Array.isArray(health.checks)?health.checks:[];
  const healthContainer=document.getElementById('pm-health');
  const driftContainer=document.getElementById('pm-drift');
  if(!healthContainer||!driftContainer)return;
  document.getElementById('pm-health-caption').textContent=health.checked_at
    ?'Última comprobación '+new Date(health.checked_at).toLocaleTimeString()+(health.mutation||health.lifecycle_job?' · mutación activa':' · sin mutaciones activas')
    :'Sin comprobar';
  healthContainer.innerHTML=checks.map(check=>'<div class="pm-health-row"><strong>'+escapeHtml(check.name||'check')+'</strong><span>'+escapeHtml(check.detail||'')+'</span>'+pmBadge(check.ok?'ok':'fallo',check.ok?'ok':'bad')+'</div>').join('')
    +(health.mutation?'<div class="pm-health-row"><strong>Mutación Node activa</strong><code>'+escapeHtml(health.mutation.action||'')+'</code>'+pmBadge('bloqueado','warn')+'</div>':'')
    +(health.lifecycle_job?'<div class="pm-health-row"><strong>Ciclo de vida activo</strong><code>'+escapeHtml(health.lifecycle_job)+'</code>'+pmBadge('bloqueado','warn')+'</div>':'')
    +'<div class="pm-health-row"><strong>Jobs persistentes</strong><span>'+escapeHtml(String(health.release_jobs||0))+'</span>'+pmBadge('release jobs','info')+'</div>';

  const scans=existingInstallations();
  const nodes=pmNodeInstallations();
  const drift=nodes.map(node=>{
    const scan=scans.find(item=>normalizePathKey(item.path)===normalizePathKey(node.path));
    if(!scan)return {name:pmPathName(node.path),detail:'Registry sin correspondencia en runtime',status:'missing'};
    const nodeVersion=versionText(node.version||node.tag||''),scanVersion=versionText(scan.version||scan.tag||'');
    if(nodeVersion&&scanVersion&&nodeVersion!==scanVersion)return {name:pmPathName(node.path),detail:'Registry '+nodeVersion+' · disco '+scanVersion,status:'drift'};
    return {name:pmPathName(node.path),detail:scan.path+' · '+(scanVersion||nodeVersion||'versión no resuelta'),status:'aligned'};
  });
  scans.forEach(scan=>{
    if(!nodes.some(node=>normalizePathKey(node.path)===normalizePathKey(scan.path))){
      drift.push({name:pmPathName(scan.path),detail:'Detectada en runtime, ausente del registry',status:'unregistered'});
    }
  });
  driftContainer.innerHTML=drift.map(row=>'<div class="pm-health-row"><strong>'+escapeHtml(row.name)+'</strong><span>'+escapeHtml(row.detail)+'</span>'+pmBadge(row.status,row.status==='aligned'?'ok':'warn')+'</div>').join('')||'<div class="pm-empty">Sin instalaciones para comparar.</div>';
}
function pmEvidenceDetail(entry){
  const target=entry&&entry.target||{};
  const targetText=target.piece_id?target.installation_id+' → '+target.piece_id:target.scope||target.output||JSON.stringify(target);
  const before=entry&&entry.before&&entry.before.mode||'';
  const after=entry&&entry.after&&entry.after.mode||'';
  return [entry.actor||'?',entry.result||'?',targetText,before&&after?before+' → '+after:''].filter(Boolean).join(' · ');
}
function pmLocalAuditSnapshot(){
  return {
    unavailable:true,
    checked_at:new Date().toISOString(),
    error:'Auditoría no disponible sin Electron/backend operativo',
    project:null,
    bago:null,
    events:[]
  };
}
async function pmLoadAudit(){
  const api=electronApi();
  if(api&&api.projectAudit&&api.bagoAudit){
    try{
      const [project,bago]=await Promise.all([api.projectAudit(),api.bagoAudit()]);
      const events=api.eventLedger?await api.eventLedger(80):[];
      pmAuditState={project,bago,events:Array.isArray(events&&events.entries)?events.entries:events||[],loaded_at:new Date().toISOString()};
    }catch(e){
      pmAuditState={...pmLocalAuditSnapshot(),loaded_at:new Date().toISOString(),error:e.message};
    }
  }else{
    pmAuditState={...pmLocalAuditSnapshot(),loaded_at:new Date().toISOString()};
  }
  pmRenderAudit();
}
function pmRenderAudit(){
  const summary=document.getElementById('pm-audit-summary');
  const metricsSlot=document.getElementById('pm-audit-metrics');
  const projectSlot=document.getElementById('pm-audit-project');
  const bagoSlot=document.getElementById('pm-audit-bago');
  const eventsSlot=document.getElementById('pm-audit-events');
  const caption=document.getElementById('pm-audit-caption');
  const metricsToggle=document.getElementById('pm-audit-toggle-metrics');
  if(!summary||!metricsSlot||!projectSlot||!bagoSlot||!eventsSlot||!caption)return;
  if(pmAuditState&&pmAuditState.unavailable){
    summary.innerHTML='<div class="pm-audit-callout"><strong>Auditoría no disponible</strong><p>'+escapeHtml(pmAuditState.error||'Sin Electron/backend operativo.')+'</p></div>';
    metricsSlot.innerHTML='<div class="pm-audit-callout"><strong>Métricas</strong><p>No disponibles sin Electron/backend operativo.</p></div>';
    projectSlot.innerHTML='<div class="pm-empty">Auditoría de proyecto no disponible.</div>';
    bagoSlot.innerHTML='<div class="pm-empty">Auditoría de BAGO no disponible.</div>';
    eventsSlot.innerHTML='<div class="pm-empty">Ledger de eventos no disponible.</div>';
    caption.textContent='Auditoría no disponible';
    if(metricsToggle){
      metricsToggle.classList.remove('active');
      metricsToggle.textContent='Métricas';
    }
    return;
  }
  const project=pmAuditState.project||pmLocalAuditSnapshot().project;
  const bago=pmAuditState.bago||pmLocalAuditSnapshot().bago;
  const events=Array.isArray(pmAuditState.events)?pmAuditState.events:[];
  const projectFindings=Array.isArray(project.findings)?project.findings:[];
  const bagoFindings=Array.isArray(bago.findings)?bago.findings:[];
  const activeLabel=pmAuditTab==='project'?'Proyecto':pmAuditTab==='bago'?'BAGO':'Eventos';
  summary.innerHTML='<div class="pm-audit-callout"><strong>'+escapeHtml(activeLabel)+'</strong><p>Última carga: '+escapeHtml(pmAuditState.loaded_at?new Date(pmAuditState.loaded_at).toLocaleString('es-ES'):'pendiente')+' · Proyecto '+escapeHtml(String(project.summary&&project.summary.findings||projectFindings.length))+' · BAGO '+escapeHtml(String(bago.summary&&bago.summary.findings||bagoFindings.length))+' · Eventos '+escapeHtml(String(events.length))+'</p></div>';
  metricsSlot.innerHTML='<div class="pm-audit-callout"><strong>Métricas</strong><p>Resumen cuantitativo separado de los hallazgos para mantener cada pestaña enfocada en una sola decisión.</p><div class="pm-audit-list">'
    +pmAuditMetric('Proyecto', project.summary&&project.summary.findings||projectFindings.length)
    +pmAuditMetric('Proyecto alto', project.summary&&project.summary.high||projectFindings.filter(item=>item.severity==='high').length)
    +pmAuditMetric('BAGO', bago.summary&&bago.summary.findings||bagoFindings.length)
    +pmAuditMetric('Eventos', events.length)
    +'</div></div>';
  metricsSlot.classList.toggle('open',!!pmAuditMetricsOpen);
  if(metricsToggle){
    metricsToggle.classList.toggle('active',!!pmAuditMetricsOpen);
    metricsToggle.textContent=pmAuditMetricsOpen?'Ocultar métricas':'Métricas';
  }

  const tabButtons=document.querySelectorAll('[data-audit-tab]');
  tabButtons.forEach(btn=>btn.classList.toggle('active',(btn.getAttribute('data-audit-tab')||'')===pmAuditTab));

  const renderProject=()=>{
    const lead=projectFindings[0]||null;
    const leadTitle=lead?((lead.title||lead.code||'Hallazgo principal')):'Sin bloqueos';
    const leadDetail=lead?(lead.detail||'Revisar este punto primero.'):('No hay hallazgos bloqueantes en el proyecto.');
    projectSlot.innerHTML='<div class="pm-audit-header"><div><h3>Proyecto</h3><p>'+escapeHtml(project.root||'')+'</p></div><div class="pm-actions"><button class="pm-btn" id="pm-audit-project-export">Exportar</button></div></div>'
      +'<div class="pm-audit-callout"><strong>'+escapeHtml(leadTitle)+'</strong><p>'+escapeHtml(leadDetail)+'</p><div class="pm-audit-actions">'+pmAuditQuickActions('project',project)+'</div></div>'
      +'<div class="pm-audit-findings">'+(projectFindings.map(pmAuditFindingHtml).join('')||'<div class="pm-empty">Sin hallazgos de proyecto.</div>')+'</div>';
    const exportBtn=document.getElementById('pm-audit-project-export');
    if(exportBtn)exportBtn.addEventListener('click',()=>pmAuditState&&pmAuditState.unavailable?showToast('Exportación no disponible sin Electron/backend operativo',false):pmDownloadJson('bago-project-audit.json',project));
  };
  const renderBago=()=>{
    const health=bago.health||{};
    const startup=health.startup||{};
    const checks=Array.isArray(health.checks)?health.checks:[];
    const missing=Array.isArray(startup.missing_core)?startup.missing_core:[];
    const lead=missing[0]||null;
    const leadTitle=lead?('Falta '+(lead.label||lead.id||'dependencia')):(bagoFindings[0]&&(bagoFindings[0].title||bagoFindings[0].code)||'Estado BAGO');
    const leadDetail=lead?(lead.detail||lead.install_command||'Instalar ahora'):(bagoFindings[0]&&(bagoFindings[0].detail||'Sin incidencias críticas.'));
    bagoSlot.innerHTML='<div class="pm-audit-header"><div><h3>BAGO</h3><p>'+escapeHtml(bago.runtime_root||bago.repo_root||'')+'</p></div><div class="pm-actions"><button class="pm-btn" id="pm-audit-bago-export">Exportar</button></div></div>'
      +'<div class="pm-audit-callout"><strong>'+escapeHtml(leadTitle)+'</strong><p>'+escapeHtml(leadDetail)+'</p><div class="pm-audit-actions">'+pmAuditQuickActions('bago',bago)+'</div></div>'
      +'<div class="pm-audit-findings">'+(bagoFindings.map(pmAuditFindingHtml).join('')||'<div class="pm-empty">Sin hallazgos de BAGO.</div>')+'</div>'
      +'<div class="pm-audit-list" style="margin-top:8px">'
      +(checks.map(check=>'<div class="pm-audit-event"><time>'+escapeHtml(bago.checked_at?new Date(bago.checked_at).toLocaleTimeString('es-ES',{hour:'2-digit',minute:'2-digit'}):'--:--')+'</time><strong>'+escapeHtml(check.name||'check')+'</strong><span>'+escapeHtml(check.detail||'')+'</span><code>'+escapeHtml(check.ok?'ok':'fail')+'</code></div>').join('')||'<div class="pm-empty">Sin checks de salud.</div>')
      +'</div>';
    const exportBtn=document.getElementById('pm-audit-bago-export');
    if(exportBtn)exportBtn.addEventListener('click',()=>pmAuditState&&pmAuditState.unavailable?showToast('Exportación no disponible sin Electron/backend operativo',false):pmDownloadJson('bago-runtime-audit.json',bago));
  };
  const renderEvents=()=>{
    const interactionLog=typeof window.__bagoInteractionLogRead==='function'?window.__bagoInteractionLogRead():[];
    const sessionRows=(pmSessionAudit||[]).map(row=>({
      timestamp:row.time?new Date().toISOString().slice(0,10)+'T'+row.time+':00Z':new Date().toISOString(),
      scope:'session',
      action:row.action||'event',
      detail:row.detail||'',
      source:'pmSessionAudit'
    }));
    const interactionRows=(interactionLog||[]).slice(0,80).map(entry=>({
      timestamp:entry.ts,
      scope:'ui',
      action:entry.event||'event',
      detail:entry.payload&&entry.payload.target&&entry.payload.target.text || entry.payload&&entry.payload.target&&entry.payload.target.id || 'interacción',
      source:'interaction-log'
    }));
    const combined=(events||[]).concat(sessionRows).concat(interactionRows).sort((a,b)=>String(b.timestamp||'').localeCompare(String(a.timestamp||'')));
    const top=combined[0]||null;
    const topLabel=top?((top.scope||'evento')+' · '+(top.action||'evento')):'Sin eventos';
    const topDetail=top?(top.detail||''):'No hay eventos para mostrar.';
    eventsSlot.innerHTML='<div class="pm-audit-header"><div><h3>Eventos</h3><p>Ledger unificado de UI, runtime y Node Control</p></div><div class="pm-actions"><button class="pm-btn" id="pm-audit-events-export">Exportar</button></div></div>'
      +'<div class="pm-audit-callout"><strong>'+escapeHtml(topLabel)+'</strong><p>'+escapeHtml(topDetail)+'</p><div class="pm-audit-actions">'+pmAuditQuickActions('events',{combined})+'</div></div>'
      +'<div class="pm-audit-list">'+(combined.slice(0,12).map(pmAuditEventHtml).join('')||'<div class="pm-empty">Sin eventos todavía.</div>')+'</div>';
    const exportBtn=document.getElementById('pm-audit-events-export');
    if(exportBtn)exportBtn.addEventListener('click',()=>pmDownloadJson('bago-event-ledger.json',combined));
  };
  projectSlot.classList.toggle('active',pmAuditTab==='project');
  bagoSlot.classList.toggle('active',pmAuditTab==='bago');
  eventsSlot.classList.toggle('active',pmAuditTab==='events');
  caption.textContent=pmAuditTab==='project'
    ?'Auditoría de proyecto'
    :pmAuditTab==='bago'
      ?'Auditoría de BAGO'
      :'Ledger de eventos';
  renderProject();
  renderBago();
  renderEvents();
  document.querySelectorAll('[data-audit-action]').forEach(btn=>btn.addEventListener('click',async()=>pmHandleAuditAction(btn.getAttribute('data-audit-action')||'')));
}
async function pmHandleAuditAction(action){
  const api=electronApi();
  if(action==='project-export') return pmAuditState&&pmAuditState.unavailable?showToast('Exportación no disponible sin Electron/backend operativo',false):pmDownloadJson('bago-project-audit.json',pmAuditState.project);
  if(action==='bago-export') return pmAuditState&&pmAuditState.unavailable?showToast('Exportación no disponible sin Electron/backend operativo',false):pmDownloadJson('bago-runtime-audit.json',pmAuditState.bago);
  if(action==='events-export') return pmAuditState&&pmAuditState.unavailable?showToast('Exportación no disponible sin Electron/backend operativo',false):pmDownloadJson('bago-event-ledger.json',Array.isArray(pmAuditState.events)?pmAuditState.events:[]);
  if(action==='events-refresh') return pmLoadAudit();
  if(action==='events-filter-ui') return showToast('Usa los filtros del ledger en la vista de eventos',true);
  if(action==='bago-open-health') return pmSwitchView('health');
  if(action==='bago-open-jobs') return pmSwitchView('jobs');
  if(action==='bago-install-missing'){
    const missing=((pmAuditState.bago&&pmAuditState.bago.health&&pmAuditState.bago.health.startup&&pmAuditState.bago.health.startup.missing_core)||[]).filter(item=>item.install_command);
    if(!missing.length) return showToast('No hay dependencias instalables',true);
    if(api && !pmElectronBridgeReady(api,'dependencyAction','dependencyAction')) return;
    if(!api) return showToast('Instalación no disponible sin Electron/backend operativo',false);
    await api.dependencyAction({action:'install-all',targets:missing.map(item=>item.id)});
    await pmLoadAudit();
    return showToast('Instaladores lanzados',true);
  }
  if(action==='project-fix-version') return pmSwitchView('system');
  if(action==='project-fix-duplicates') return pmSwitchView('patch');
  if(action==='project-fix-missing') return pmSwitchView('installations');
}
function renderPatchManager(){
  pmEnsureSelection();
  const status=nodeCache.status||{};
  const detected=existingInstallations().length;
  document.getElementById('pm-status').textContent=status.installations
    ?status.installations+' instalaciones registry · '+detected+' detectadas en runtime · '+status.pieces+' piezas · '+status.connectors+' connectors · '+releaseItems.length+' releases'
    :'Cargando runtime, releases y Node Control...';
  pmRenderStats();pmRenderPatch();pmRenderInstallations();pmRenderMatrix();pmRenderPieces();pmRenderReleases();pmRenderJobs();pmRenderHealth();pmRenderAudit();
  if(typeof pmRenderControl==='function')pmRenderControl();
  if(typeof pmRenderRoute==='function')pmRenderRoute();
}
function pmInit(){
  document.querySelectorAll('[data-pm-view]').forEach(btn=>btn.addEventListener('click',()=>pmSwitchView(btn.getAttribute('data-pm-view')||'patch')));
  document.querySelectorAll('[data-audit-tab]').forEach(btn=>btn.addEventListener('click',async()=>{
    pmAuditTab=btn.getAttribute('data-audit-tab')||'project';
    localStorage.setItem('bago.pm.audit.tab',pmAuditTab);
    await pmLoadAudit();
  }));
  const metricsToggle=document.getElementById('pm-audit-toggle-metrics');
  if(metricsToggle)metricsToggle.addEventListener('click',()=>{
    pmAuditMetricsOpen=!pmAuditMetricsOpen;
    localStorage.setItem('bago.pm.audit.metrics',pmAuditMetricsOpen?'1':'0');
    pmRenderAudit();
  });
  document.getElementById('pm-search').addEventListener('input',ev=>{pmSearch=ev.target.value.trim().toLowerCase();renderPatchManager();});
  document.getElementById('pm-mode-filter').addEventListener('change',ev=>{window.__bagoInteractionLogPush && window.__bagoInteractionLogPush('filter-change', { id: 'pm-mode-filter', value: ev.target.value });pmModeFilter=ev.target.value;pmRenderPatch();});
  document.getElementById('pm-install-filter').addEventListener('change',ev=>{window.__bagoInteractionLogPush && window.__bagoInteractionLogPush('filter-change', { id: 'pm-install-filter', value: ev.target.value });pmSelectedInstallation=ev.target.value;pmRenderPatch();});
  document.getElementById('pm-release-channel').addEventListener('change',ev=>{window.__bagoInteractionLogPush && window.__bagoInteractionLogPush('filter-change', { id: 'pm-release-channel', value: ev.target.value });pmReleaseChannel=ev.target.value;pmRenderReleases();});
  const matrixPieceSort=document.getElementById('pm-matrix-piece-sort');
  if(matrixPieceSort) matrixPieceSort.addEventListener('change',()=>pmRenderMatrix());
  const matrixInstallSort=document.getElementById('pm-matrix-install-sort');
  if(matrixInstallSort) matrixInstallSort.addEventListener('change',()=>pmRenderMatrix());
  const matrixDirection=document.getElementById('pm-matrix-direction');
  if(matrixDirection) matrixDirection.addEventListener('change',()=>pmRenderMatrix());
  const matrixTranspose=document.getElementById('pm-matrix-transpose');
  if(matrixTranspose) matrixTranspose.addEventListener('click',pmTransposeMatrix);
  const webChatBtn=document.getElementById('pm-open-web-chat');
  if(webChatBtn) webChatBtn.addEventListener('click',()=>typeof openWebChat==='function' ? openWebChat() : showToast('Abrir BAGO Web solo disponible en Electron',false));
  const cliChatBtn=document.getElementById('pm-open-cli-chat');
  if(cliChatBtn) cliChatBtn.addEventListener('click',()=>typeof openCliChat==='function' ? openCliChat() : showToast('Abrir BAGO CLI solo disponible en Electron',false));
  const heroWebBtn=document.getElementById('pm-hero-open-web');
  if(heroWebBtn) heroWebBtn.addEventListener('click',()=>typeof openWebChat==='function' ? openWebChat() : showToast('Abrir BAGO Web solo disponible en Electron',false));
  const heroCliBtn=document.getElementById('pm-hero-open-cli');
  if(heroCliBtn) heroCliBtn.addEventListener('click',()=>typeof openCliChat==='function' ? openCliChat() : showToast('Abrir BAGO CLI solo disponible en Electron',false));
  document.getElementById('pm-jobs-refresh').addEventListener('click',pmLoadJobs);
  document.getElementById('pm-health-refresh').addEventListener('click',pmLoadHealth);
  const auditRefresh=document.getElementById('pm-audit-refresh');
  if(auditRefresh) auditRefresh.addEventListener('click',pmLoadAudit);
  const auditExport=document.getElementById('pm-audit-export');
  if(auditExport) auditExport.addEventListener('click',()=>pmDownloadJson('bago-audit-state.json',pmAuditState));
  document.querySelectorAll('[data-audit-action]').forEach(btn=>btn.addEventListener('click',async()=>pmHandleAuditAction(btn.getAttribute('data-audit-action')||'')));
  document.getElementById('pm-refresh').addEventListener('click',async()=>{pmAudit('refresh','Runtime, releases, salud y Node Control');await Promise.all([refreshAll([]),loadNodeData(),pmLoadHealth(),pmLoadAudit()]);});
  document.getElementById('pm-reset-layout').addEventListener('click',()=>{
    Object.keys(localStorage).filter(k=>k.startsWith('bago.pm.pos.')).forEach(k=>localStorage.removeItem(k));
    pmAudit('layout','Posiciones restablecidas');pmRenderPatch();
  });
  document.getElementById('pm-scan-manual').addEventListener('click',async()=>{
    const path=window.prompt('Ruta BAGO a detectar:','');
    if(path){pmAudit('scan','Ruta manual: '+path);await refreshAll([path]);}
  });
  const validateBtn=document.getElementById('pm-validate');
  if(validateBtn)validateBtn.addEventListener('click',async()=>{
    const api=electronApi();
    if(api && !pmElectronBridgeReady(api,'runNodeValidate','runNodeValidate')) return;
    if(!api||!api.runNodeValidate){
      const result=pmLocalNodeValidate();
      pmAudit('validate',result.error||'Validación no disponible');
      showToast(result.error||'Validación no disponible',false);
      return;
    }
    try{const result=await api.runNodeValidate();pmAudit('validate',result&&result.ok?'Node Control válido':'Validación con fallos');showToast(result&&result.ok?'Node Control válido':'Validación con fallos',!!(result&&result.ok));}catch(e){showToast(e.message,false);}
  });
  const exportBtn=document.getElementById('pm-export');
  if(exportBtn)exportBtn.addEventListener('click',async()=>{
    if(!window.confirm('Exportar el estado Node Control a node-export.json?'))return;
    const api=electronApi();
    if(api && !pmElectronBridgeReady(api,'runNodeCommand','runNodeCommand')) return;
    if(!api||!api.runNodeCommand){
      showToast('Exportación no disponible sin Electron/backend operativo',false);
      return;
    }
    try{await api.runNodeCommand(['node','export','--output','node-export.json']);pmAudit('export','node-export.json');showToast('Estado exportado',true);}catch(e){showToast(e.message,false);}
  });
  window.addEventListener('resize',pmUpdatePatchLines);
  renderPatchManager();
  pmLoadHealth();
  pmLoadJobs();
  pmLoadAudit();
  const api=electronApi();
  if(api&&api.onReleaseJobChanged)api.onReleaseJobChanged(job=>{
    if(job&&job.deleted){
      releaseJobs=releaseJobs.filter(item=>item.id!==job.id);
      if(pmSelectedJobId===job.id)pmSelectedJobId='';
      pmRenderJobs();pmRenderReleases();pmRenderHealth();
      return;
    }
    const index=releaseJobs.findIndex(item=>item.id===job.id);
    if(index>=0)releaseJobs[index]=job;else releaseJobs.unshift(job);
    pmRenderJobs();pmRenderReleases();pmRenderHealth();
  });
}
