const { contextBridge, clipboard, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('bagoElectron', {
  readClipboardText: () => clipboard.readText(),
  writeClipboardText: (text) => clipboard.writeText(String(text || '')),
  runCommand: (command) => ipcRenderer.invoke('bago:run-command', String(command || ''))
});
