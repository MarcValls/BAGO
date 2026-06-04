let pmSessions=[];
let pmSession=null;

function pmSessionApi(args){
  const api=electronApi();
  if(!api||!api.runSessionCommand)throw new Error('SessionManager solo esta disponible en Electron');
  return api.runSessionCommand(args);
}
function pmSessionOption(value,label,selected){
  return '<option value="'+escapeHtml(value)+'"'+(value===selected?' selected':'')+'>'+escapeHtml(label||value)+'</option>';
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
  try{const result=await pmSessionApi(args);pmSession=result.session;await pmLoadSessions();pmRenderSession();showToast('Sesion actualizada',true);}catch(error){showToast(error.message,false);}
}
async function pmSendSession(orchestrate=false){
  if(!pmSession)return;
  const input=document.getElementById('pm-session-prompt');
  const prompt=input.value.trim();if(!prompt)return;
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
  });
  pmLoadSessions();
}
pmInitSessions();
