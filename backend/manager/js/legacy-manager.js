let managerVersion='';
let hiddenFutureReleaseCount=0;

function normalizeVersionTag(value){
  return String(value||'').trim().replace(/^v/i,'');
}

function parseVersionTag(value){
  const text=normalizeVersionTag(value);
  const match=text.match(/^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+.*)?$/);
  if(!match)return null;
  return {major:Number(match[1]),minor:Number(match[2]),patch:Number(match[3]),prerelease:match[4]?match[4].split('.'):[]};
}

function compareVersionTags(left,right){
  const a=parseVersionTag(left);
  const b=parseVersionTag(right);
  if(!a||!b)return 0;
  for(const key of ['major','minor','patch']){
    if(a[key]!==b[key])return a[key]-b[key];
  }
  if(!a.prerelease.length&&!b.prerelease.length)return 0;
  if(!a.prerelease.length)return 1;
  if(!b.prerelease.length)return -1;
  const length=Math.max(a.prerelease.length,b.prerelease.length);
  for(let i=0;i<length;i+=1){
    if(i>=a.prerelease.length)return -1;
    if(i>=b.prerelease.length)return 1;
    const leftPart=a.prerelease[i];
    const rightPart=b.prerelease[i];
    const leftNum=/^\d+$/.test(leftPart);
    const rightNum=/^\d+$/.test(rightPart);
    if(leftNum&&rightNum){
      const diff=Number(leftPart)-Number(rightPart);
      if(diff)return diff;
      continue;
    }
    if(leftNum)return -1;
    if(rightNum)return 1;
    const diff=leftPart.localeCompare(rightPart);
    if(diff)return diff;
  }
  return 0;
}

function pmLegacyBridgeReady(api, methodName, label){
  if(api && typeof api[methodName] !== 'function'){
    showToast((label || methodName) + ' no disponible en Electron', false);
    return false;
  }
  return true;
}

function isFutureReleaseTag(tagName, ceiling){
  const tag=normalizeVersionTag(tagName);
  const current=normalizeVersionTag(ceiling);
  if(!tag||!current)return false;
  return compareVersionTags(tag,current)>0;
}

async function resolveManagerVersion(){
  if(managerVersion)return managerVersion;
  const api=typeof electronApi==='function'?electronApi():null;
  try{
    if(api&&api.getVersion){
      managerVersion=normalizeVersionTag(await api.getVersion());
      if(managerVersion)return managerVersion;
    }
  }catch{}
  const fallback=document.getElementById('bago-version-meta');
  managerVersion=normalizeVersionTag((fallback&&fallback.textContent)||'');
  return managerVersion;
}

async function loadLatestRelease(){
  try{
    const ceiling=await resolveManagerVersion();
    const api=electronApi();
    const releases=api&&api.fetchReleases ? await api.fetchReleases() : await (async()=>{
      const res=await fetch('https://api.github.com/repos/MarcValls/BAGO/releases?per_page=100');
      if(!res.ok)throw new Error('HTTP '+res.status);
      return await res.json();
    })();
    const normalized=(Array.isArray(releases)?releases:[]).filter(r=>!r.draft);
    const allowed=normalized.filter(r=>!isFutureReleaseTag(r.tag_name,ceiling));
    hiddenFutureReleaseCount=Math.max(0,normalized.length-allowed.length);
    releaseItems=allowed
      .sort((a,b)=>new Date(b.published_at||0)-new Date(a.published_at||0));
    latestRelease=releaseItems.find(r=>!r.prerelease)||releaseItems[0]||null;
  }catch(e){
    releaseItems=[];
    latestRelease=null;
    hiddenFutureReleaseCount=0;
  }
}

function latestZipAsset(){
  if(!latestRelease||!Array.isArray(latestRelease.assets))return null;
  return latestRelease.assets.find(a=>/\.zip$/i.test(a.name||''))||null;
}

function psSingle(s){return "'"+String(s||'').replace(/'/g,"''")+"'";}
function psCommand(script){
  let bin='';
  for(let i=0;i<script.length;i++){
    const code=script.charCodeAt(i);
    bin+=String.fromCharCode(code&255,(code>>8)&255);
  }
  return 'powershell -NoProfile -ExecutionPolicy Bypass -EncodedCommand '+btoa(bin);
}
function localFilePathFromUrl(relativePath){
  try{
    const href=(typeof window!=='undefined'&&window.location&&window.location.href)||'';
    if(!href)return '';
    const url=new URL(relativePath,href);
    if(url.protocol!=='file:')return '';
    const pathname=decodeURIComponent(url.pathname||'');
    if(/^\/[A-Za-z]:/.test(pathname))return pathname.slice(1).replace(/\//g,'\\');
    return pathname.replace(/\//g,'\\');
  }catch{
    return '';
  }
}
function installCommand(tag,target){
  const api=electronApi();
  if(api&&pmLegacyBridgeReady(api,'buildInstallCommand','buildInstallCommand')&&api.buildInstallCommand){
    return api.buildInstallCommand(tag,target,'Express');
  }
  if(api){
    return psCommand('Write-Error '+psSingle('buildInstallCommand no disponible en Electron'));
  }
  const installScript=localFilePathFromUrl('../install-remote.ps1');
  if(!installScript){
    return psCommand('Write-Error '+psSingle('No se pudo resolver install-remote.ps1 local. Usa el Manager empaquetado o lanza el instalador local.'));
  }
  const tagArg=tag? ' -Tag '+psSingle(tag) : '';
  return psCommand('& '+psSingle(installScript)+tagArg+' -InstallDir '+psSingle(target)+' -Mode Express');
}
function uninstallCommand(target){
  const api=electronApi();
  if(api&&pmLegacyBridgeReady(api,'buildUninstallCommand','buildUninstallCommand')&&api.buildUninstallCommand){
    return api.buildUninstallCommand(target,false);
  }
  if(api){
    return psCommand('Write-Error '+psSingle('buildUninstallCommand no disponible en Electron'));
  }
  return psCommand('& '+psSingle(target+'\\bago-uninstall.ps1')+' -InstallDir '+psSingle(target));
}
function roleCommand(role,target){
  const api=electronApi();
  if(api&&pmLegacyBridgeReady(api,'buildRoleCommand','buildRoleCommand')&&api.buildRoleCommand){
    return api.buildRoleCommand(role,target);
  }
  if(api){
    return psCommand('Write-Error '+psSingle('buildRoleCommand no disponible en Electron'));
  }
  const label=(ROLE_DEFS[role]&&ROLE_DEFS[role].label)||role;
  return psCommand([
    '$role = '+psSingle(role),
    '$root = '+psSingle(target),
    '$label = '+psSingle(label),
    '$file = Join-Path $env:USERPROFILE '+psSingle('.bago\\install_selection.json'),
    '$roles = @{}',
    'if (Test-Path $file) { try { $data = Get-Content -LiteralPath $file -Raw | ConvertFrom-Json; if ($data.roles) { foreach ($p in $data.roles.PSObject.Properties) { $roles[$p.Name] = $p.Value } } } catch {} }',
    "$now = (Get-Date).ToUniversalTime().ToString('o')",
    '$roles[$role] = [ordered]@{ path = $root; label = $label; updated_at = $now }',
    '$out = [ordered]@{ version = 1; updated_at = $now; roles = $roles }',
    'New-Item -ItemType Directory -Force -Path (Split-Path -Parent $file) | Out-Null',
    '$out | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $file -Encoding UTF8',
    'Write-Host ("BAGO role " + $role + " -> " + $root)'
  ].join('; '));
}

function normalizePathKey(p){
  return String(p||'').replace(/[\\/]+$/,'').toLowerCase();
}

function normalizeSelection(raw){
  const roles=(raw&&raw.roles&&typeof raw.roles==='object')?raw.roles:{};
  const out={version:1,updated_at:(raw&&raw.updated_at)||'',selection_file:(raw&&raw.selection_file)||(raw&&raw.file)||'',roles:{}};
  ROLE_ORDER.forEach(role=>{
    const entry=roles[role];
    if(typeof entry==='string'&&entry) out.roles[role]={path:entry,label:ROLE_DEFS[role].label};
    else if(entry&&entry.path) out.roles[role]={path:String(entry.path),label:entry.label||ROLE_DEFS[role].label,updated_at:entry.updated_at||''};
  });
  return out;
}

function rolePathsFromSelection(sel=installSelection){
  const out={};
  ROLE_ORDER.forEach(role=>{
    const entry=sel.roles&&sel.roles[role];
    if(entry&&entry.path) out[role]=String(entry.path);
  });
  return out;
}

function readLocalSelection(){
  return normalizeSelection({});
}

function writeLocalSelection(role,target){
  return normalizeSelection({});
}

async function resolveInstallSelection(data){
  const api=electronApi();
  if(api&&pmLegacyBridgeReady(api,'readInstallSelection','readInstallSelection')&&api.readInstallSelection){
    try{return normalizeSelection(await api.readInstallSelection());}catch(e){/* fallback to payload/local */}
  }
  if(api){
    return normalizeSelection({});
  }
  return normalizeSelection({});
}

function decorateInstallRoles(items){
  const selected=rolePathsFromSelection();
  (items||[]).forEach(inst=>{
    const roles=ROLE_ORDER.filter(role=>normalizePathKey(selected[role])===normalizePathKey(inst.path));
    inst.selection_roles=roles;
    ROLE_ORDER.forEach(role=>{inst['selected_'+role]=roles.includes(role);});
  });
}

function existingInstallations(data=currentPayload){
  return data&&Array.isArray(data.installations)?data.installations.filter(i=>i.exists):[];
}

function roleBadgeLabel(role){
  if(role==='active')return 'activa';
  if(role==='dev')return 'dev';
  if(role==='launch')return 'arranque';
  if(role==='writer')return 'escritor';
  if(role==='illustrator')return 'ilustrador';
  return role;
}

function renderRolePanel(items){
  if(!rolePanel||!roleCards)return;
  const selected=rolePathsFromSelection();
  const file=installSelection.selection_file||'~\\.bago\\install_selection.json';
  roleFileLabel.textContent=file;
  rolePanel.style.display='block';
  roleCards.innerHTML=ROLE_ORDER.map(role=>{
    const def=ROLE_DEFS[role];
    const selectedPath=selected[role]||'';
    const found=items.find(i=>normalizePathKey(i.path)===normalizePathKey(selectedPath));
    const cmd=selectedPath?roleCommand(role,selectedPath):'';
    const state=selectedPath?(found?'seleccionada':'seleccionada, no detectada'):'sin seleccionar';
    const stateBadge='<span class="badge '+(selectedPath?(found?'badge-on':'badge-warn'):'badge-neutral')+'">'+escapeHtml(state)+'</span>';
    const actions=selectedPath
      ? '<div class="actions">'
        +(canRunCommands()?'<button class="run" data-cmd="'+escapeHtml(cmd)+'">reaplicar</button>':'')
        +'<button class="copy" data-cmd="'+escapeHtml(cmd)+'">copiar comando</button>'
        +'</div>'
      : '<div class="actions"><span class="badge badge-neutral">elige una copia en las tarjetas de abajo</span></div>';
    return '<div class="role-card '+(selectedPath?'selected':'')+'">'
      +'<div class="role-title">'+escapeHtml(def.label)+' '+stateBadge+'</div>'
      +'<div class="role-desc">'+escapeHtml(def.desc)+'</div>'
      +'<div class="role-path">'+escapeHtml(selectedPath||'No asignado')+'</div>'
      +actions
      +'</div>';
  }).join('');
  roleCards.querySelectorAll('button.copy').forEach(btn=>btn.addEventListener('click',()=>copyText(btn.getAttribute('data-cmd')||'')));
  roleCards.querySelectorAll('button.run').forEach(btn=>btn.addEventListener('click',()=>runCommand(btn.getAttribute('data-cmd')||'')));
}

function rerenderInstallationCards(){
  if(!currentPayload)return;
  decorateInstallRoles(currentPayload.installations);
  const existing=existingInstallations(currentPayload);
  renderRolePanel(existing);
  installBox.innerHTML=existing.map(renderCard).join('');
  attachCardHandlers();
}

async function setInstallRole(role,target){
  const api=electronApi();
  try{
    if(api&&pmLegacyBridgeReady(api,'writeInstallSelection','writeInstallSelection')&&api.writeInstallSelection){
      installSelection=normalizeSelection(await api.writeInstallSelection(role,target));
      showToast('rol '+roleBadgeLabel(role)+' guardado',true);
    }else if(api){
      return;
    }else{
      installSelection=writeLocalSelection(role,target);
      await copyText(roleCommand(role,target));
      showToast('rol guardado localmente; comando copiado para aplicarlo en BAGO',true);
    }
    rerenderInstallationCards();
  }catch(e){
    showToast('no se pudo guardar rol: '+e.message,false);
  }
}

function versionText(v){return String(v||'').replace(/^v/i,'').trim();}
function updateState(inst){
  if(!latestRelease)return {label:'release no consultada',cls:'badge-neutral',tag:'',asset:''};
  const current=versionText(inst.version||inst.tag||'');
  const latest=versionText(latestRelease.tag_name||'');
  const beta=latestRelease.prerelease?' · beta':'';
  if(current&&latest&&current===latest)return {label:'actualizado '+latest+beta,cls:'badge-on',tag:latestRelease.tag_name,asset:(latestZipAsset()||{}).name||''};
  return {label:'update '+(current||'desconocida')+' → '+latest+beta,cls:'badge-warn',tag:latestRelease.tag_name,asset:(latestZipAsset()||{}).name||''};
}

function renderReleaseList(){
  if(!releaseList) return;
  const total = releaseItems.length;
  const beta = releaseItems.filter(r=>r.prerelease).length;
  releaseSummary.textContent = total
    ? `Detectadas ${total} release(s) compatibles · ${beta} beta(s)${hiddenFutureReleaseCount ? ` · ${hiddenFutureReleaseCount} futura(s) ocultada(s)` : ''} · la mas reciente permitida es ${latestRelease ? latestRelease.tag_name : 'n/a'}`
    : hiddenFutureReleaseCount
      ? `No hay releases compatibles con la versión actual${managerVersion ? ` (${managerVersion})` : ''}. Se ocultaron ${hiddenFutureReleaseCount} release(s) futura(s).`
      : 'No se pudieron cargar releases compatibles desde GitHub.';
  releaseList.innerHTML = releaseItems.map(rel=>{
    const asset = (Array.isArray(rel.assets) ? rel.assets.find(a=>/\.zip$/i.test(a.name||'')) : null) || {};
    const betaBadge = rel.prerelease ? '<span class="badge badge-warn">beta</span>' : '<span class="badge badge-on">release</span>';
    const dateText = rel.published_at ? new Date(rel.published_at).toLocaleString() : 'fecha desconocida';
    const target = document.getElementById('target-install-path')?.value || 'C:\\Program Files\\BAGO';
    const safeTag = versionText(rel.tag_name || 'latest').replace(/[^A-Za-z0-9._-]/g, '_');
    return '<div class="release-item">'
      + '<div>'
      + '<div class="title">'+escapeHtml(rel.tag_name || 'sin tag')+' '+betaBadge+'</div>'
      + '<div class="meta">'+escapeHtml(dateText)+' · '+escapeHtml(asset.name || 'sin asset zip')+'</div>'
      + '<div class="meta">'+escapeHtml(asset.browser_download_url || '')+'</div>'
      + '</div>'
      + '<div class="actions">'
      + '<button class="run" data-release="'+escapeHtml(rel.tag_name || '')+'" data-target="'+escapeHtml(target)+'">instalar aquí</button>'
      + '<button class="run" data-release="'+escapeHtml(rel.tag_name || '')+'" data-target="'+escapeHtml(target+'-'+safeTag)+'">instalar aparte</button>'
      + '<button class="copy" data-cmd="'+escapeHtml(asset.browser_download_url || '')+'">copiar url</button>'
      + '<button class="copy" data-cmd="'+escapeHtml(rel.html_url || '')+'">copiar release</button>'
      + '</div>'
      + '</div>';
  }).join('');
  releaseList.querySelectorAll('button.run').forEach(btn=>{
    btn.addEventListener('click',()=>{
      const tag = btn.getAttribute('data-release')||'';
      const target = btn.getAttribute('data-target')||'C:\\Program Files\\BAGO';
      runCommand(installCommand(tag,target));
    });
  });
  releaseList.querySelectorAll('button.copy').forEach(btn=>{
    btn.addEventListener('click',()=>copyText(btn.getAttribute('data-cmd')||''));
  });
  renderPatchManager();
}

async function renderPayload(data){
  if(!latestRelease && releaseItems.length) latestRelease = releaseItems.find(r=>!r.prerelease)||releaseItems[0];
  if(!data||!Array.isArray(data.installations)){showToast('el JSON no tiene el campo installations[]',false);return;}
  currentPayload=data;
  pmStoreLocalPayload(data);
  installSelection=await resolveInstallSelection(data);
  decorateInstallRoles(data.installations);
  const existing=data.installations.filter(i=>i.exists);
  if(!existing.length){showToast('ninguna instalación existente detectada',false);renderEmpty();return;}
  document.getElementById('s-total').textContent=data.installations.length;
  document.getElementById('s-existing').textContent=existing.length;
  document.getElementById('s-sup').textContent=existing.filter(i=>i.has_supervisor).length;
  document.getElementById('s-probe').textContent=existing.filter(i=>i.has_probe).length;
  summaryBar.style.display='flex';
  emptyState.style.display='none';
  renderRolePanel(existing);
  installBox.innerHTML=existing.map(renderCard).join('');
  attachCardHandlers();
  renderPatchManager();
  showToast(existing.length+' instalación(es) cargada(s)',true);
}

async function refreshAll(extraPaths){
  const api=electronApi();
  try{
    if(api&&api.scanInstallations&&api.fetchReleases){
      const [scan,releases]=await Promise.all([api.scanInstallations(Array.isArray(extraPaths)?extraPaths:[]), api.fetchReleases()]);
      const normalized=(Array.isArray(releases)?releases:[]).filter(r=>!r.draft);
      const ceiling=await resolveManagerVersion();
      releaseItems=normalized.filter(r=>!isFutureReleaseTag(r.tag_name,ceiling));
      hiddenFutureReleaseCount=Math.max(0,normalized.length-releaseItems.length);
      latestRelease=releaseItems.find(r=>!r.prerelease)||releaseItems[0]||null;
      renderReleaseList();
      await renderPayload(scan);
      return;
    }
    await loadLatestRelease();
    renderReleaseList();
    showToast('modo web: usa el pegado manual para cargar instalaciones',false);
  }catch(e){
    showToast('no se pudo actualizar: '+e.message,false);
  }
}

async function bootstrapAuto(){
  const api=electronApi();
  if(api&&api.scanInstallations&&api.fetchReleases){
    const io=document.querySelector('.io');
    if(io) io.style.display='none';
    await refreshAll([]);
  } else {
    await loadLatestRelease();
    renderReleaseList();
    const cached=pmGetLocalPayload();
    if(cached&&Array.isArray(cached.installations)){
      await renderPayload(cached);
    }
  }
}

async function parseAndRender(raw){
  if(latestRelease===null)await loadLatestRelease();
  raw=(raw||'').trim();
  if(!raw){showToast('pega primero el JSON o usa Cargar desde archivo',false);return;}
  let data;
  try{data=JSON.parse(raw);}catch(e){showToast('JSON inválido: '+e.message,false);return;}
  await renderPayload(data);
}

function modeBadge(mode,alive){const map={system:['system','badge-mode'],user:['user','badge-mode'],work:['work','badge-mode'],ign:['ign','badge-mode'],dev:['dev','badge-mode'],source:['source','badge-mode']};const[v,c]=map[mode]||[mode,'badge-neutral'];const a=alive==='alive'?'<span class="badge badge-on">● vivo</span>':'<span class="badge badge-off">○ parado</span>';return'<span class="badge '+c+'">'+escapeHtml(v)+'</span>'+a;}

function renderCard(inst){
  const ver=inst.version||inst.tag||'—';
  const supBadge=inst.has_supervisor?(inst.supervisor_alive?'<span class="badge badge-on">supervisor ●</span>':'<span class="badge badge-off">supervisor ○</span>'):'<span class="badge badge-neutral">no sup</span>';
  const probeBadge=inst.has_probe?'<span class="badge badge-on">probe</span>':'<span class="badge badge-neutral">no probe</span>';
  const cliBadge=inst.has_cli?'<span class="badge badge-on">cli</span>':'<span class="badge badge-warn">sin cli</span>';
  const upd=updateState(inst);
  const updateBadge='<span class="badge '+upd.cls+'">'+escapeHtml(upd.label)+'</span>';
  const roleBadges=(inst.selection_roles||[]).map(role=>'<span class="badge badge-on">rol '+escapeHtml(roleBadgeLabel(role))+'</span>').join('');
  const isSource=inst.mode==='source';
  const pathEnc=escapeHtml(inst.path);
  const roleButtons='<div class="role-actions">'
    +ROLE_ORDER.map(role=>'<button class="role-select '+(inst['selected_'+role]?'active':'')+'" data-role="'+escapeHtml(role)+'" data-path="'+pathEnc+'">'+escapeHtml(roleBadgeLabel(role))+'</button>').join('')
    +'</div>';
  const actions=buildActions(inst,isSource);
  return'<div class="card" data-idx="'+escapeHtml(inst.mode)+'">'
    +'<div class="card-head"><h3 class="card-title">'+pathEnc.split(/[\\\\\\/]/).filter(Boolean).slice(-1)[0]+' <span class="mono" style="color:var(--muted);font-size:13px;font-weight:400">v'+escapeHtml(ver)+'</span></h3></div>'
    +'<div class="card-path">'+pathEnc+'</div>'
    +'<div class="badges">'+modeBadge(inst.mode,inst.supervisor_alive?'alive':'dead')+supBadge+probeBadge+cliBadge+sealBadge+updateBadge+roleBadges+'</div>'
    +roleButtons
    +actions
    +'</div>';
}

function actionGroup(title,icon,items){
  if(!items.length)return'';
  const runButton=canRunCommands()?'<button class="run" data-cmd="{cmd}">ejecutar</button>':'';
  return'<details><summary><span class="chev">▸</span> '+icon+' '+title+'<span class="count">'+items.length+'</span></summary><div class="body">'
    +items.map(it=>{
      const cmd=escapeHtml(it.cmd);
      return'<div class="row"><div class="label">'+escapeHtml(it.label)+'<span class="desc">'+escapeHtml(it.desc||'')+'</span></div><div class="actions">'+runButton.replace('{cmd}',cmd)+'<button class="copy" data-cmd="'+cmd+'">copiar</button></div></div>';
    }).join('')
    +'</div></details>';
}

function buildActions(inst,isSource){
  const path=inst.path;
  const pypath=isSource?'python':'pythonw';
  const cd='Set-Location -LiteralPath '+psSingle(path);
  const groups=[];
  const latestTag=latestRelease&&latestRelease.tag_name?latestRelease.tag_name:'';
  const latestAsset=latestZipAsset();
  const latestAssetName=latestAsset&&latestAsset.name?latestAsset.name:'asset .zip mas reciente';
  const latestReleaseUrl=latestRelease&&latestRelease.html_url?latestRelease.html_url:'https://github.com/MarcValls/BAGO/releases';
  const latestAssetUrl=latestAsset&&latestAsset.browser_download_url?latestAsset.browser_download_url:'https://github.com/MarcValls/BAGO/releases';
  groups.push(actionGroup('Roles BAGO','🎛',[
    {label:'Usar como copia activa',desc:'Hace que `bago` apunte a esta copia',cmd:roleCommand('active',path)},
    {label:'Usar como desarrollo',desc:'Hace que `bago des` apunte a esta copia',cmd:roleCommand('dev',path)},
    {label:'Usar como arranque principal',desc:'Hace que `bago ign` apunte a esta copia',cmd:roleCommand('launch',path)},
    {label:'Usar como escritor',desc:'Registra esta copia para flujos de redacción',cmd:roleCommand('writer',path)},
    {label:'Usar como ilustrador',desc:'Registra esta copia para flujos visuales',cmd:roleCommand('illustrator',path)},
  ]));
  groups.push(actionGroup('Ejecutar','▶',[
    {label:'Abrir chat BAGO',desc:'Lanza la CLI interactiva',cmd:cd+'; '+pypath+' bago_core/cli.py chat'},
    {label:'Arrancar supervisor',desc:'Modo silencioso (pythonw)',cmd:cd+'; pythonw scripts/bago_supervisor.pyw'},
    {label:'Parar supervisor',desc:'taskkill sobre el pid vivo',cmd:'taskkill /F /PID '+((inst.supervisor_pid||'0'))},
    {label:'Estado del supervisor',desc:'Lee state.json',cmd:cd+'; python scripts/probe.py'},
  ]));
  groups.push(actionGroup('Plataforma','⚙',[
    {label:'Probe completo',desc:'5 checks del sistema',cmd:cd+'; python scripts/probe.py'},
    {label:'Validar instalación',desc:'Security, contratos, providers y claims',cmd:cd+'; python bago_core/cli.py validate'},
    {label:'Ver configuración',desc:'Config efectiva de esta instalación',cmd:cd+'; python bago_core/cli.py config list'},
    {label:'Route status',desc:'Preset activo y contrato',cmd:cd+'; python bago_core/cli.py route status'},
    {label:'Editar config',desc:'abrir install_config.json en notepad',cmd:'notepad "'+path+'\\install_config.json"'},
  ]));
  groups.push(actionGroup('Actualizaciones','⬆',[
    {label:'Ver ultima release compatible',desc:'Muestra el tag y asset permitido por el gestor',cmd:psCommand('Write-Host '+psSingle(latestTag+' / '+latestAssetName))},
    {label:'Actualizar esta instalación',desc:'Instala la release mas reciente encima de esta ruta',cmd:installCommand(latestTag,path)},
    {label:'Instalar aparte',desc:'Crea una instalación separada para probar sin pisar esta',cmd:installCommand(latestTag,path+'-'+latestTag.replace(/[^A-Za-z0-9._-]/g,'_'))},
    {label:'Desinstalar',desc:'Llama al uninstall local de esta ruta',cmd:uninstallCommand(path)},
    {label:'Abrir release en GitHub',desc:'Revisar notas antes de actualizar',cmd:psCommand('Start-Process '+psSingle(latestReleaseUrl))},
    {label:'Descargar asset latest',desc:'Baja el zip resuelto a Descargas',cmd:psCommand('Invoke-WebRequest -Uri '+psSingle(latestAssetUrl)+' -OutFile (Join-Path $env:USERPROFILE '+psSingle('Downloads\\'+latestAssetName)+')')},
  ]));
  groups.push(actionGroup('Proveedores LLM','🔌',[
    {label:'Listar providers',desc:'Instalados/configurados y disponibles',cmd:cd+'; python bago_core/cli.py llm list'},
    {label:'Probar Ollama local',desc:'Dry-run sin abrir chat',cmd:cd+'; python bago_core/cli.py llm start --provider ollama-local --model llama3.2:3b --dry-run'},
    {label:'Fijar Ollama como default',desc:'Guarda provider/modelo por defecto en esta instalación',cmd:cd+'; python bago_core/cli.py llm start --provider ollama-local --model llama3.2:3b --persist-default --dry-run'},
    {label:'Probar BAGO persona',desc:'Modelo Ollama con identidad BAGO',cmd:cd+'; python bago_core/cli.py llm start --provider ollama-local --model bago-llama32-bago-persona --dry-run'},
    {label:'Fijar BAGO persona',desc:'Usar bago-llama32-bago-persona como modelo por defecto',cmd:cd+'; python bago_core/cli.py llm start --provider ollama-local --model bago-llama32-bago-persona --persist-default --dry-run'},
    {label:'Activar OpenRouter',desc:'Marca provider cloud como habilitado',cmd:cd+'; python bago_core/cli.py config set providers.openrouter.enabled true'},
    {label:'Activar Anthropic',desc:'Marca provider cloud como habilitado',cmd:cd+'; python bago_core/cli.py config set providers.anthropic.enabled true'},
    {label:'Editar .bago/config.json',desc:'Config de providers de esta instalación',cmd:'notepad "'+path+'\\.bago\\config.json"'},
    {label:'Abrir carpeta .bago',desc:'Revisar state/config/provider local',cmd:'explorer "'+path+'\\.bago"'},
  ]));
  groups.push(actionGroup('Conocimiento','🧠',[
    {label:'Estado de la knowledge base',desc:'chunks, fallback, embeddings',cmd:cd+'; python bago_core/cli.py knowledge status'},
    {label:'Ingerir carpeta',desc:'Añade .md/.txt/.py al KB',cmd:cd+'; python bago_core/cli.py knowledge ingest '+psSingle(path+'\\docs')},
    {label:'Escanear recursivo',desc:'Recorre subcarpetas',cmd:cd+'; python bago_core/cli.py knowledge scan '+psSingle(path+'\\docs')+' --recursive'},
  ]));
  groups.push(actionGroup('Entrenamiento','🎓',[
    {label:'Estado del RL',desc:'versión BC, recompensas, checkpoint',cmd:cd+'; python bago_core/cli.py rl status'},
    {label:'Entrenar BC',desc:'Behavioral cloning desde transiciones disponibles',cmd:cd+'; python bago_core/cli.py rl train bc'},
    {label:'Activar shadow mode',desc:'Aprende sin afectar decisiones',cmd:cd+'; python bago_core/cli.py rl shadow on'},
    {label:'Desactivar shadow',desc:'Vuelve a modo observación apagada',cmd:cd+'; python bago_core/cli.py rl shadow off'},
  ]));
  groups.push(actionGroup('Agentes y Tools','🤖',[
    {label:'Listar agentes',desc:'agentes activos y roles',cmd:cd+'; python bago_core/cli.py agent list'},
    {label:'Spawn agente explorer',desc:'Crea un agente por id',cmd:cd+'; python bago_core/cli.py agent spawn explorer'},
    {label:'Toolsmith catalog',desc:'Tools disponibles y permisos',cmd:cd+'; python bago_core/cli.py toolsmith catalog'},
    {label:'Toolsmith assign',desc:'Asigna tool sugerida a una tarea',cmd:cd+'; python bago_core/cli.py toolsmith assign --task explore --agent explorer'},
  ]));
  groups.push(actionGroup('Backup y snapshot','💾',[
    {label:'Crear backup',desc:'Snapshot de state+config+memory',cmd:cd+'; python bago_core/cli.py backup create'},
    {label:'Listar backups',desc:'Snapshots disponibles',cmd:cd+'; python bago_core/cli.py backup list'},
    {label:'Inventario completo',desc:'Cuenta archivos, tamaños, sellos',cmd:cd+'; python bago_core/cli.py inventory'},
    {label:'Generar bundle 4.8',desc:'Crea un ZIP de release local',cmd:cd+'; python scripts/publish_release.py --mode build'},
  ]));
  return groups.join('');
}

function attachCardHandlers(){
  installBox.querySelectorAll('button.role-select').forEach(btn=>{
    btn.addEventListener('click',()=>setInstallRole(btn.getAttribute('data-role')||'',btn.getAttribute('data-path')||''));
  });
  installBox.querySelectorAll('button.copy').forEach(btn=>{
    btn.addEventListener('click',()=>{
      const cmd=btn.getAttribute('data-cmd')||'';
      copyText(cmd);
    });
  });
  installBox.querySelectorAll('button.run').forEach(btn=>{
    btn.addEventListener('click',()=>{
      const cmd=btn.getAttribute('data-cmd')||'';
      runCommand(cmd);
    });
  });
}

function renderEmpty(){
  installBox.innerHTML='';
  summaryBar.style.display='none';
  if(rolePanel) rolePanel.style.display='none';
  emptyState.style.display='block';
}

document.getElementById('btn-paste').addEventListener('click',async()=>{
  try{
    const text=await readTextClipboard();
    inputArea.value=text;
    window.__bagoInteractionLogPush && window.__bagoInteractionLogPush('paste', { source: 'clipboard', target: 'input-area', value: text });
    parseAndRender(text);
  }catch(e){showToast('no se pudo leer el portapapeles: '+e.message,false);}
});
document.getElementById('btn-render').addEventListener('click',()=>{window.__bagoInteractionLogPush && window.__bagoInteractionLogPush('render', { target: 'input-area', value: inputArea.value });parseAndRender(inputArea.value);});
document.getElementById('btn-clear').addEventListener('click',()=>{window.__bagoInteractionLogPush && window.__bagoInteractionLogPush('clear', { target: 'input-area' });inputArea.value='';pmStoreLocalPayload(null);renderEmpty();showToast('limpio',true);});
document.getElementById('btn-file').addEventListener('click',()=>{window.__bagoInteractionLogPush && window.__bagoInteractionLogPush('open-file-picker', { target: 'file-input' });document.getElementById('file-input').click();});
document.getElementById('file-input').addEventListener('change',ev=>{
  const f=ev.target.files&&ev.target.files[0];
  if(!f)return;
  const r=new FileReader();
  r.onload=e=>{window.__bagoInteractionLogPush && window.__bagoInteractionLogPush('file-load', { file: f.name, size: f.size, target: 'input-area', value: e.target.result });inputArea.value=e.target.result;parseAndRender(e.target.result);};
  r.onerror=()=>showToast('error leyendo archivo',false);
  r.readAsText(f);
});
document.getElementById('btn-sample').addEventListener('click',()=>{
  const sample=window.__SAMPLE__||'{"summary":{"existing":1,"with_supervisor":0,"with_probe":1},"installations":[{"path":"C:\\\\\\\\BAGO-demo","mode":"source","exists":true,"version":"4.8.0","has_bago_ps1":true,"has_bago_cmd":true,"has_supervisor":false,"supervisor_alive":"dead","has_probe":true,"has_cli":true,"description":"Instalación demo","release_sig_short":"abc1234"}]}';
  window.__bagoInteractionLogPush && window.__bagoInteractionLogPush('sample', { target: 'input-area', value: sample });
  inputArea.value=sample;
  parseAndRender(sample);
});

document.getElementById('btn-refresh-data').addEventListener('click',()=>refreshAll([]));
document.getElementById('btn-refresh-roles').addEventListener('click',async()=>{
  if(currentPayload){
    installSelection=await resolveInstallSelection(currentPayload);
    rerenderInstallationCards();
    showToast('roles recargados',true);
  }else{
    await refreshAll([]);
  }
});
document.getElementById('btn-scan-path').addEventListener('click',()=>{
  const p=document.getElementById('manual-scan-path').value.trim();
  if(!p){showToast('indica una ruta primero',false);return;}
  refreshAll([p]);
});

// Node Control: tabs, refresh, copy buttons (event delegation)
document.querySelectorAll('.section-tab').forEach(tab=>{
  tab.addEventListener('click',()=>setNodeTab(tab.getAttribute('data-tab')));
});
document.getElementById('btn-refresh-node').addEventListener('click',()=>loadNodeData());
document.getElementById('node-evidence').addEventListener('click',ev=>{
  const b=ev.target.closest('button.copy');if(!b)return;
  copyText(b.getAttribute('data-cmd')||'');
});
