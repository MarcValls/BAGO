const toast=document.getElementById('toast');
function showToast(msg,ok=true){toast.textContent=msg;toast.className='toast '+(ok?'ok':'err');requestAnimationFrame(()=>toast.classList.add('show'));setTimeout(()=>toast.classList.remove('show'),2400);}

const PM_LOCAL_RUNTIME_KEY='bago.manager.runtime.fallback';
function pmClone(value){
  try{return value==null?null:JSON.parse(JSON.stringify(value));}catch{return value==null?null:String(value);}
}
function pmReadLocalRuntime(){
  try{
    const raw=localStorage.getItem(PM_LOCAL_RUNTIME_KEY);
    const parsed=raw?JSON.parse(raw):{};
    return parsed&&typeof parsed==='object'?parsed:{};
  }catch{return {};}
}
function pmWriteLocalRuntime(next){
  try{localStorage.setItem(PM_LOCAL_RUNTIME_KEY,JSON.stringify(next||{}));}catch{}
}
function pmUpdateLocalRuntime(patch){
  const next=Object.assign({sessions:{list:[],activeId:''},payload:null,system:{lastAction:'',lastAt:''}},pmReadLocalRuntime(),patch||{});
  pmWriteLocalRuntime(next);
  return next;
}
function pmStoreLocalPayload(payload){
  const state=pmReadLocalRuntime();
  state.payload=pmClone(payload);
  pmWriteLocalRuntime(state);
  window.__bagoLocalPayload=pmClone(payload);
  return payload;
}
function pmGetLocalPayload(){
  const state=pmReadLocalRuntime();
  return state.payload!=null?state.payload:(window.__bagoLocalPayload||null);
}
function pmLocalProviderCatalog(){
  return [
    {name:'ollama-local',configured:true,models:['llama3.2:3b','bago-llama32-bago-persona']},
    {name:'codex',configured:true,models:['gpt-5.4-mini','gpt-4.1-mini']},
    {name:'openrouter',configured:false,models:['gpt-4.1-mini']}
  ];
}
function pmNormalizeLocalSession(session){
  const providers=pmLocalProviderCatalog();
  const modelByProvider=provider=>{
    const found=providers.find(item=>item.name===provider);
    return found&&found.models&&found.models[0]||'gpt-5.4-mini';
  };
  const provider=session&&session.provider||providers[0].name;
  const models=(providers.find(item=>item.name===provider)||providers[0]).models||['gpt-5.4-mini'];
  const sessionId=session&&session.session_id||session&&session.sid||('local-session-'+Date.now().toString(36));
  return {
    session_id:sessionId,
    sid:sessionId,
    provider,
    model:session&&session.model||modelByProvider(provider),
    last_provider:session&&session.last_provider||provider,
    last_model:session&&session.last_model||session&&session.model||modelByProvider(provider),
    bago_mode:session&&session.bago_mode||'B',
    active_agent:session&&session.active_agent||'default',
    active_bridges:Array.isArray(session&&session.active_bridges)?session.active_bridges.slice():[provider],
    providers:(session&&Array.isArray(session.providers)&&session.providers.length?session.providers:providers).map(item=>({
      name:item.name,
      configured:item.configured!==false,
      models:Array.isArray(item.models)&&item.models.length?item.models.slice():[modelByProvider(item.name)]
    })),
    agents:Array.isArray(session&&session.agents)&&session.agents.length?session.agents.slice():['default','reviewer'],
    history:Array.isArray(session&&session.history)?session.history.slice():[],
    messages:Number(session&&session.messages||0),
    total_calls:Number(session&&session.total_calls||0),
    total_tokens:Number(session&&session.total_tokens||0),
    health:session&&session.health||{ok:true},
    base_path:session&&session.base_path||'browser-local'
  };
}
function pmReadLocalSessions(){
  const state=pmReadLocalRuntime();
  const raw=Array.isArray(state.sessions&&state.sessions.list)?state.sessions.list:(Array.isArray(state.sessions)?state.sessions:[]);
  const list=raw.map(pmNormalizeLocalSession);
  const activeId=String(state.sessions&&state.sessions.activeId||state.activeSessionId||list[0]&&list[0].session_id||'');
  return {list,activeId};
}
function pmWriteLocalSessions(list,activeId){
  const state=pmReadLocalRuntime();
  state.sessions={list:(list||[]).map(pmNormalizeLocalSession),activeId:String(activeId||list&&list[0]&&list[0].session_id||'')};
  pmWriteLocalRuntime(state);
  return state.sessions;
}
function pmSeedLocalSessions(){
  const state=pmReadLocalSessions();
  if(!state.list.length){
    const session=pmNormalizeLocalSession({session_id:'local-session-1',provider:'ollama-local',model:'llama3.2:3b',bago_mode:'B',active_agent:'default',active_bridges:['ollama-local'],history:[],messages:0,total_calls:0,total_tokens:0,health:{ok:true},base_path:'browser-local'});
    pmWriteLocalSessions([session],session.session_id);
    return {list:[session],activeId:session.session_id};
  }
  return state;
}
function pmLocalSessionCommand(args){
  const safe=Array.isArray(args)?args.map(value=>String(value||'')):[];
  const action=String(safe[0]||'list');
  const getArg=(flag)=>{
    const idx=safe.indexOf(flag);
    return idx>=0?safe[idx+1]||'':'';
  };
  const state=pmSeedLocalSessions();
  let list=state.list.map(pmNormalizeLocalSession);
  let activeId=state.activeId||list[0].session_id;
  const findSession=id=>list.find(item=>item.session_id===id)||null;
  const activeSession=()=>findSession(activeId)||findSession(getArg('--session-id'))||list[0]||pmNormalizeLocalSession({});
  if(action==='list'){
    return {ok:true,base_path:'browser-local',sessions:list.map(item=>({
      sid:item.session_id,
      session_id:item.session_id,
      provider:item.provider,
      model:item.model,
      last_provider:item.last_provider,
      last_model:item.last_model,
      bago_mode:item.bago_mode,
      active_agent:item.active_agent,
      active_bridges:item.active_bridges,
      health:item.health,
      messages:item.messages,
      total_calls:item.total_calls,
      total_tokens:item.total_tokens,
      agents:item.agents,
      providers:item.providers
    }))};
  }
  if(action==='status'){
    const id=getArg('--session-id')||activeId;
    const session=pmNormalizeLocalSession(findSession(id)||list[0]);
    activeId=session.session_id;
    pmWriteLocalSessions(list,activeId);
    return {ok:true,session};
  }
  if(action==='create'){
    const session=pmNormalizeLocalSession({session_id:'local-session-'+Date.now().toString(36)});
    list=[session].concat(list);
    activeId=session.session_id;
    pmWriteLocalSessions(list,activeId);
    return {ok:true,session};
  }
  if(action==='apply'){
    const id=getArg('--session-id')||activeId;
    const index=list.findIndex(item=>item.session_id===id);
    const base=pmNormalizeLocalSession(index>=0?list[index]:activeSession());
    base.provider=getArg('--provider')||base.provider;
    base.model=getArg('--model')||base.model;
    base.bago_mode=getArg('--mode')||base.bago_mode;
    base.active_agent=getArg('--agent')||base.active_agent;
    const bridges=getArg('--bridges');
    if(bridges!==''||safe.includes('--bridges')) base.active_bridges=bridges?bridges.split(',').map(item=>item.trim()).filter(Boolean):[];
    base.last_provider=base.provider;
    base.last_model=base.model;
    if(index>=0) list[index]=base; else list.unshift(base);
    activeId=base.session_id;
    pmWriteLocalSessions(list,activeId);
    return {ok:true,session:base};
  }
  if(action==='send'){
    const id=getArg('--session-id')||activeId;
    const prompt=getArg('--prompt');
    const index=list.findIndex(item=>item.session_id===id);
    const session=pmNormalizeLocalSession(index>=0?list[index]:activeSession());
    const userMessage={role:'user',content:prompt,ts:new Date().toISOString(),source:'browser-local'};
    const assistantMessage={role:'assistant',content:'[modo local] '+prompt,ts:new Date().toISOString(),source:'browser-local'};
    session.history=[].concat(session.history||[],userMessage,assistantMessage).slice(-60);
    session.messages=Number(session.messages||0)+2;
    session.total_calls=Number(session.total_calls||0)+1;
    session.total_tokens=Number(session.total_tokens||0)+Math.max(8,prompt.length);
    if(safe.includes('--orchestrate')) session.health={ok:true,detail:'orchestrate local'};
    if(index>=0) list[index]=session; else list.unshift(session);
    activeId=session.session_id;
    pmWriteLocalSessions(list,activeId);
    return {ok:true,session,response:{local:{ok:true,mode:safe.includes('--orchestrate')?'orchestrate':'send'}}};
  }
  throw new Error('Accion de sesión no soportada en modo local: '+action);
}
function pmLocalNodeSnapshot(){
  const payload=pmGetLocalPayload();
  const installations=Array.isArray(payload&&payload.installations)?payload.installations:[];
  const pieces=Array.isArray(payload&&payload.pieces)?payload.pieces:[];
  const connectors=Array.isArray(payload&&payload.connectors)?payload.connectors:[];
  const matrix=payload&&payload.matrix&&typeof payload.matrix==='object'?payload.matrix:{installations:installations.map(item=>({
    installation_id:item.installation_id||item.path||'',
    path:item.path||'',
    mode:item.mode||item.profile||'browser-local'
  })),rows:[]};
  return {
    status:{
      installations:installations.length,
      pieces:pieces.length,
      connectors:connectors.length,
      installations_data:installations,
      pieces_data:pieces,
      connectors_data:connectors,
      compatibility_data:Array.isArray(payload&&payload.compatibility_data)?payload.compatibility_data:[],
      modes:payload&&payload.modes&&typeof payload.modes==='object'?payload.modes:{},
      piece_inventory:Array.isArray(payload&&payload.piece_inventory)?payload.piece_inventory:[],
      evidence_file:'browser-local',
      base_path:'browser-local',
      store_root:'browser-local',
      unmaterialized_connectors:Math.max(0,installations.length*pieces.length-connectors.length)
    },
    matrix,
    pieces:{pieces},
    connectors:{connectors},
    evidence:{entries:[{timestamp:new Date().toISOString(),action:'local-cache',actor:'browser',result:payload?'ok':'empty',target:{source:'local-storage'}}]}
  };
}
function pmLocalNodeValidate(){
  const snapshot=pmLocalNodeSnapshot();
  const status=snapshot.status||{};
  const hasPayload=!!pmGetLocalPayload();
  const failures=[];
  if(!hasPayload)failures.push('no hay payload local');
  if(!Array.isArray(status.installations_data))failures.push('installations_data ausente');
  return {
    ok:hasPayload && failures.length===0,
    data:{
      installations:status.installations||0,
      pieces:status.pieces||0,
      connectors:status.connectors||0,
      failures:failures.length,
      source:'browser-local'
    },
    error:failures.join(' · ')
  };
}
function pmDownloadJson(filename,data){
  try{
    const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});
    const url=URL.createObjectURL(blob);
    const a=document.createElement('a');
    a.href=url;
    a.download=filename||'bago-export.json';
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
    showToast('descarga preparada: '+a.download,true);
    return true;
  }catch(e){
    showToast('no se pudo descargar: '+(e.message||''),false);
    return false;
  }
}
function pmLocalSystemStamp(action,detail){
  const state=pmReadLocalRuntime();
  state.system={lastAction:action,lastDetail:detail||'',lastAt:new Date().toISOString()};
  pmWriteLocalRuntime(state);
  window.__bagoLocalSystemState=state.system;
  return state.system;
}

function electronApi(){return window.bagoElectron||null;}
function copyText(t){
  const api=electronApi();
  if(api&&api.writeClipboardText){api.writeClipboardText(t);showToast('comando copiado al portapapeles',true);return Promise.resolve();}
  if(navigator.clipboard&&navigator.clipboard.writeText){return navigator.clipboard.writeText(t).then(()=>showToast('comando copiado al portapapeles',true),()=>fallbackCopy(t));}
  return Promise.resolve(fallbackCopy(t));
}
function readTextClipboard(){
  const api=electronApi();
  if(api&&api.readClipboardText)return Promise.resolve(api.readClipboardText());
  if(navigator.clipboard&&navigator.clipboard.readText)return navigator.clipboard.readText();
  return Promise.reject(new Error('Clipboard API no disponible'));
}
function fallbackCopy(t){const ta=document.createElement('textarea');ta.value=t;document.body.appendChild(ta);ta.select();try{document.execCommand('copy');showToast('comando copiado',true);}catch(e){showToast('no se pudo copiar',false);}document.body.removeChild(ta);}
async function openWebChat(){
  // Navegar al tab BAGO dentro del gestor en lugar de abrir ventana separada
  const btn = document.querySelector('[data-pm-view="bago"]');
  if(btn){btn.click();showToast('chat BAGO abierto en la pestaña local',true);return;}
  // Fallback si el tab no existe (contexto externo)
  const api=electronApi();
  if(!api||!api.openWebChat){
    showToast('chat web no disponible en Electron; usa la pestaña local BAGO',false);
    return;
  }
  try{
    const result=await api.openWebChat({});
    showToast('chat web abierto'+(result&&result.port?' · puerto '+result.port:''),true);
  }catch(e){
    showToast('chat web: '+e.message,false);
  }
}
async function openCliChat(){
  const api=electronApi();
  if(!api||!api.openCliChat){
    await copyText('python -m bago_core.launcher chat');
    pmLocalSystemStamp('open-cli-chat','fallback web');
    showToast('chat CLI no disponible en Electron; comando copiado',false);
    return;
  }
  try{
    const result=await api.openCliChat({});
    showToast('chat CLI lanzado'+(result&&result.pid?' · pid '+result.pid:''),true);
  }catch(e){
    showToast('chat CLI: '+e.message,false);
  }
}
function fallbackCopy(t){const ta=document.createElement('textarea');ta.value=t;document.body.appendChild(ta);ta.select();try{document.execCommand('copy');showToast('comando copiado',true);}catch(e){showToast('no se pudo copiar',false);}document.body.removeChild(ta);}

function escapeHtml(s){return String(s).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}

const inputArea=document.getElementById('input-area');
const installBox=document.getElementById('installations');
const emptyState=document.getElementById('empty-state');
const summaryBar=document.getElementById('summary-bar');
const releaseSummary=document.getElementById('release-summary');
const releaseList=document.getElementById('release-list');
const nodePanel=document.getElementById('node-panel');
const nodeCmdLabel=document.getElementById('node-cmd');
const releasesPanel=document.getElementById('releases-panel');
const rolePanel=document.getElementById('role-panel');
const roleCards=document.getElementById('role-cards');
const roleFileLabel=document.getElementById('role-file');
const ROLE_DEFS={
  active:{label:'Uso / activa',desc:'La copia que ejecuta `bago` sin subcomando.'},
  dev:{label:'Desarrollo',desc:'La copia que ejecuta `bago des` y donde editas código.'},
  launch:{label:'Lanzamiento',desc:'La plataforma que ejecuta `bago ign`.'}
};
const ROLE_ORDER=['active','dev','launch'];
const ROLE_STORAGE_KEY='bago.install.selection';
let latestRelease=null;
let releaseItems=[];
let releaseJobs=[];
let installSelection={version:1,updated_at:'',roles:{}};
let currentPayload=null;
let nodeCache={status:null,matrix:null,pieces:null,connectors:null,evidence:null};
let activeNodeTab='overview';

if(nodePanel&&releasesPanel&&releasesPanel.parentNode){
  releasesPanel.parentNode.insertBefore(nodePanel,releasesPanel);
}
