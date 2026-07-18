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
const pmDependencyCatalog={
  core:[
    {id:'python',label:'Python',required:true,wingetId:'Python.Python.3.11',installCommand:'winget install -e --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements'},
    {id:'powershell',label:'PowerShell',required:true,wingetId:'',installCommand:''},
    {id:'git',label:'Git',required:false,wingetId:'Git.Git',installCommand:'winget install -e --id Git.Git --accept-package-agreements --accept-source-agreements'},
    {id:'ollama',label:'Ollama',required:false,wingetId:'Ollama.Ollama',installCommand:'winget install -e --id Ollama.Ollama --accept-package-agreements --accept-source-agreements'}
  ],
  providers:{
    'ollama-local':{label:'Ollama local',authModes:['install'],installTarget:'ollama',primaryKey:'OLLAMA_HOST',optionalKeys:[]},
    'ollama-cloud':{label:'Ollama Cloud',authModes:['api'],primaryKey:'OLLAMA_CLOUD_KEY',optionalKeys:['OLLAMA_CLOUD_URL']},
    'copilot':{label:'GitHub Copilot',authModes:['api','login'],primaryKey:'GITHUB_TOKEN',optionalKeys:[],loginCommand:'copilot login'},
    'anthropic':{label:'Anthropic',authModes:['api'],primaryKey:'ANTHROPIC_API_KEY',optionalKeys:[]},
    'codex':{label:'Codex / OpenAI',authModes:['api','login'],primaryKey:'OPENAI_API_KEY',optionalKeys:['OPENAI_ORG_ID'],loginCommand:'codex login'},
    'openrouter':{label:'OpenRouter',authModes:['api'],primaryKey:'OPENROUTER_API_KEY',optionalKeys:['OPENROUTER_HTTP_REFERER']},
    'opencode':{label:'OpenCode',authModes:['api'],primaryKey:'OPENCODE_API_KEY',optionalKeys:['OPENCODE_BASE_URL']}
  }
};
function pmDependencySpec(id){
  return pmDependencyCatalog.core.find(item=>item.id===id)||null;
}
function pmProviderSpec(name){
  return pmDependencyCatalog.providers[name]||{label:name,authModes:[],primaryKey:'',optionalKeys:[]};
}
function pmProviderAuthModes(name){
  return Array.isArray(pmProviderSpec(name).authModes)?pmProviderSpec(name).authModes.slice():[];
}
function pmProviderPrimaryKey(name){
  return pmProviderSpec(name).primaryKey||'';
}
function pmProviderOptionalKeys(name){
  return Array.isArray(pmProviderSpec(name).optionalKeys)?pmProviderSpec(name).optionalKeys.slice():[];
}
function pmProviderLoginCommand(name){
  return pmProviderSpec(name).loginCommand||'';
}
function pmDependencyInstallCommand(id){
  return (pmDependencySpec(id)||{}).installCommand||'';
}
function pmBrowserOnlyError(feature){
  return new Error(feature+' no está disponible sin Electron/backend operativo');
}
function pmLocalSessionCommand(){
  throw pmBrowserOnlyError('Gestor de sesiones');
}
function pmLocalNodeSnapshot(){
  throw pmBrowserOnlyError('Node Control');
}
function pmLocalNodeValidate(){
  return {ok:false,error:'Node Control no está disponible sin Electron/backend operativo'};
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
  return {lastAction:action,lastDetail:detail||'',lastAt:new Date().toISOString(),unavailable:true};
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
  const api=electronApi();
  if(!api||typeof api.openWebChat!=='function'){
    showToast('chat web no disponible sin Electron/backend operativo',false);
    return;
  }
  try{
    const session = typeof pmCurrentSession === 'function' ? pmCurrentSession() : null;
    const provider = session && session.provider ? session.provider : '';
    const model = session && session.model ? session.model : '';
    const bridges = session && Array.isArray(session.active_bridges) ? session.active_bridges : [];
    const sessionId = session && (session.session_id || session.sid) ? (session.session_id || session.sid) : '';
    const result=await api.openWebChat({sessionId,provider,model,bridges});
    showToast('chat web abierto'+(result&&result.port?' · puerto '+result.port:''),true);
  }catch(e){
    showToast('chat web: '+e.message,false);
  }
}
async function openCliChat(){
  const api=electronApi();
  if(!api||typeof api.openCliChat!=='function'){
    showToast('chat CLI no disponible sin Electron/backend operativo',false);
    return;
  }
  try{
    const session = typeof pmCurrentSession === 'function' ? pmCurrentSession() : null;
    const provider = session && session.provider ? session.provider : '';
    const model = session && session.model ? session.model : '';
    const sessionId = session && (session.session_id || session.sid) ? (session.session_id || session.sid) : '';
    const result=await api.openCliChat({sessionId,provider,model});
    if(result&&result.command){
      await copyText(result.command);
      showToast('comando CLI copiado; ejecútalo solo si quieres terminal externa',true);
      return;
    }
    showToast('chat CLI preparado'+(result&&result.pid?' · pid '+result.pid:''),true);
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
  active:{label:'Copia activa',desc:'La copia que ejecuta `bago` sin subcomando.'},
  dev:{label:'Desarrollo',desc:'La copia que ejecuta `bago des` y donde editas código.'},
  launch:{label:'Arranque principal',desc:'La copia que ejecuta `bago ign`.'},
  writer:{label:'Escritor',desc:'Copia orientada a redacción y texto.'},
  illustrator:{label:'Ilustrador',desc:'Copia orientada a piezas visuales.'}
};
const ROLE_ORDER=['active','dev','launch','writer','illustrator'];
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
