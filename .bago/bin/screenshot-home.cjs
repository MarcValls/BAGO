const { app, BrowserWindow } = require('electron');
const fs = require('fs');
const path = require('path');

const SHOT = path.resolve('electron-viewer/screenshot-home.png');

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
  await sleep(6000);

  const statusHtml = await win.webContents.executeJavaScript(`
    document.querySelector('.start-chat-runtime-status')?.outerHTML || 'NO_RUNTIME_STATUS'
  `);
  console.log('runtime status HTML:', statusHtml.substring(0, 1200));

  const homeText = await win.webContents.executeJavaScript(`
    (document.querySelector('.start-chat-runtime-step')?.textContent || '') +
    ' | ' +
    (document.querySelector('.start-chat-no-recent-body .text-button')?.textContent || '')
  `);
  console.log('home actionable text:', homeText);

  const actionCount = await win.webContents.executeJavaScript(`
    document.querySelectorAll('.start-chat-runtime-item .text-button.compact').length
  `);
  console.log('runtime action buttons:', actionCount);

  const image = await win.capturePage();
  fs.writeFileSync(SHOT, image.toPNG());
  console.log('screenshot saved:', SHOT);

  await app.quit();
  const hasGuidance = homeText.includes('workspace') || homeText.includes('backend') || homeText.includes('proveedor');
  process.exit(hasGuidance && actionCount >= 2 ? 0 : 1);
}

main().catch((err) => {
  console.error(err);
  app.quit();
  process.exit(1);
});
