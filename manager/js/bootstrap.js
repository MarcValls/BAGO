// Ctrl+Enter en el textarea = parsear
inputArea.addEventListener('keydown',ev=>{if((ev.ctrlKey||ev.metaKey)&&ev.key==='Enter'){ev.preventDefault();parseAndRender(inputArea.value);}});
pmInit();
bootstrapAuto();
loadNodeData();
