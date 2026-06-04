const toast=document.getElementById('toast');
function showToast(msg,ok=true){toast.textContent=msg;toast.className='toast '+(ok?'ok':'err');requestAnimationFrame(()=>toast.classList.add('show'));setTimeout(()=>toast.classList.remove('show'),2400);}

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
function canRunCommands(){const api=electronApi();return !!(api&&api.runCommand);}
async function runCommand(t){
  const api=electronApi();
  if(!api||!api.runCommand){showToast('ejecución directa solo disponible en Electron',false);return;}
  try{
    const result=await api.runCommand(t);
    showToast('comando lanzado en PowerShell'+(result&&result.pid?' · pid '+result.pid:''),true);
  }catch(e){
    showToast('no se pudo ejecutar: '+e.message,false);
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
