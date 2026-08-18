import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const out = '/mnt/data/BAGO_UI_v2.3_screenshots';
fs.rmSync(out, { recursive: true, force: true });
fs.mkdirSync(out, { recursive: true });

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 940 }, deviceScaleFactor: 1 });
const page = await context.newPage();
await page.addInitScript(() => {
  localStorage.clear();
  localStorage.setItem('bago.ui.apiBase', 'http://127.0.0.1:8787');
  localStorage.setItem('bago.ui.state', JSON.stringify({
    sidebarCollapsed: false,
    activeSection: 'home',
    globalMode: 'normal',
    chatMode: 'live',
    chatPanel: 'hidden',
    inspectorLevel: 'summary',
    inspectorWidth: 360,
    helpOpen: false,
    commandPaletteOpen: false,
    apiBase: 'http://127.0.0.1:8787',
    apiToken: '',
    workspaceHint: '',
    drafts: {}
  }));
});

async function shot(name) {
  await page.waitForTimeout(450);
  await page.screenshot({ path: path.join(out, name), fullPage: false });
}

async function gotoSection(label, name) {
  await page.getByRole('button', { name: new RegExp(label, 'i') }).first().click();
  await page.waitForTimeout(550);
  await shot(name);
}

await page.goto('http://127.0.0.1:5179/', { waitUntil: 'networkidle' });
await page.waitForSelector('.workspace-shell');
await shot('01_home_cockpit.png');

await gotoSection('Workspace', '02_workspace.png');
await gotoSection('Grafo', '03_graph.png');
await gotoSection('Pipeline', '04_pipeline.png');
await gotoSection('Evidencia', '05_evidence.png');
await gotoSection('Contexto', '06_context.png');
await gotoSection('Operación', '07_system_operation.png');

await page.getByRole('button', { name: /Chat/i }).first().click();
await page.waitForTimeout(500);
await shot('08_chat_split.png');

await page.keyboard.press(process.platform === 'darwin' ? 'Meta+K' : 'Control+K');
await page.waitForTimeout(350);
await shot('09_command_palette.png');
await page.keyboard.press('Escape');
await page.waitForTimeout(250);

await page.keyboard.press('?');
await page.waitForTimeout(350);
await shot('10_help_overlay.png');
await page.keyboard.press('Escape');
await page.waitForTimeout(250);

await page.getByRole('button', { name: /Grafo/i }).first().click();
await page.waitForTimeout(300);
await page.locator('.graph-node').first().click();
await page.waitForTimeout(450);
await shot('11_inspector_drawer.png');

await browser.close();
console.log(out);
