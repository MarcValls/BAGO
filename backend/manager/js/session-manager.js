let pmSessions=[];
let pmSession=null;

function pmSessionApi(args){
  const api=electronApi();
  if(api&&typeof api.runSessionCommand==='function')return api.runSessionCommand(args);
  return Promise.reject(new Error('Gestor de sesiones no disponible sin Electron/backend operativo'));
}
function pmSessionOption(value,label,selected){
  return '<option value="'+escapeHtml(value)+'"'+(value===selected?' selected':'')+'>'+escapeHtml(label||value)+'</option>';
}
function pmCurrentProviderInfo(session){
  const providers=session&&Array.isArray(session.providers)?session.providers:[];
  const selected=document.getElementById('pm-session-provider');
  const providerName=(selected&&selected.value)||session&&session.provider||providers[0]&&providers[0].name||'';
  const provider=providers.find(item=>item.name===providerName)||null;
  return {providerName,provider,providers};
}
function pmRenderProviderActions(){
  const box=document.getElementById('pm-session-provider-actions');
  if(!box)return;
  const session=pmSession;
  const info=pmCurrentProviderInfo(session);
  const spec=pmProviderSpec(info.providerName);
  const configured=!!(info.provider&&info.provider.configured);
  const authModes=pmProviderAuthModes(info.providerName);
  const buttons=[];
  if(authModes.includes('api')){
    buttons.push('<button class="pm-btn primary" data-provider-action="api">API key</button>');
  }
  if(authModes.includes('login')){
    buttons.push('<button class="pm-btn" data-provider-action="login">Login</button>');
  }
  if(authModes.includes('install') && pmDependencySpec(spec.installTarget||'ollama')){
    buttons.push('<button class="pm-btn" data-provider-action="install">Instalar dependencia</button>');
  }
  const badges=[
    pmBadge(spec.label||info.providerName||'provider',configured?'ok':'warn'),
    pmBadge(configured?'configurado':'no configurado',configured?'ok':'bad'),
    authModes.length?pmBadge(authModes.join(' / '),'info'):pmBadge('sin onboarding','warn')
  ];
  box.innerHTML='<div class="pm-session-provider-tools" style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;justify-content:space-between;padding:10px 12px;border:1px solid #334155;border-radius:10px;background:#0f172a;">'
    +'<div style="min-width:260px;">'
    +'<div style="font-size:12px;color:#94a3b8;">Proveedor actual</div>'
    +'<div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:6px;">'+badges.join('')+'</div>'
    +'</div>'
    +'<div class="pm-provider-actions" style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;">'+buttons.join('')+'</div>'
    +'</div>';
  box.querySelectorAll('[data-provider-action]').forEach(btn=>{
    btn.addEventListener('click',()=>pmProviderAction(btn.getAttribute('data-provider-action')||'',info.providerName));
  });
}
async function pmProviderAction(action,providerName){
  const api=electronApi();
  const spec=pmProviderSpec(providerName);
  if(!api){
    throw new Error('providerAction solo está disponible en Electron');
  }
  try{
    if(action==='api'){
      if(typeof api.dependencyAction!=='function'){
        throw new Error('dependencyAction no disponible en Electron');
      }
      const primary=pmProviderPrimaryKey(providerName);
      if(!primary){
        showToast('No hay key primaria definida para '+providerName,false);
        return;
      }
      const label=spec.label||providerName;
      const value=window.prompt('Introduce el valor de '+primary+' para '+label,'');
      if(value===null||!value.trim())return;
      await api.dependencyAction({action:'set-credential',provider:providerName,key:primary,value:value.trim()});
      for(const extraKey of pmProviderOptionalKeys(providerName)){
        if(!window.confirm('¿Quieres registrar también '+extraKey+'?'))continue;
        const extraValue=window.prompt('Introduce el valor de '+extraKey+' para '+label,'');
        if(extraValue===null||!extraValue.trim())continue;
        await api.dependencyAction({action:'set-credential',provider:providerName,key:extraKey,value:extraValue.trim()});
      }
      showToast('Credenciales guardadas para '+label,true);
      if(pmSession&&pmSession.session_id) await pmLoadSession(pmSession.session_id);
      await pmLoadSessions();
      return;
    }
    if(action==='login'){
      const loginCommand=pmProviderLoginCommand(providerName);
      if(!loginCommand){
        showToast('No hay login definido para '+providerName,false);
        return;
      }
      if(typeof api.dependencyAction!=='function'){
        throw new Error('dependencyAction no disponible en Electron');
      }
      const result=await api.dependencyAction({action:'login',target:providerName});
      if(result&&result.command){
        await copyText(result.command);
        showToast('Comando de login copiado para '+(spec.label||providerName),true);
        return;
      }
      showToast('Login preparado para '+(spec.label||providerName),true);
      return;
    }
    if(action==='install'){
      const dep=pmDependencySpec(spec.installTarget||'ollama');
      if(!dep||!dep.id){
        showToast('No hay dependencia instalable para '+providerName,false);
        return;
      }
      if(typeof api.dependencyAction!=='function'){
        throw new Error('dependencyAction no disponible en Electron');
      }
      const result=await api.dependencyAction({action:'install',target:dep.id});
      if(result&&result.command){
        await copyText(result.command);
        showToast('Comando copiado para '+dep.label,true);
        return;
      }
      showToast('Instalador iniciado en segundo plano para '+dep.label,true);
      return;
    }
  }catch(error){
    showToast(error.message||'No se pudo completar la acción',false);
  }finally{
    if(pmSession&&pmSession.session_id){
      try{await pmLoadSession(pmSession.session_id);}catch{}
    }
  }
}
function pmRenderSessionList(){
  const box=document.getElementById('pm-session-list');
  box.innerHTML=pmSessions.map(item=>'<div class="pm-row '+(pmSession&&pmSession.session_id===item.sid?'selected':'')+'" data-session-id="'+escapeHtml(item.sid)+'"><span class="pm-row-icon">S</span><div><h3>'+escapeHtml(item.sid)+'</h3><p>'+escapeHtml((item.provider||item.last_provider||'sin provider')+' · '+(item.model||item.last_model||'sin modelo'))+'</p><div class="pm-badges">'+pmBadge(item.bago_mode||'B','info')+pmBadge(item.active_agent||'default')+'</div></div></div>').join('')||'<div class="pm-empty">Sin sesiones persistidas.</div>';
  box.querySelectorAll('[data-session-id]').forEach(row=>row.addEventListener('click',()=>pmLoadSession(row.getAttribute('data-session-id'))));
}
function pmRenderSession(){
  pmRenderSessionList();
  const session=pmSession;
  document.getElementById('pm-session-active').textContent=session?session.session_id+' · '+session.provider+' / '+session.model:'Selecciona o crea una sesion';
  const providers=session&&Array.isArray(session.providers)?session.providers:[];
  document.getElementById('pm-session-provider').innerHTML=providers.map(item=>pmSessionOption(item.name,item.name+(item.configured?' · listo':' · no configurado'),session&&session.provider)).join('');
  const current=providers.find(item=>session&&item.name===session.provider);
  const models=current&&current.models&&current.models.length?current.models:[session&&session.model||''];
  document.getElementById('pm-session-model').innerHTML=models.filter(Boolean).map(model=>pmSessionOption(model,model,session&&session.model)).join('');
  document.getElementById('pm-session-mode').value=session&&session.bago_mode||'B';
  document.getElementById('pm-session-agent').innerHTML=(session&&session.agents||['default']).map(agent=>pmSessionOption(agent,agent,session&&session.active_agent)).join('');
  document.getElementById('pm-session-bridges').innerHTML=providers.map(item=>pmSessionOption(item.name,item.name,session&&(session.active_bridges||[]).includes(item.name))).join('');
  pmRenderProviderActions();
  document.getElementById('pm-session-status').innerHTML=session?[
    pmBadge(session.health&&session.health.ok?'provider listo':'provider con fallo',session.health&&session.health.ok?'ok':'bad'),
    pmBadge(String(session.messages||0)+' mensajes'),
    pmBadge(String(session.total_calls||0)+' llamadas'),
    pmBadge(String(session.total_tokens||0)+' tokens')
  ].join(''):'';
  document.getElementById('pm-session-chat').innerHTML=(session&&session.history||[]).map(message=>'<div class="pm-session-message '+escapeHtml(message.role||'')+'"><strong>'+escapeHtml(message.role||'message')+'</strong>'+escapeHtml(message.content||'')+'</div>').join('')||'<div class="pm-empty">Sin historial.</div>';
}
async function pmLoadSessions(){
  try{
    const result=await pmSessionApi(['list']);
    pmSessions=result.sessions||[];
    document.getElementById('pm-session-caption').textContent=pmSessions.length+' sesiones · '+(result.base_path||'runtime activo');
    pmRenderSessionList();
  }catch(error){showToast(error.message,false);}
}
async function pmLoadSession(id){
  try{
    const result=await pmSessionApi(['status','--session-id',id]);
    pmSession=result.session;pmRenderSession();
  }catch(error){showToast(error.message,false);}
}
async function pmCreateSession(){
  try{
    const result=await pmSessionApi(['create']);
    pmSession=result.session;await pmLoadSessions();pmRenderSession();showToast('Sesion creada',true);
  }catch(error){showToast(error.message,false);}
}
async function pmApplySession(){
  if(!pmSession)return;
  const bridges=[...document.getElementById('pm-session-bridges').selectedOptions].map(option=>option.value).join(',');
  const args=['apply','--session-id',pmSession.session_id,'--provider',document.getElementById('pm-session-provider').value,'--model',document.getElementById('pm-session-model').value,'--mode',document.getElementById('pm-session-mode').value,'--agent',document.getElementById('pm-session-agent').value,'--bridges',bridges,'--force'];
  window.__bagoInteractionLogPush && window.__bagoInteractionLogPush('session-apply', {
    session_id: pmSession.session_id,
    provider: document.getElementById('pm-session-provider').value,
    model: document.getElementById('pm-session-model').value,
    mode: document.getElementById('pm-session-mode').value,
    agent: document.getElementById('pm-session-agent').value,
    bridges,
  });
  try{const result=await pmSessionApi(args);pmSession=result.session;await pmLoadSessions();pmRenderSession();showToast('Sesion actualizada',true);}catch(error){showToast(error.message,false);}
}
async function pmSendSession(orchestrate=false){
  if(!pmSession)return;
  const input=document.getElementById('pm-session-prompt');
  const prompt=input.value.trim();if(!prompt)return;
  window.__bagoInteractionLogPush && window.__bagoInteractionLogPush('session-send', {
    session_id: pmSession.session_id,
    orchestrate,
    prompt,
  });
  input.disabled=true;
  const args=['send','--session-id',pmSession.session_id,'--prompt',prompt];if(orchestrate)args.push('--orchestrate');
  try{const result=await pmSessionApi(args);pmSession=result.session;input.value='';pmRenderSession();if(orchestrate&&Object.values(result.response||{}).some(item=>!item.ok))showToast('Orquestacion parcial: revisa respuestas',false);}catch(error){showToast(error.message,false);}finally{input.disabled=false;}
}
function pmInitSessions(){
  document.getElementById('pm-session-refresh').addEventListener('click',pmLoadSessions);
  document.getElementById('pm-session-create').addEventListener('click',pmCreateSession);
  document.getElementById('pm-session-apply').addEventListener('click',pmApplySession);
  document.getElementById('pm-session-send').addEventListener('click',()=>pmSendSession(false));
  document.getElementById('pm-session-orchestrate').addEventListener('click',()=>pmSendSession(true));
  document.getElementById('pm-session-provider').addEventListener('change',event=>{
    if(!pmSession)return;
    const provider=(pmSession.providers||[]).find(item=>item.name===event.target.value);
    document.getElementById('pm-session-model').innerHTML=((provider&&provider.models)||[]).map(model=>pmSessionOption(model,model,'')).join('');
    pmRenderProviderActions();
  });
  pmLoadSessions().then(()=>{ if(!pmSession && pmSessions[0]){ pmSession=pmSessions[0]; pmRenderSession(); } }).catch(()=>{});
}
pmInitSessions();
