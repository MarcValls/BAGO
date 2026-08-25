const { app, BrowserWindow } = require('electron');
const fs = require('fs');
const path = require('path');

const SHOT = path.resolve('electron-viewer/screenshot-help.png');

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

  // Open help by dispatching the keyboard shortcut handler.
  await win.webContents.executeJavaScript(`
    const event = new KeyboardEvent('keydown', { key: '?', bubbles: true });
    window.dispatchEvent(event);
    true;
  `);
  await sleep(1500);

  // Ensure the help panel is in the DOM.
  await win.webContents.executeJavaScript(`
    if (!document.querySelector('.help-panel')) {
      const btn = Array.from(document.querySelectorAll('button')).find(b =>
        (b.getAttribute('title') || '').includes('ayuda') ||
        (b.getAttribute('aria-label') || '').includes('ayuda')
      );
      btn?.click();
    }
    true;
  `);
  await sleep(1000);

  const helpText = await win.webContents.executeJavaScript(`
    document.querySelector('.help-note')?.textContent || 'NO_HELP_NOTE'
  `);
  console.log('help note text:', helpText);

  const image = await win.capturePage();
  fs.writeFileSync(SHOT, image.toPNG());
  console.log('screenshot saved:', SHOT);

  await app.quit();
  process.exit(helpText.includes('pantalla completa') && helpText.includes('Ctrl+Shift+C') ? 0 : 1);
}

main().catch((err) => {
  console.error(err);
  app.quit();
  process.exit(1);
});
