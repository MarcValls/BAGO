// Preload: expone APIs nativas de Electron a la BAGO UI.
// La UI las detecta via window.bagoElectron y, si existen, usa el
// explorador de archivos nativo en vez del text input manual.

const { contextBridge, ipcRenderer } = require('electron');

// Las funciones que abren diálogos nativos se ejecutan en el main process
// via IPC. El preload solo expone el canal.
contextBridge.exposeInMainWorld('bagoElectron', {
  isViewer: true,

  // Abre el diálogo nativo de selección de carpeta.
  // Devuelve {path, canceled} o null si el usuario cancela.
  async chooseProjectRoot(options = {}) {
    return ipcRenderer.invoke('bago:choose-project-root', options);
  },

  async chooseWorkspaceRoot(options = {}) {
    return ipcRenderer.invoke('bago:choose-workspace-root', options);
  },

  // Notificación cuando otra instancia ya está activa.
  onInstanceActive(callback) {
    const handler = (_event, payload) => callback(payload);
    ipcRenderer.on('bago:instance-active', handler);
    return () => ipcRenderer.removeListener('bago:instance-active', handler);
  }
});
