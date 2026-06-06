const PM_CHAIN_TYPES=['prompt','agent','command','tool','script','config'];
let pmChainRegistry={version:1,updated_at:'',chains:[]};
let pmActiveChain=null;
let pmPatchSurface=localStorage.getItem('bago.pm.patch.surface')||'connectors';
let pmSelectedChainStageId='';
let pmSelectedChainStepId='';
let pmChainDirty=false;

function pmChainId(prefix){
  return prefix+'-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,7);
}
function pmDefaultChain(){
  return {
    id:pmChainId('chain'),
    name:'Flujo BAGO',
    mode:'mixed',
    stages:[
      {id:pmChainId('stage'),mode:'serial',steps:[{id:pmChainId('step'),type:'prompt',label:'Objetivo',value:'Define el resultado y los criterios de éxito.'}]},
      {id:pmChainId('stage'),mode:'parallel',steps:[
        {id:pmChainId('step'),type:'tool',label:'Inspeccionar',value:'Recopilar estado y evidencia.'},
        {id:pmChainId('step'),type:'script',label:'Validar',value:'Ejecutar comprobaciones reproducibles.'}
      ]},
      {id:pmChainId('stage'),mode:'serial',steps:[{id:pmChainId('step'),type:'agent',label:'Resolver',value:'Planear, implementar y verificar el resultado.'}]}
    ],
    updated_at:''
  };
}
function pmDefaultChainStep(){
  return {id:pmChainId('step'),type:'tool',label:'Nuevo nodo',ref:'',value:'',enabled:true};
}
function pmChainClone(value){return JSON.parse(JSON.stringify(value));}
function pmChainModeLabel(mode){return mode==='parallel'?'paralelo':mode==='mixed'?'mixto':mode==='atomic'?'atómico':'serie';}
function pmChainFindStage(stageId){return (pmActiveChain&&pmActiveChain.stages||[]).find(stage=>stage.id===stageId)||null;}
function pmChainFindStep(stage,stepId){return (stage&&stage.steps||[]).find(step=>step.id===stepId)||null;}
function pmChainLocateStep(stepId){
  for(let stageIndex=0;stageIndex<(pmActiveChain&&pmActiveChain.stages||[]).length;stageIndex++){
    const stage=pmActiveChain.stages[stageIndex],stepIndex=(stage.steps||[]).findIndex(step=>step.id===stepId);
    if(stepIndex>=0)return {stage,stageIndex,step:stage.steps[stepIndex],stepIndex};
  }
  return null;
}
function pmEnsureChainSelection(){
  const located=pmChainLocateStep(pmSelectedChainStepId);
  if(located){pmSelectedChainStageId=located.stage.id;return;}
  if(pmSelectedChainStageId&&!pmSelectedChainStepId&&pmChainFindStage(pmSelectedChainStageId))return;
  const stage=pmChainFindStage(pmSelectedChainStageId)||(pmActiveChain&&pmActiveChain.stages||[])[0]||null;
  pmSelectedChainStageId=stage&&stage.id||'';
  pmSelectedChainStepId=stage&&stage.steps&&stage.steps[0]&&stage.steps[0].id||'';
}
function pmMarkChainDirty(){
  pmChainDirty=true;
  if(pmActiveChain)pmActiveChain.updated_at='';
}
function pmAtomicizeStage(stage,preserveId){
  const steps=Array.isArray(stage&&stage.steps)?stage.steps.filter(Boolean):[];
  if(!steps.length){
    return [{id:preserveId?stage.id:pmChainId('stage'),mode:'serial',steps:[]}];
  }
  return steps.map((step,index)=>({
    id:index===0&&preserveId?stage.id:pmChainId('stage'),
    mode:'serial',
    steps:[pmChainClone(step)]
  }));
}
function pmNormalizeAtomicChain(chain){
  const normalized=pmChainClone(chain);
  const nextStages=[];
  (normalized.stages||[]).forEach((stage,index)=>{
    nextStages.push(...pmAtomicizeStage(stage,index===0));
  });
  if(!nextStages.length){
    nextStages.push({id:pmChainId('stage'),mode:'serial',steps:[pmDefaultChainStep()]});
  }
  normalized.mode='atomic';
  normalized.stages=nextStages;
  return normalized;
}
function pmSetAtomicMode(){
  if(!pmActiveChain)return;
  pmActiveChain=pmNormalizeAtomicChain(pmActiveChain);
  pmChainDirty=true;
}
function pmSetPatchSurfaceControls(){
  const chainMode=pmPatchSurface==='chain';
  document.querySelectorAll('[data-pm-chain-only]').forEach(control=>{control.hidden=!chainMode;});
  document.getElementById('pm-patch-chain').hidden=!chainMode;
  document.getElementById('pm-install-filter').hidden=chainMode;
  document.getElementById('pm-reset-layout').textContent=chainMode?'Reencajar':'Centrar';
}
function pmAddChainStage(){
  const stage={id:pmChainId('stage'),mode:'serial',steps:pmActiveChain.mode==='atomic'?[pmDefaultChainStep()]:[]};
  pmActiveChain.stages.push(stage);
  pmSelectedChainStageId=stage.id;pmSelectedChainStepId=stage.steps[0]&&stage.steps[0].id||'';pmMarkChainDirty();
  if(pmActiveChain.mode==='atomic')pmSetAtomicMode();
  pmRenderChain();
}
function pmAddChainStep(stageId){
  if(pmActiveChain.mode==='atomic'){
    const selected=pmChainFindStage(stageId)||pmChainFindStage(pmSelectedChainStageId)||(pmActiveChain.stages||[]).slice(-1)[0];
    const stage={id:pmChainId('stage'),mode:'serial',steps:[pmDefaultChainStep()]};
    const index=selected?pmActiveChain.stages.findIndex(item=>item.id===selected.id):-1;
    pmActiveChain.stages.splice(index>=0?index+1:pmActiveChain.stages.length,0,stage);
    pmSelectedChainStageId=stage.id;
    pmSelectedChainStepId=stage.steps[0].id;
    pmMarkChainDirty();
    pmSetAtomicMode();
    pmRenderChain();
    return;
  }
  let stage=pmChainFindStage(stageId)||pmChainFindStage(pmSelectedChainStageId)||(pmActiveChain.stages||[]).slice(-1)[0];
  if(!stage){
    stage={id:pmChainId('stage'),mode:'serial',steps:[]};pmActiveChain.stages.push(stage);
  }
  const step=pmDefaultChainStep();
  stage.steps.push(step);pmSelectedChainStageId=stage.id;pmSelectedChainStepId=step.id;pmMarkChainDirty();pmRenderChain();
}
function pmMoveChainStep(stepId,targetStageId){
  const located=pmChainLocateStep(stepId),target=pmChainFindStage(targetStageId);
  if(!located||!target||located.stage.id===target.id)return;
  target.steps.push(...located.stage.steps.splice(located.stepIndex,1));
  pmSelectedChainStageId=target.id;pmSelectedChainStepId=stepId;pmMarkChainDirty();pmRenderChain();
}
function pmApplyChainAction(action,stageId,stepId){
  const stage=pmChainFindStage(stageId),stageIndex=(pmActiveChain.stages||[]).findIndex(item=>item.id===stageId);
  const located=pmChainLocateStep(stepId);
  if(action==='stage-add')return pmAddChainStep(stageId);
  if(action==='stage-left')pmMoveItem(pmActiveChain.stages,stageIndex,-1);
  if(action==='stage-right')pmMoveItem(pmActiveChain.stages,stageIndex,1);
  if(action==='stage-delete'&&stageIndex>=0){pmActiveChain.stages.splice(stageIndex,1);pmSelectedChainStageId='';pmSelectedChainStepId='';}
  if(located){
    if(action==='step-up')pmMoveItem(located.stage.steps,located.stepIndex,-1);
    if(action==='step-down')pmMoveItem(located.stage.steps,located.stepIndex,1);
    if(action==='step-left'&&located.stageIndex>0)return pmMoveChainStep(stepId,pmActiveChain.stages[located.stageIndex-1].id);
    if(action==='step-right'&&located.stageIndex<pmActiveChain.stages.length-1)return pmMoveChainStep(stepId,pmActiveChain.stages[located.stageIndex+1].id);
    if(action==='step-duplicate'){
      const copy=pmChainClone(located.step);copy.id=pmChainId('step');copy.label=(copy.label||'Nodo')+' copia';
      located.stage.steps.splice(located.stepIndex+1,0,copy);pmSelectedChainStepId=copy.id;pmSelectedChainStageId=located.stage.id;
    }
    if(action==='step-delete'){located.stage.steps.splice(located.stepIndex,1);pmSelectedChainStepId='';}
  }
  if(pmActiveChain.mode==='atomic')pmSetAtomicMode();
  pmMarkChainDirty();pmEnsureChainSelection();pmRenderChain();
}
function pmChainOptions(){
  const rows=pmChainRegistry.chains||[];
  return rows.map(chain=>'<option value="'+escapeHtml(chain.id)+'">'+escapeHtml(chain.id===pmActiveChain.id?pmActiveChain.name||'Sin nombre':chain.name||'Sin nombre')+'</option>').join('')+(pmActiveChain&&!rows.some(chain=>chain.id===pmActiveChain.id)?'<option value="'+escapeHtml(pmActiveChain.id)+'">Borrador · '+escapeHtml(pmActiveChain.name||'Sin nombre')+'</option>':'');
}
function pmChainStepHtml(step,stageIndex,stepIndex,stageCount,stepCount){
  const options=PM_CHAIN_TYPES.map(type=>'<option value="'+type+'"'+(step.type===type?' selected':'')+'>'+type+'</option>').join('');
  return '<article class="pm-chain-step" data-chain-step="'+escapeHtml(step.id)+'">'
    +'<div class="pm-chain-step-head"><select class="pm-select" data-chain-step-field="type">'+options+'</select><span>#'+(stepIndex+1)+'</span></div>'
    +'<input class="pm-input" data-chain-step-field="label" value="'+escapeHtml(step.label||'')+'" placeholder="Nombre">'
    +'<textarea data-chain-step-field="value" placeholder="Prompt, comando, tool, script o configuración">'+escapeHtml(step.value||'')+'</textarea>'
    +'<div class="pm-chain-step-actions"><button data-chain-step-action="up"'+(stepIndex===0?' disabled':'')+'>↑</button><button data-chain-step-action="down"'+(stepIndex===stepCount-1?' disabled':'')+'>↓</button><button data-chain-step-action="left"'+(stageIndex===0?' disabled':'')+'>← etapa</button><button data-chain-step-action="right"'+(stageIndex===stageCount-1?' disabled':'')+'>etapa →</button><button data-chain-step-action="delete">×</button></div>'
    +'</article>';
}
function pmChainStageHtml(stage,index,count){
  const displayMode=pmActiveChain.mode==='mixed'?stage.mode:pmActiveChain.mode;
  const effective=pmActiveChain.mode==='mixed'?stage.mode:(pmActiveChain.mode==='atomic'?'serial':pmActiveChain.mode);
  const steps=(stage.steps||[]).map((step,stepIndex)=>pmChainStepHtml(step,index,stepIndex,count,stage.steps.length)).join('');
  return '<section class="pm-chain-stage '+escapeHtml(displayMode)+'" data-chain-stage="'+escapeHtml(stage.id)+'">'
    +'<div class="pm-chain-stage-head"><strong>Etapa '+(index+1)+'</strong><select class="pm-select" data-chain-stage-mode'+(pmActiveChain.mode==='mixed'?'':' disabled')+'><option value="serial"'+(stage.mode==='serial'?' selected':'')+'>Serie</option><option value="parallel"'+(stage.mode==='parallel'?' selected':'')+'>Paralelo</option></select></div>'
    +'<div class="pm-chain-steps">'+(steps||'<div class="pm-chain-empty">Etapa vacía</div>')+'</div>'
    +'<div class="pm-chain-stage-actions"><button data-chain-stage-action="add">+ Paso</button><button data-chain-stage-action="up"'+(index===0?' disabled':'')+'>←</button><button data-chain-stage-action="down"'+(index===count-1?' disabled':'')+'>→</button><button data-chain-stage-action="delete">Eliminar etapa</button></div>'
    +'</section>';
}
function pmRenderChain(){
  if(!pmActiveChain)return;
  pmEnsureChainSelection();
  document.getElementById('pm-chain-select').innerHTML=pmChainOptions();
  document.getElementById('pm-chain-select').value=pmActiveChain.id;
  document.getElementById('pm-chain-name').value=pmActiveChain.name||'';
  document.getElementById('pm-chain-mode').value=pmActiveChain.mode||'serial';
  document.getElementById('pm-chain-caption').textContent=(pmActiveChain.stages||[]).length+' etapas · '+(pmActiveChain.stages||[]).reduce((n,stage)=>n+(stage.steps||[]).length,0)+' pasos · '+pmChainModeLabel(pmActiveChain.mode)+(pmChainDirty?' · cambios sin guardar':pmActiveChain.updated_at?' · guardada':' · borrador');
  document.getElementById('pm-chain-track').innerHTML=(pmActiveChain.stages||[]).map(pmChainStageHtml).join('')||'<div class="pm-empty">Añade una etapa para diseñar la cadena.</div>';
  pmSyncPatchChainOptions();
  if(pmPatchSurface==='chain')pmRenderPatchChain();
}
function pmSyncPatchChainOptions(){
  const select=document.getElementById('pm-patch-chain');
  if(!select||!pmActiveChain)return;
  select.innerHTML=pmChainOptions();
  select.value=pmActiveChain.id;
}
function pmRenderChainDetail(){
  const container=document.getElementById('pm-detail'),title=document.getElementById('pm-detail-title');
  if(!container||!title||!pmActiveChain)return;
  pmEnsureChainSelection();
  const located=pmChainLocateStep(pmSelectedChainStepId),stage=located&&located.stage||pmChainFindStage(pmSelectedChainStageId);
  document.getElementById('pm-chain-ref-options').innerHTML=pmPieces().map(piece=>'<option value="'+escapeHtml(piece.piece_id)+'"></option>').join('');
  if(located){
    const step=located.step,types=PM_CHAIN_TYPES.map(type=>'<option value="'+type+'"'+(step.type===type?' selected':'')+'>'+type+'</option>').join('');
    title.textContent='Interior del nodo';
    container.innerHTML='<div class="pm-detail-form">'
      +'<div><h3>'+escapeHtml(step.label||'Nodo sin nombre')+'</h3><div class="pm-detail-sub">'+escapeHtml(step.id)+' · etapa '+(located.stageIndex+1)+' · posición '+(located.stepIndex+1)+'</div></div>'
      +'<label class="pm-detail-field">Tipo<select class="pm-select" data-chain-inspector-field="type">'+types+'</select></label>'
      +'<label class="pm-detail-field">Nombre<input class="pm-input" data-chain-inspector-field="label" value="'+escapeHtml(step.label||'')+'"></label>'
      +'<label class="pm-detail-field">Referencia / comando<input class="pm-input" list="pm-chain-ref-options" data-chain-inspector-field="ref" value="'+escapeHtml(step.ref||'')+'" placeholder="tool.*, script, comando o ruta"></label>'
      +'<label class="pm-detail-field">Interior<textarea data-chain-inspector-field="value" placeholder="Prompt, argumentos, script o configuración">'+escapeHtml(step.value||'')+'</textarea></label>'
      +'<label class="pm-detail-check"><input type="checkbox" data-chain-inspector-field="enabled"'+(step.enabled===false?'':' checked')+'> Nodo activo</label>'
      +'<div class="pm-kv"><div><span>Etapa</span><strong>'+escapeHtml(String(located.stageIndex+1))+' / '+escapeHtml(pmChainModeLabel(pmActiveChain.mode==='mixed'?stage.mode:pmActiveChain.mode))+'</strong></div><div><span>Entradas</span><strong>'+(located.stageIndex?'etapa '+located.stageIndex:'inicio')+'</strong></div><div><span>Salida</span><strong>'+(located.stageIndex<pmActiveChain.stages.length-1?'etapa '+(located.stageIndex+2):'fin')+'</strong></div></div>'
      +'<div class="pm-detail-actions"><button data-chain-detail-action="step-up"'+(located.stepIndex===0?' disabled':'')+'>↑ Orden</button><button data-chain-detail-action="step-down"'+(located.stepIndex===stage.steps.length-1?' disabled':'')+'>↓ Orden</button><button data-chain-detail-action="step-left"'+(located.stageIndex===0?' disabled':'')+'>← Etapa</button><button data-chain-detail-action="step-right"'+(located.stageIndex===pmActiveChain.stages.length-1?' disabled':'')+'>Etapa →</button><button data-chain-detail-action="step-duplicate">Duplicar</button><button class="danger" data-chain-detail-action="step-delete">Eliminar</button><button class="pm-btn primary" data-chain-detail-action="save">Guardar cadena</button></div>'
      +'</div>';
    return;
  }
  if(stage){
    const stageIndex=pmActiveChain.stages.findIndex(item=>item.id===stage.id);
    title.textContent='Interior de la etapa';
    container.innerHTML='<div class="pm-detail-form"><div><h3>Etapa '+(stageIndex+1)+'</h3><div class="pm-detail-sub">'+escapeHtml(stage.id)+' · '+(stage.steps||[]).length+' nodos</div></div>'
      +'<label class="pm-detail-field">Ejecución<select class="pm-select" data-chain-inspector-stage-mode'+(pmActiveChain.mode==='mixed'?'':' disabled')+'><option value="serial"'+(stage.mode==='serial'?' selected':'')+'>Serie</option><option value="parallel"'+(stage.mode==='parallel'?' selected':'')+'>Paralelo</option></select></label>'
      +'<div class="pm-detail-actions"><button data-chain-detail-action="stage-add">+ Nodo</button><button data-chain-detail-action="stage-left"'+(stageIndex===0?' disabled':'')+'>← Mover etapa</button><button data-chain-detail-action="stage-right"'+(stageIndex===pmActiveChain.stages.length-1?' disabled':'')+'>Mover etapa →</button><button class="danger" data-chain-detail-action="stage-delete">Eliminar etapa</button><button class="pm-btn primary" data-chain-detail-action="save">Guardar cadena</button></div></div>';
    return;
  }
  title.textContent='Cadena';
  container.innerHTML='<div class="pm-empty">Selecciona un nodo o una etapa para abrir su interior.</div>';
}
function pmRenderPatchChain(renderDetail=true){
  const stage=document.getElementById('pm-stage'),layout=document.getElementById('pm-patch-layout');
  if(!stage||!layout||!pmActiveChain)return;
  pmEnsureChainSelection();
  pmSetPatchSurfaceControls();
  layout.classList.add('chain-mode');
  stage.classList.add('chain-view');
  stage.style.minWidth='960px';
  const stages=pmActiveChain.stages||[];
  document.getElementById('pm-patch-caption').textContent=pmActiveChain.name+' · '+stages.length+' etapas · '+pmChainModeLabel(pmActiveChain.mode)+(pmChainDirty?' · sin guardar':'');
  if(!stages.length){stage.innerHTML='<div class="pm-empty">La cadena no contiene etapas.</div>';if(renderDetail)pmRenderChainDetail();return;}
  const maxSteps=Math.max(1,...stages.map(item=>Math.max(1,(item.steps||[]).length)));
  const canvasWidth=Math.max(stage.clientWidth||0,960,stages.length*260);
  stage.style.minWidth=canvasWidth+'px';
  const stageWidth=Math.max(240,Math.floor((canvasWidth-100)/stages.length));
  const height=Math.max(650,maxSteps*155+150);
  stage.style.height=height+'px';
  const stageCards=[],nodes=[],paths=[];
  stages.forEach((chainStage,stageIndex)=>{
    const steps=chainStage.steps||[];
    const x=60+stageWidth*stageIndex+stageWidth/2;
    const displayMode=pmActiveChain.mode==='mixed'?chainStage.mode:pmActiveChain.mode;
    const effective=pmActiveChain.mode==='mixed'?chainStage.mode:(pmActiveChain.mode==='atomic'?'serial':pmActiveChain.mode);
    stageCards.push('<div class="pm-flow-stage '+escapeHtml(displayMode)+' '+(pmSelectedChainStageId===chainStage.id&&!pmSelectedChainStepId?'selected':'')+'" data-chain-flow-stage="'+escapeHtml(chainStage.id)+'" style="left:'+(x-stageWidth/2+12)+'px;width:'+(stageWidth-24)+'px"><strong>Etapa '+(stageIndex+1)+'</strong><span>'+escapeHtml(pmChainModeLabel(displayMode))+' · '+steps.length+' nodos · suelta aquí</span></div>');
    steps.forEach((step,stepIndex)=>{
      const spread=effective==='parallel'?Math.max(1,steps.length):Math.max(1,steps.length);
      const y=130+(height-220)*(stepIndex+.5)/spread;
      const nodeId='pm-flow-'+stageIndex+'-'+stepIndex;
      nodes.push('<div class="pm-flow-node '+escapeHtml(step.type||'tool')+' '+(step.enabled===false?'disabled ':'')+(pmSelectedChainStepId===step.id?'selected':'')+'" id="'+nodeId+'" draggable="true" data-chain-flow-step="'+escapeHtml(step.id)+'" data-chain-flow-stage="'+escapeHtml(chainStage.id)+'" style="left:'+x+'px;top:'+y+'px"><span>'+escapeHtml(step.type||'tool')+'</span><strong>'+escapeHtml(step.label||'Sin nombre')+'</strong><small>'+escapeHtml(step.ref||step.value||'Sin configuración')+'</small></div>');
      if(effective==='serial'&&stepIndex>0)paths.push('<path data-from="pm-flow-'+stageIndex+'-'+(stepIndex-1)+'" data-to="'+nodeId+'"/>');
    });
    if(stageIndex>0){
      const previous=stages[stageIndex-1].steps||[];
      const targets=effective==='parallel'?steps:steps.slice(0,1);
      const sources=(pmActiveChain.mode==='mixed'?stages[stageIndex-1].mode:(pmActiveChain.mode==='atomic'?'serial':pmActiveChain.mode))==='parallel'?previous:previous.slice(-1);
      sources.forEach((_source,sourceIndex)=>targets.forEach((_target,targetIndex)=>paths.push('<path data-from="pm-flow-'+(stageIndex-1)+'-'+(sources.length===previous.length?sourceIndex:previous.length-1)+'" data-to="pm-flow-'+stageIndex+'-'+targetIndex+'"/>')));
    }
  });
  stage.innerHTML='<svg class="pm-patch-svg pm-flow-svg" id="pm-patch-svg">'+paths.join('')+'</svg>'+stageCards.join('')+nodes.join('');
  stage.querySelectorAll('[data-chain-flow-step]').forEach(node=>{
    node.addEventListener('click',()=>{pmSelectedChainStepId=node.dataset.chainFlowStep||'';pmSelectedChainStageId=node.dataset.chainFlowStage||'';pmRenderPatchChain();});
    node.addEventListener('dragstart',event=>{event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('text/plain',node.dataset.chainFlowStep||'');});
  });
  stage.querySelectorAll('.pm-flow-stage[data-chain-flow-stage]').forEach(card=>{
    card.addEventListener('click',()=>{pmSelectedChainStageId=card.dataset.chainFlowStage||'';pmSelectedChainStepId='';pmRenderPatchChain();});
    card.addEventListener('dragover',event=>{event.preventDefault();card.classList.add('drop-target');});
    card.addEventListener('dragleave',()=>card.classList.remove('drop-target'));
    card.addEventListener('drop',event=>{event.preventDefault();card.classList.remove('drop-target');pmMoveChainStep(event.dataTransfer.getData('text/plain'),card.dataset.chainFlowStage||'');});
  });
  stage.addEventListener('dragend',()=>stage.querySelectorAll('.drop-target').forEach(item=>item.classList.remove('drop-target')),{once:true});
  setTimeout(pmUpdatePatchLines,20);
  if(renderDetail)pmRenderChainDetail();
}
async function pmLoadChains(){
  const api=electronApi();
  if(api&&api.readChainRegistry){
    try{pmChainRegistry=await api.readChainRegistry();}catch(e){showToast('No se pudieron cargar las cadenas: '+e.message,false);}
  }else{
    try{pmChainRegistry=JSON.parse(localStorage.getItem('bago.pm.chains')||'null')||pmChainRegistry;}catch{}
  }
  pmActiveChain=pmChainClone((pmChainRegistry.chains||[])[0]||pmDefaultChain());
  if(pmActiveChain.mode==='atomic')pmActiveChain=pmNormalizeAtomicChain(pmActiveChain);
  pmChainDirty=false;pmSelectedChainStageId='';pmSelectedChainStepId='';
  pmRenderChain();
}
async function pmSaveChains(){
  if(pmActiveChain.mode==='atomic')pmActiveChain=pmNormalizeAtomicChain(pmActiveChain);
  pmActiveChain.name=(pmActiveChain.name||'Cadena sin nombre').trim()||'Cadena sin nombre';
  pmActiveChain.updated_at=new Date().toISOString();
  const index=(pmChainRegistry.chains||[]).findIndex(chain=>chain.id===pmActiveChain.id);
  if(index>=0)pmChainRegistry.chains[index]=pmChainClone(pmActiveChain);else pmChainRegistry.chains.push(pmChainClone(pmActiveChain));
  const api=electronApi();
  try{
    if(api&&api.writeChainRegistry)pmChainRegistry=await api.writeChainRegistry(pmChainRegistry);
    else localStorage.setItem('bago.pm.chains',JSON.stringify(pmChainRegistry));
    pmChainDirty=false;
    pmAudit('chain','Cadena guardada: '+pmActiveChain.name);showToast('Cadena guardada',true);pmRenderChain();
  }catch(e){showToast('No se pudo guardar: '+e.message,false);}
}
function pmMoveItem(items,index,delta){
  const target=index+delta;if(index<0||target<0||target>=items.length)return;
  [items[index],items[target]]=[items[target],items[index]];
}
function pmInitChains(){
  const track=document.getElementById('pm-chain-track');
  const surface=document.getElementById('pm-patch-surface'),patchChain=document.getElementById('pm-patch-chain'),fullscreen=document.getElementById('pm-patch-fullscreen');
  surface.value=pmPatchSurface;
  pmSetPatchSurfaceControls();
  surface.addEventListener('change',ev=>{pmPatchSurface=ev.target.value;localStorage.setItem('bago.pm.patch.surface',pmPatchSurface);pmSetPatchSurfaceControls();pmRenderPatch();});
  patchChain.addEventListener('change',ev=>{const chain=(pmChainRegistry.chains||[]).find(row=>row.id===ev.target.value);if(chain){pmActiveChain=pmChainClone(chain);pmChainDirty=false;pmSelectedChainStageId='';pmSelectedChainStepId='';pmRenderChain();}});
  fullscreen.addEventListener('click',async()=>{
    const layout=document.getElementById('pm-patch-layout');
    try{if(document.fullscreenElement)await document.exitFullscreen();else await layout.requestFullscreen();}catch(e){showToast('Pantalla completa no disponible: '+e.message,false);}
  });
  document.addEventListener('fullscreenchange',()=>{fullscreen.textContent=document.fullscreenElement?'Salir de pantalla completa':'Pantalla completa';setTimeout(()=>pmPatchSurface==='chain'?pmRenderPatchChain():pmUpdatePatchLines(),40);});
  window.addEventListener('resize',()=>{if(pmPatchSurface==='chain')pmRenderPatchChain();});
  document.getElementById('pm-patch-add-node').addEventListener('click',()=>pmAddChainStep(pmSelectedChainStageId));
  document.getElementById('pm-patch-add-stage').addEventListener('click',pmAddChainStage);
  document.getElementById('pm-patch-save-chain').addEventListener('click',pmSaveChains);
  document.getElementById('pm-chain-new').addEventListener('click',()=>{pmActiveChain=pmDefaultChain();pmChainDirty=true;pmSelectedChainStageId='';pmSelectedChainStepId='';pmRenderChain();});
  document.getElementById('pm-chain-save').addEventListener('click',pmSaveChains);
  document.getElementById('pm-chain-delete').addEventListener('click',async()=>{
    if(!pmActiveChain||!window.confirm('Eliminar la cadena '+pmActiveChain.name+'?'))return;
    pmChainRegistry.chains=(pmChainRegistry.chains||[]).filter(chain=>chain.id!==pmActiveChain.id);
    pmActiveChain=pmChainClone(pmChainRegistry.chains[0]||pmDefaultChain());
    const api=electronApi();if(api&&api.writeChainRegistry)pmChainRegistry=await api.writeChainRegistry(pmChainRegistry);else localStorage.setItem('bago.pm.chains',JSON.stringify(pmChainRegistry));
    pmChainDirty=false;pmSelectedChainStageId='';pmSelectedChainStepId='';pmAudit('chain','Cadena eliminada');pmRenderChain();
  });
  document.getElementById('pm-chain-select').addEventListener('change',ev=>{const chain=(pmChainRegistry.chains||[]).find(row=>row.id===ev.target.value);if(chain){pmActiveChain=pmChainClone(chain);pmChainDirty=false;pmSelectedChainStageId='';pmSelectedChainStepId='';pmRenderChain();}});
  document.getElementById('pm-chain-name').addEventListener('input',ev=>{pmActiveChain.name=ev.target.value;pmMarkChainDirty();if(pmPatchSurface==='chain')pmRenderPatchChain(false);});
  document.getElementById('pm-chain-mode').addEventListener('change',ev=>{
    pmActiveChain.mode=ev.target.value;
    if(pmActiveChain.mode==='atomic')pmSetAtomicMode();
    pmMarkChainDirty();
    pmRenderChain();
  });
  document.getElementById('pm-chain-add-stage').addEventListener('click',pmAddChainStage);
  track.addEventListener('input',ev=>{
    const stageEl=ev.target.closest('[data-chain-stage]'),stepEl=ev.target.closest('[data-chain-step]');
    const stage=stageEl&&pmChainFindStage(stageEl.dataset.chainStage),step=stepEl&&pmChainFindStep(stage,stepEl.dataset.chainStep);
    const field=ev.target.dataset.chainStepField;if(step&&field){step[field]=ev.target.value;pmSelectedChainStageId=stage.id;pmSelectedChainStepId=step.id;pmMarkChainDirty();if(pmPatchSurface==='chain')pmRenderPatchChain(false);}
  });
  track.addEventListener('change',ev=>{
    const stageEl=ev.target.closest('[data-chain-stage]'),stage=stageEl&&pmChainFindStage(stageEl.dataset.chainStage);
    const stepEl=ev.target.closest('[data-chain-step]'),step=stepEl&&pmChainFindStep(stage,stepEl.dataset.chainStep);
    const field=ev.target.dataset.chainStepField;if(step&&field){step[field]=ev.target.value;pmSelectedChainStageId=stage.id;pmSelectedChainStepId=step.id;pmMarkChainDirty();}
    if(stage&&ev.target.matches('[data-chain-stage-mode]')){stage.mode=ev.target.value;pmSelectedChainStageId=stage.id;pmSelectedChainStepId='';pmMarkChainDirty();}
    pmRenderChain();
  });
  track.addEventListener('click',ev=>{
    const button=ev.target.closest('button');if(!button)return;
    const stageEl=button.closest('[data-chain-stage]'),stageIndex=pmActiveChain.stages.findIndex(stage=>stage.id===stageEl.dataset.chainStage);
    if(stageIndex<0)return;
    const stage=pmActiveChain.stages[stageIndex],stepEl=button.closest('[data-chain-step]');
    if(button.dataset.chainStageAction){
      const action=button.dataset.chainStageAction;
      pmApplyChainAction(action==='add'?'stage-add':action==='up'?'stage-left':action==='down'?'stage-right':'stage-delete',stage.id,'');
    }else if(button.dataset.chainStepAction&&stepEl){
      const action=button.dataset.chainStepAction;
      pmApplyChainAction('step-'+action,stage.id,stepEl.dataset.chainStep);
    }
  });
  document.getElementById('pm-detail').addEventListener('input',ev=>{
    if(pmPatchSurface!=='chain')return;
    const located=pmChainLocateStep(pmSelectedChainStepId),field=ev.target.dataset.chainInspectorField;
    if(!located||!field)return;
    located.step[field]=ev.target.type==='checkbox'?ev.target.checked:ev.target.value;
    pmMarkChainDirty();pmRenderPatchChain(false);
  });
  document.getElementById('pm-detail').addEventListener('change',ev=>{
    if(pmPatchSurface!=='chain')return;
    const located=pmChainLocateStep(pmSelectedChainStepId),field=ev.target.dataset.chainInspectorField;
    if(located&&field){located.step[field]=ev.target.type==='checkbox'?ev.target.checked:ev.target.value;pmMarkChainDirty();pmRenderPatchChain(false);}
    const stage=pmChainFindStage(pmSelectedChainStageId);
    if(stage&&ev.target.matches('[data-chain-inspector-stage-mode]')){stage.mode=ev.target.value;pmMarkChainDirty();pmRenderPatchChain(false);}
  });
  document.getElementById('pm-detail').addEventListener('click',ev=>{
    if(pmPatchSurface!=='chain')return;
    const button=ev.target.closest('[data-chain-detail-action]');if(!button)return;
    const action=button.dataset.chainDetailAction;
    if(action==='save'){pmSaveChains();return;}
    pmApplyChainAction(action,pmSelectedChainStageId,pmSelectedChainStepId);
  });
  pmLoadChains();
}
