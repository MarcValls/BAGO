const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { _electron: electron } = require('playwright');

const ROOT = path.resolve(__dirname, '..', '..');
const VIEWER = path.join(ROOT, 'electron-viewer');
const ELECTRON = path.join(ROOT, 'node_modules', 'electron', 'dist', 'electron.exe');
const SOURCE = process.env.BAGO_TEST_SCORE_PATH || path.join(ROOT, 'fixtures', 'CantinaBand_TubaTrio-TC.pdf');
const PACKAGE_ZIP = path.join(ROOT, 'output', 'playwright', 'music.score-transform-1.3.0.zip');
const OUTPUT = path.join(ROOT, 'output', 'playwright', 'cantina-band-live-output');
const SCREENSHOT = path.join(ROOT, 'output', 'playwright', 'electron-cantina-band-result.png');

async function main() {
  assert.ok(fs.existsSync(SOURCE), `No existe ${SOURCE}`);
  const app = await electron.launch({ executablePath: ELECTRON, args: ['.'], cwd: VIEWER });
  const errors = [];
  try {
    const window = await app.firstWindow();
    window.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
    window.on('pageerror', (error) => errors.push(error.message));
    await window.locator('.app-root').waitFor({ state: 'visible', timeout: 120000 });
    await window.evaluate(() => {
      localStorage.setItem('bago.first-run.v1.completed', 'true');
      sessionStorage.setItem('bago.start.chat-mode', 'open');
    });
    await window.reload({ waitUntil: 'domcontentloaded' });
    await window.locator('.app-root').waitFor({ state: 'visible', timeout: 120000 });
    const tourClose = window.getByRole('button', { name: 'Cerrar recorrido', exact: true });
    if (await tourClose.isVisible().catch(() => false)) await tourClose.click();
    assert.equal(await window.evaluate(() => Boolean(window.bagoElectron?.isViewer)), true);

    await window.locator('.sidebar-item').filter({ hasText: 'Grafo' }).click();
    await window.getByRole('button', { name: 'Capacidades', exact: true }).click();
    await window.locator('.capability-anatomy').waitFor({ state: 'visible', timeout: 30000 });
    await window.getByRole('button', { name: 'Externas', exact: true }).click();
    await window.getByLabel('Paquete ZIP').setInputFiles(PACKAGE_ZIP);
    await window.getByRole('checkbox', { name: 'Confío en este código local' }).check();
    await window.getByRole('button', { name: 'Importar', exact: true }).click();
    const packageItem = window.locator('.capability-package-list > button').filter({ hasText: 'music.score-transform · v1.3.0' });
    await packageItem.waitFor({ state: 'visible', timeout: 30000 });
    await packageItem.click();

    const detail = window.locator('.capability-package-detail');
    const activate = detail.getByRole('button', { name: 'Activar', exact: true });
    if (await activate.isVisible().catch(() => false)) await activate.click();
    await detail.getByRole('button', { name: 'Desactivar', exact: true }).waitFor({ state: 'visible', timeout: 30000 });
    await window.waitForFunction(() => {
      const button = [...document.querySelectorAll('.capability-package-title button')].find((item) => item.textContent?.trim() === 'Desactivar');
      return button instanceof HTMLButtonElement && !button.disabled;
    }, null, { timeout: 30000 });

    await detail.getByLabel('Ejecutable de Audiveris').fill('C:\\Program Files\\Audiveris\\Audiveris.exe');
    await detail.getByLabel('Carpeta de salida').fill(OUTPUT);
    await detail.getByLabel('Límite OMR en segundos').fill('540');
    await detail.getByRole('checkbox', { name: 'Separar voces en operación completa' }).check();
    const saveConfig = detail.getByRole('button', { name: 'Guardar configuración', exact: true });
    await saveConfig.click();
    await window.waitForFunction(() => {
      const button = [...document.querySelectorAll('button')].find((item) => item.textContent?.trim() === 'Guardar configuración');
      return button instanceof HTMLButtonElement && !button.disabled;
    }, null, { timeout: 30000 });

    await detail.getByLabel('Ruta de la partitura').fill(SOURCE);
    await detail.locator('.capability-package-workbench > section').nth(1).locator('select').selectOption('completo');
    await detail.getByLabel('Semitonos').fill('0');
    const execute = detail.getByRole('button', { name: 'Ejecutar con receipt', exact: true });
    assert.equal(await execute.isDisabled(), true, 'La ejecución debe exigir confirmación explícita');
    const priorReceipt = await detail.locator('.capability-receipt > small').first().textContent().catch(() => '');
    await detail.getByRole('checkbox', { name: /Confirmo esta ejecución/ }).check();
    await execute.click();

    await detail.getByText('Ejecución completada con receipt.', { exact: true }).waitFor({ state: 'visible', timeout: 600000 });
    await detail.getByRole('button', { name: 'Ejecutar con receipt', exact: true }).waitFor({ state: 'visible', timeout: 30000 });
    const receipt = detail.locator('.capability-receipt[data-status="succeeded"]');
    await receipt.waitFor({ state: 'visible', timeout: 30000 });
    await window.waitForFunction((previous) => {
      const current = document.querySelector('.capability-receipt > small')?.textContent || '';
      return Boolean(current) && current !== previous;
    }, priorReceipt || '', { timeout: 30000 });
    const receiptText = await receipt.innerText();
    assert.ok(receiptText.includes('audiveris-omr'));
    assert.ok(receiptText.includes('CantinaBand_TubaTrio-TC.pdf'));
    assert.ok(receiptText.includes('Audiveris'));
    assert.ok(receiptText.includes('structure'));

    const outputFiles = fs.readdirSync(OUTPUT);
    assert.ok(outputFiles.some((name) => /\.(mxl|musicxml|xml)$/i.test(name)), 'Audiveris no generó MusicXML');
    assert.ok(outputFiles.some((name) => name.includes('.normalized.musicxml')));

    const fit = await window.evaluate(() => {
      const root = document.documentElement;
      const panel = document.querySelector('.capability-packages')?.getBoundingClientRect();
      return {
        overflowX: root.scrollWidth > root.clientWidth,
        overflowY: root.scrollHeight > root.clientHeight,
        panelInside: Boolean(panel && panel.left >= 0 && panel.right <= window.innerWidth && panel.top >= 0 && panel.bottom <= window.innerHeight),
      };
    });
    assert.deepEqual(fit, { overflowX: false, overflowY: false, panelInside: true });
    fs.mkdirSync(path.dirname(SCREENSHOT), { recursive: true });
    await window.screenshot({ path: SCREENSHOT });
    assert.deepEqual(errors.filter((message) => !message.includes('favicon')), []);
    console.log(JSON.stringify({ ok: true, fit, screenshot: SCREENSHOT, output: OUTPUT, outputFiles }));
  } finally {
    await app.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
