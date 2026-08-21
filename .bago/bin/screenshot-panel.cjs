const { app, BrowserWindow } = require('electron');
const fs = require('fs');
const path = require('path');

const SHOT = path.resolve('electron-viewer/screenshot-panel.png');

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function main() {
  await app.whenReady();
  const win = new BrowserWindow({
    width: 1600,
    height: 1000,
    show: false,
    webPreferences: { contextIsolation: true, nodeIntegration: false },
  });

  await win.loadURL('http://127.0.0.1:8080/');
  await sleep(5000);

  // Dismiss any help overlay first.
  await win.webContents.executeJavaScript(`
    const help = document.querySelector('.help-backdrop');
    if (help) {
      const closeBtn = help.querySelector('button[title="Cerrar ayuda"], button.icon-button');
      closeBtn?.click();
    }
    true;
  `);
  await sleep(500);

  // Open the Capabilities panel via the command palette.
  win.webContents.sendInputEvent({ type: 'keyDown', keyCode: 'k', modifiers: ['control'] });
  win.webContents.sendInputEvent({ type: 'keyUp', keyCode: 'k', modifiers: ['control'] });
  await sleep(800);

  await win.webContents.executeJavaScript(`
    const input = document.querySelector('.command-palette-search input');
    if (input) {
      input.value = 'capacidades';
      input.dispatchEvent(new Event('input', { bubbles: true }));
    }
    true;
  `);
  await sleep(500);

  await win.webContents.executeJavaScript(`
    const buttons = document.querySelectorAll('.command-palette-list button');
    for (const btn of buttons) {
      if ((btn.textContent || '').toLowerCase().includes('capacidades')) {
        btn.click();
        break;
      }
    }
    true;
  `);
  await sleep(1500);

  const panelClass = await win.webContents.executeJavaScript(`
    const panel = document.querySelector('.inline-panel-host:not(.inline-chat-host)');
    panel?.className || 'NO_PANEL'
  `);
  const workspaceHidden = await win.webContents.executeJavaScript(`
    const ws = document.querySelector('.workspace-area');
    !!ws && getComputedStyle(ws).display === 'none'
  `);
  console.log('panel classes:', panelClass);
  console.log('workspace hidden:', workspaceHidden);

  const image = await win.capturePage();
  fs.writeFileSync(SHOT, image.toPNG());
  console.log('screenshot saved:', SHOT);

  await app.quit();
  process.exit(panelClass.includes('is-fullscreen') ? 0 : 1);
}

main().catch((err) => {
  console.error(err);
  app.quit();
  process.exit(1);
});
