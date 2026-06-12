// ── Patch-first manager experience ───────────────────────────
const PM_VIEW_TITLES={
  patch:'Patch Bay',
  installations:'Instalaciones',
  matrix:'Matriz',
  pieces:'PieceStore',
  releases:'Releases',
  jobs:'Trabajos de release',
  sessions:'Sesiones',
  health:'Salud operativa',
  audit:'Auditoría'
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
let pmActiveView='patch';
let pmSelectedInstallation='';
let pmSelectedPiece='';
let pmSearch='';
let pmModeFilter='';
let pmReleaseChannel='stable';
let pmMatrixPieceSort='type';
let pmMatrixInstallSort='profile';
let pmMatrixDirection='asc';
let pmMatrixTransposed=false;
try{
  const storedMatrix=JSON.parse(localStorage.getItem('bago.pm.matrix.preferences')||'null');
  if(storedMatrix){
    pmMatrixPieceSort=storedMatrix.pieceSort||pmMatrixPieceSort;
    pmMatrixInstallSort=storedMatrix.installSort||pmMatrixInstallSort;
    pmMatrixDirection=storedMatrix.direction||pmMatrixDirection;
    pmMatrixTransposed=!!storedMatrix.transposed;
  }
}catch{}
let pmManagerHealth=null;
let pmMutationBusy=false;
let pmSelectedJobId='';
let pmSessionAudit=[{time:new Date().toLocaleTimeString('es-ES',{hour:'2-digit',minute:'2-digit'}),action:'manager',detail:'Gestor Patch-first iniciado'}];

function pmModeClass(mode){return String(mode||'available').replace(/\s+/g,'-');}
function pmFormatBytes(value){
  const bytes=Number(value||0);
  if(!bytes)return '0 B';
  const units=['B','KB','MB','GB','TB'];
  const index=Math.min(units.length-1,Math.floor(Math.log(bytes)/Math.log(1024)));
  return (bytes/Math.pow(1024,index)).toFixed(index?1:0)+' '+units[index];
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
  const ordered=[...bundles].sort((a,b)=>{
    const aRuntime=/^bago-v/i.test(String(a.name||''));
    const bRuntime=/^bago-v/i.test(String(b.name||''));
    if(aRuntime!==bRuntime) return aRuntime ? -1 : 1;
    const aTime=new Date(a.updated_at||a.created_at||0).getTime();
    const bTime=new Date(b.updated_at||b.created_at||0).getTime();
    if(aTime!==bTime) return bTime-aTime;
    return String(a.name||'').localeCompare(String(b.name||''));
  });
  const exactChecksum=bundle=>assets.find(asset=>String(asset.name||'').toLowerCase()===(bundle.name+'.sha256').toLowerCase())||null;
  const bundle=ordered.find(item=>exactChecksum(item))||ordered[0]||null;
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
function pmSwitchView(view){
  pmActiveView=view;
  document.querySelectorAll('[data-pm-view]').forEach(b=>b.classList.toggle('active',b.getAttribute('data-pm-view')===view));
  document.querySelectorAll('.pm-view').forEach(v=>v.classList.toggle('active',v.id==='pm-view-'+view));
  document.getElementById('pm-title').textContent=PM_VIEW_TITLES[view]||'BAGO Manager';
  if(view==='patch')setTimeout(()=>typeof pmPatchSurface!=='undefined'&&pmPatchSurface==='chain'&&typeof pmRenderPatchChain==='function'?pmRenderPatchChain():pmUpdatePatchLines(),30);
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
    ['Instalaciones',status.installations||pmNodeInstallations().length,scanRows.length?'detección local + registry':'registry'],
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
  if(typeof pmPatchSurface!=='undefined'&&pmPatchSurface==='chain'&&typeof pmRenderPatchChain==='function'){
    pmRenderPatchChain();
    return;
  }
  document.getElementById('pm-patch-layout').classList.remove('chain-mode');
  document.getElementById('pm-stage').classList.remove('chain-view');
  document.getElementById('pm-install-filter').hidden=false;
  document.getElementById('pm-detail-title').textContent='Connector';
  const stage=document.getElementById('pm-stage');
  stage.style.height='650px';
  stage.style.minWidth='';
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
  const container=document.getElementById('pm-detail');
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
  if(!api||!api.runNodeValidate)return {ok:false,error:'validación solo disponible en Electron'};
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
  const hero=document.getElementById('pm-hero-bago-ready');
  if(hero){hero.style.display=filtered.length>0?'block':'none';}
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
      +'<button data-pm-install-action="launch" data-path="'+escapeHtml(inst.path)+'">Ign</button><button data-pm-install-action="update" data-path="'+escapeHtml(inst.path)+'">Actualizar</button><button data-pm-install-action="uninstall-impact" data-path="'+escapeHtml(inst.path)+'">Impacto</button></div></article>';
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
  }));
}
function pmRenderMatrix(){
  const container=document.getElementById('pm-matrix');
  const direction=pmMatrixDirection==='desc'?-1:1;
  const compare=(a,b)=>String(a||'').localeCompare(String(b||''),'es',{numeric:true,sensitivity:'base'})*direction;
  const pieceValue=piece=>pmMatrixPieceSort==='id'?piece.piece_id:pmMatrixPieceSort==='scope'?piece.scope:pmMatrixPieceSort==='refs'?pmConnectors().filter(c=>c.piece_id===piece.piece_id).length:piece.type;
  const installValue=inst=>pmMatrixInstallSort==='name'?pmPathName(inst.path):pmMatrixInstallSort==='mode'?inst.mode:inst.profile||inst.mode;
  const installs=[...pmNodeInstallations()].sort((a,b)=>compare(installValue(a),installValue(b))||compare(a.installation_id,b.installation_id));
  const pieces=pmPieces().filter(p=>!pmSearch||[p.piece_id,p.type,p.scope].join(' ').toLowerCase().includes(pmSearch)).sort((a,b)=>compare(pieceValue(a),pieceValue(b))||compare(a.piece_id,b.piece_id));
  if(!installs.length||!pieces.length){container.innerHTML='<div class="pm-empty">Matriz sin datos.</div>';return;}
  const cellHtml=(inst,piece)=>{
    const connector=pmFindConnector(inst.installation_id,piece.piece_id),cell=pmMatrixCell(inst.installation_id,piece.piece_id)||{};
    const mode=connector&&connector.mode||cell.mode||'available';
    return '<td><div class="pm-cell" data-pm-matrix-inst="'+escapeHtml(inst.installation_id)+'" data-pm-matrix-piece="'+escapeHtml(piece.piece_id)+'"><strong>'+escapeHtml(mode)+'</strong><span>exec '+escapeHtml(String((connector&&connector.policy&&connector.policy.can_execute)||cell.can_execute||false))+' · mod '+escapeHtml(String((connector&&connector.policy&&connector.policy.can_modify)||cell.can_modify||false))+'</span>'+pmModeBadge(mode)+'</div></td>';
  };
  let html='<table class="pm-matrix"><thead><tr>';
  if(pmMatrixTransposed){
    html+='<th>Instalación</th>'+pieces.map(piece=>'<th>'+escapeHtml(piece.piece_id)+'<br><span>'+escapeHtml(piece.type||'')+' · '+escapeHtml(piece.scope||'')+'</span></th>').join('')+'</tr></thead><tbody>';
    installs.forEach(inst=>{html+='<tr><td><strong>'+escapeHtml(pmPathName(inst.path))+'</strong><br><span>'+escapeHtml(inst.profile||inst.mode||'')+'</span></td>'+pieces.map(piece=>cellHtml(inst,piece)).join('')+'</tr>';});
  }else{
    html+='<th>Pieza</th>'+installs.map(inst=>'<th>'+escapeHtml(pmPathName(inst.path))+'<br><span>'+escapeHtml(inst.profile||inst.mode||'')+'</span></th>').join('')+'</tr></thead><tbody>';
    pieces.forEach(piece=>{html+='<tr><td><strong>'+escapeHtml(piece.piece_id)+'</strong><br><span>'+escapeHtml(piece.type||'')+' · '+escapeHtml(piece.scope||'')+'</span></td>'+installs.map(inst=>cellHtml(inst,piece)).join('')+'</tr>';});
  }
  container.innerHTML=html+'</tbody></table>';
  container.querySelectorAll('[data-pm-matrix-inst]').forEach(cell=>cell.addEventListener('click',()=>{
    pmSelectedInstallation=cell.getAttribute('data-pm-matrix-inst')||'';
    pmSelectedPiece=cell.getAttribute('data-pm-matrix-piece')||'';
    pmSwitchView('patch');pmRenderPatch();
  }));
}
function pmPersistMatrixPreferences(){
  localStorage.setItem('bago.pm.matrix.preferences',JSON.stringify({pieceSort:pmMatrixPieceSort,installSort:pmMatrixInstallSort,direction:pmMatrixDirection,transposed:pmMatrixTransposed}));
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
  if(!api||!api.preflightRelease){showToast('Preflight disponible solo en Electron',false);return;}
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
async function pmPrepareRelease(release,target,action){
  const api=electronApi();
  if(!api||!api.preflightRelease||!api.startReleaseJob){
    await copyText(installCommand(release&&release.tag_name||'',target));
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
    return '<article class="pm-job '+(job.id===pmSelectedJobId?'selected':'')+'"><div class="pm-job-head"><div><h3>'+escapeHtml(job.release&&job.release.tag_name||job.id)+' · '+escapeHtml(job.action||'install')+'</h3><p>'+escapeHtml(job.target||'')+'</p></div>'+pmBadge(job.state,pmJobClass(job))+'</div>'
      +'<div class="pm-progress"><span style="width:'+percent+'%"></span></div><div class="pm-badges">'+pmBadge(progress.phase||job.state,'info')+pmBadge(percent+'%')+pmBadge(pmFormatBytes(progress.transferred)+' / '+pmFormatBytes(progress.total))+(job.verification?pmBadge('SHA256 verificado','ok'):'')+(job.error?pmBadge(job.error,'bad'):'')+'</div><div class="pm-row-actions">'+actions.join('')+'</div></article>';
  }).join('')||'<div class="pm-empty">Sin trabajos todavía. Prepara una release desde Releases.</div>';
  container.querySelectorAll('[data-pm-job-action]').forEach(btn=>btn.addEventListener('click',()=>pmJobAction(btn.getAttribute('data-pm-job-action')||'',btn.getAttribute('data-id')||'')));
  pmRenderJobLog();
}
async function pmJobAction(action,id){
  const api=electronApi();if(!api)return;
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
    await pmLoadJobs();
  }catch(e){showToast('Job: '+e.message,false);}
}
async function pmRenderJobLog(){
  const api=electronApi(),container=document.getElementById('pm-job-log'),caption=document.getElementById('pm-job-log-caption');
  if(!container||!caption)return;
  const job=releaseJobs.find(item=>item.id===pmSelectedJobId);
  caption.textContent=job?job.id:'Selecciona un trabajo';
  if(!job||!api||!api.releaseJobLogs){container.innerHTML='<div class="pm-empty">Sin log seleccionado.</div>';return;}
  try{
    const rows=await api.releaseJobLogs(job.id,300);
    container.innerHTML=(rows||[]).map(row=>'<div class="pm-job-log-row"><time>'+escapeHtml(String(row.timestamp||'').slice(11,19))+'</time><strong>'+escapeHtml(row.level||'info')+'</strong><span>'+escapeHtml(row.message||'')+'</span></div>').join('')||'<div class="pm-empty">Log vacío.</div>';
    container.scrollTop=container.scrollHeight;
  }catch(e){container.innerHTML='<div class="pm-empty">'+escapeHtml(e.message)+'</div>';}
}
async function pmLoadJobs(){
  const api=electronApi();
  if(!api||!api.listReleaseJobs){releaseJobs=[];pmRenderJobs();return;}
  try{releaseJobs=await api.listReleaseJobs();}catch(e){releaseJobs=[];}
  pmRenderJobs();pmRenderReleases();
}
async function pmLoadHealth(){
  const api=electronApi();
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
    if(!scan)return {name:pmPathName(node.path),detail:'Registry sin correspondencia en detección local',status:'missing'};
    const nodeVersion=versionText(node.version||node.tag||''),scanVersion=versionText(scan.version||scan.tag||'');
    if(nodeVersion&&scanVersion&&nodeVersion!==scanVersion)return {name:pmPathName(node.path),detail:'Registry '+nodeVersion+' · disco '+scanVersion,status:'drift'};
    return {name:pmPathName(node.path),detail:scan.path+' · '+(scanVersion||nodeVersion||'versión no resuelta'),status:'aligned'};
  });
  scans.forEach(scan=>{
    if(!nodes.some(node=>normalizePathKey(node.path)===normalizePathKey(scan.path))){
      drift.push({name:pmPathName(scan.path),detail:'Detectada localmente, ausente del registry',status:'unregistered'});
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
function pmRenderAudit(){
  const container=document.getElementById('pm-audit');
  if(!container)return;
  const evidence=nodeCache.status&&nodeCache.status.evidence_file||'Evidence ledger no cargado';
  const realEntries=Array.isArray(nodeCache.evidence&&nodeCache.evidence.entries)?nodeCache.evidence.entries:[];
  document.getElementById('pm-evidence-path').textContent=evidence;
  const real=realEntries.map(entry=>'<div class="pm-audit-row"><time>'+escapeHtml(String(entry.timestamp||'').slice(11,19))+'</time><strong>'+escapeHtml(entry.action||'event')+'</strong><span>'+escapeHtml(pmEvidenceDetail(entry))+'</span></div>');
  const session=pmSessionAudit.map(row=>'<div class="pm-audit-row"><time>'+escapeHtml(row.time)+'</time><strong>'+escapeHtml(row.action)+'</strong><span>'+escapeHtml(row.detail)+'</span></div>');
  container.innerHTML=real.concat(session).join('')||'<div class="pm-empty">Sin evidencia todavía.</div>';
}
function renderPatchManager(){
  pmEnsureSelection();
  const status=nodeCache.status||{};
  const detected=existingInstallations().length;
  document.getElementById('pm-status').textContent=status.installations
    ?status.installations+' instalaciones registry · '+detected+' detectadas localmente · '+status.pieces+' piezas · '+status.connectors+' connectors · '+releaseItems.length+' releases'
    :'Cargando detección local, releases y Node Control...';
  pmRenderStats();pmRenderPatch();pmRenderInstallations();pmRenderMatrix();pmRenderPieces();pmRenderReleases();pmRenderJobs();pmRenderHealth();pmRenderAudit();
}
function pmInit(){
  document.querySelectorAll('[data-pm-view]').forEach(btn=>btn.addEventListener('click',()=>pmSwitchView(btn.getAttribute('data-pm-view')||'patch')));
  document.getElementById('pm-search').addEventListener('input',ev=>{pmSearch=ev.target.value.trim().toLowerCase();renderPatchManager();});
  document.getElementById('pm-mode-filter').addEventListener('change',ev=>{pmModeFilter=ev.target.value;pmRenderPatch();});
  document.getElementById('pm-open-web-chat').addEventListener('click',openWebChat);
  document.getElementById('pm-open-cli-chat').addEventListener('click',openCliChat);
  const heroWeb=document.getElementById('pm-hero-open-web');
  const heroCli=document.getElementById('pm-hero-open-cli');
  if(heroWeb) heroWeb.addEventListener('click',openWebChat);
  if(heroCli) heroCli.addEventListener('click',openCliChat);
  document.getElementById('pm-install-filter').addEventListener('change',ev=>{pmSelectedInstallation=ev.target.value;pmRenderPatch();});
  document.getElementById('pm-matrix-piece-sort').value=pmMatrixPieceSort;
  document.getElementById('pm-matrix-install-sort').value=pmMatrixInstallSort;
  document.getElementById('pm-matrix-direction').value=pmMatrixDirection;
  document.getElementById('pm-matrix-transpose').classList.toggle('primary',pmMatrixTransposed);
  document.getElementById('pm-matrix-piece-sort').addEventListener('change',ev=>{pmMatrixPieceSort=ev.target.value;pmPersistMatrixPreferences();pmRenderMatrix();});
  document.getElementById('pm-matrix-install-sort').addEventListener('change',ev=>{pmMatrixInstallSort=ev.target.value;pmPersistMatrixPreferences();pmRenderMatrix();});
  document.getElementById('pm-matrix-direction').addEventListener('change',ev=>{pmMatrixDirection=ev.target.value;pmPersistMatrixPreferences();pmRenderMatrix();});
  document.getElementById('pm-matrix-transpose').addEventListener('click',()=>{pmMatrixTransposed=!pmMatrixTransposed;pmPersistMatrixPreferences();document.getElementById('pm-matrix-transpose').classList.toggle('primary',pmMatrixTransposed);pmRenderMatrix();});
  document.getElementById('pm-release-channel').addEventListener('change',ev=>{pmReleaseChannel=ev.target.value;pmRenderReleases();});
  document.getElementById('pm-jobs-refresh').addEventListener('click',pmLoadJobs);
  document.getElementById('pm-health-refresh').addEventListener('click',pmLoadHealth);
  document.getElementById('pm-refresh').addEventListener('click',async()=>{pmAudit('refresh','Detección local, releases, salud y Node Control');await Promise.all([refreshAll([]),loadNodeData(),pmLoadHealth()]);});
  document.getElementById('pm-reset-layout').addEventListener('click',()=>{
    if(typeof pmPatchSurface!=='undefined'&&pmPatchSurface==='chain'&&typeof pmRenderPatchChain==='function'){
      pmRenderPatchChain();
      pmAudit('layout','Cadena reencajada');
      return;
    }
    Object.keys(localStorage).filter(k=>k.startsWith('bago.pm.pos.')).forEach(k=>localStorage.removeItem(k));
    pmAudit('layout','Posiciones restablecidas');pmRenderPatch();
  });
  document.getElementById('pm-scan-manual').addEventListener('click',async()=>{
    const path=window.prompt('Ruta BAGO a detectar:','');
    if(path){pmAudit('scan','Ruta manual: '+path);await refreshAll([path]);}
  });
  document.getElementById('pm-validate').addEventListener('click',async()=>{
    const api=electronApi();if(!api||!api.runNodeValidate){copyText('bago node validate --json');return;}
    try{const result=await api.runNodeValidate();pmAudit('validate',result&&result.ok?'Node Control válido':'Validación con fallos');showToast(result&&result.ok?'Node Control válido':'Validación con fallos',!!(result&&result.ok));}catch(e){showToast(e.message,false);}
  });
  document.getElementById('pm-export').addEventListener('click',async()=>{
    if(!window.confirm('Exportar el estado Node Control a node-export.json?'))return;
    const api=electronApi();if(!api||!api.runNodeCommand){copyText('bago node export --output node-export.json');return;}
    try{await api.runNodeCommand(['node','export','--output','node-export.json']);pmAudit('export','node-export.json');showToast('Estado exportado',true);}catch(e){showToast(e.message,false);}
  });
  window.addEventListener('resize',pmUpdatePatchLines);
  renderPatchManager();
  pmLoadHealth();
  pmLoadJobs();
  const api=electronApi();
  if(api&&api.onReleaseJobChanged)api.onReleaseJobChanged(job=>{
    const index=releaseJobs.findIndex(item=>item.id===job.id);
    if(index>=0)releaseJobs[index]=job;else releaseJobs.unshift(job);
    pmRenderJobs();pmRenderReleases();pmRenderHealth();
  });
}
